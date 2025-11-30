import json
import os
import redis
from typing import Dict, Any, List, Tuple

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

BATCH_SIZE = 50


class RedisBuffer:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )

    def _get_keys(self, team_id: str) -> Tuple[str, str, str, str]:
        base = f"epimetheus:{team_id}"
        return (
            f"{base}:dirty_list",  # List of active threads (Order preserved)
            f"{base}:dirty_set",  # Set for fast lookup
            f"{base}:msg_count",  # Message counter for this team
            f"{base}:thread:",  # Prefix for thread lists
        )

    def ingest(self, event: Dict[str, Any], team_id: str):
        if not team_id:
            return

        serialized_event = json.dumps(event)
        thread_id = event.get("thread_ts") or event.get("ts")

        dirty_list_key, dirty_set_key, msg_count_key, thread_prefix = self._get_keys(
            team_id
        )
        thread_key = f"{thread_prefix}{thread_id}"

        pipe = self.client.pipeline()

        pipe.rpush(thread_key, serialized_event)
        pipe.incr(msg_count_key)
        pipe.sadd(dirty_set_key, thread_id)

        results = pipe.execute()

        is_new_thread_in_batch = results[2] == 1
        current_count = results[1]

        if is_new_thread_in_batch:
            self.client.rpush(dirty_list_key, thread_id)

        if current_count >= BATCH_SIZE:
            self._dispatch(team_id)

    def _dispatch(self, team_id: str):
        dirty_list_key, dirty_set_key, msg_count_key, thread_prefix = self._get_keys(
            team_id
        )

        previous_count = self.client.getset(msg_count_key, 0)
        if not previous_count or int(previous_count) == 0:
            return

        active_threads = self.client.lrange(dirty_list_key, 0, -1)
        self.client.delete(dirty_list_key, dirty_set_key)

        threads_payload = []

        for thread_id in active_threads:
            thread_key = f"{thread_prefix}{thread_id}"

            pipe = self.client.pipeline()
            pipe.lrange(thread_key, 0, -1)
            pipe.delete(thread_key)
            results = pipe.execute()

            messages_raw = results[0]
            if messages_raw:
                messages = [json.loads(msg) for msg in messages_raw]
                threads_payload.append({"thread_id": thread_id, "messages": messages})

        if threads_payload:
            payload = {"team_id": team_id, "threads": threads_payload}
            self._send_to_updater(payload)

    def _send_to_updater(self, payload: Dict[str, Any]):
        print(
            f"Dispatching batch for Team {payload['team_id']}: {len(payload['threads'])} active threads."
        )
        # HTTP request to updater_service goes here


buffer = RedisBuffer()
