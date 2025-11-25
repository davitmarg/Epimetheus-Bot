import json
import os
import redis
from typing import Dict, Any, List

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

# Keys
DIRTY_LIST_KEY = "epimetheus:dirty_threads_list"  # Preserves order of active threads
DIRTY_SET_KEY = "epimetheus:dirty_threads_set"  # Fast lookup for uniqueness
MSG_COUNT_KEY = "epimetheus:global_msg_count"  # Total messages in batch
THREAD_PREFIX = "epimetheus:thread:"  # Prefix for individual thread data

BATCH_SIZE = 50


class RedisBuffer:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )

    def ingest(self, event: Dict[str, Any]):
        serialized_event = json.dumps(event)

        # Determine the Thread ID (Group ID)
        # If 'thread_ts' exists, it's a reply. If not, use 'ts' (it's a new thread/message).
        thread_id = event.get("thread_ts") or event.get("ts")

        pipe = self.client.pipeline()

        # 1. Push message to its specific thread list
        thread_key = f"{THREAD_PREFIX}{thread_id}"
        pipe.rpush(thread_key, serialized_event)

        # 2. Increment global batch counter
        pipe.incr(MSG_COUNT_KEY)

        # 3. Track this thread as "Dirty" (Active) if not already
        # We use SISMEMBER to avoid race conditions in Python logic, but here we optimistically
        # try to add to SET. If SADD returns 1, it's new -> push to LIST.
        pipe.sadd(DIRTY_SET_KEY, thread_id)

        results = pipe.execute()

        # results[2] is the result of SADD. 1 = New element, 0 = Already exists.
        is_new_thread_in_batch = results[2] == 1
        current_count = results[1]

        if is_new_thread_in_batch:
            self.client.rpush(DIRTY_LIST_KEY, thread_id)

        if current_count >= BATCH_SIZE:
            self._dispatch()

    def print_messages(self):
        # print messages thread by thread no matter dirty or not
        threads = self.client.keys(f"{THREAD_PREFIX}*")
        for thread_key in threads:
            thread_id = thread_key.replace(THREAD_PREFIX, "")
            messages = self.client.lrange(thread_key, 0, -1)
            print(f"Thread ID: {thread_id}")
            for msg in messages:
                event = json.loads(msg)
                print(f" - {event.get('text', '')}", sep=" ")
            print()

    def _dispatch(self):
        # 1. Atomic Reset: Reset count so other workers start a new batch immediately
        # getset ensures we only dispatch once if multiple threads race here
        previous_count = self.client.getset(MSG_COUNT_KEY, 0)
        if not previous_count or int(previous_count) == 0:
            return

        # 2. Get all active thread IDs in insertion order
        active_threads = self.client.lrange(DIRTY_LIST_KEY, 0, -1)

        # 3. Clear the tracking keys immediately so new ingests start fresh
        self.client.delete(DIRTY_LIST_KEY, DIRTY_SET_KEY)

        payload_data = []

        # 4. Collect and Flush messages for each thread
        # We use a pipeline to Atomically Get and Delete the data for each thread
        # This ensures no messages are lost if a new one arrives during reading
        for thread_id in active_threads:
            thread_key = f"{THREAD_PREFIX}{thread_id}"

            pipe = self.client.pipeline()
            pipe.lrange(thread_key, 0, -1)
            pipe.delete(thread_key)
            results = pipe.execute()

            messages_raw = results[0]
            if messages_raw:
                messages = [json.loads(msg) for msg in messages_raw]
                payload_data.append({"thread_id": thread_id, "messages": messages})

        # 5. Send
        if payload_data:
            self._send_to_updater(payload_data)

    def _send_to_updater(self, data: List[Dict[str, Any]]):
        payload = {"threads": data}
        print(f"Dispatching {len(data)} threads to Updater Service")


buffer = RedisBuffer()
