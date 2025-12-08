"""
Entry Module
Handles Redis queue consumption and service startup.
"""

import time
import json
from dotenv import load_dotenv

# Import database utilities
from utils.db_utils import get_redis_client, REDIS_QUEUE_KEY

# Import local modules
from services.updater.core import ingest_messages

load_dotenv()

redis_client = get_redis_client()


def consume_from_redis():
    """
    Consume messages from Redis queue as a log.

    Continuously processes messages from queue, checking chunks for knowledge extraction
    and only updating documents when needed.
    """
    print(f"Starting Redis consumer on queue: {REDIS_QUEUE_KEY}")
    print(f"Update processing uses BOTH direct calls and Redis queue consumption.")
    print(f"Waiting for messages from Redis queue...")

    # Verify Redis connection and queue status
    try:
        redis_client.ping()
        queue_length = redis_client.llen(REDIS_QUEUE_KEY)
        print(f"✓ Redis connected. Queue '{REDIS_QUEUE_KEY}' length: {queue_length}")
        if queue_length > 0:
            print(f"  Found {queue_length} message(s) already in queue")
    except Exception as e:
        print(f"✗ Redis connection check failed: {e}")

    last_heartbeat = time.time()
    heartbeat_interval = 30  # Print heartbeat every 30 seconds

    while True:
        try:
            # Blocking pop from queue (wait up to 1 second)
            # blpop returns (key, value) tuple or None if timeout
            result = redis_client.blpop(REDIS_QUEUE_KEY, timeout=1)
            if result:
                # result is a tuple: (key, value)
                queue_key, payload_json = result

                try:
                    payload = json.loads(payload_json)
                    team_id = payload.get("team_id", "unknown")
                    thread_count = len(payload.get("threads", []))

                    total_messages = sum(
                        len(t.get("messages", [])) for t in payload.get("threads", [])
                    )
                    print(
                        f"✓ Received message(s) for team {team_id}: {thread_count} thread(s), {total_messages} message(s)"
                    )
                    ingest_messages(payload)
                    print(f"✓ Successfully processed message(s) for team {team_id}")

                except json.JSONDecodeError as e:
                    print(f"✗ Error decoding JSON payload: {e}")
                    print(f"  Raw payload: {payload_json[:200]}...")
                    continue
                except Exception as e:
                    print(f"✗ Error processing batch: {e}")
                    import traceback

                    traceback.print_exc()
                    continue
            else:
                # No message available, continue polling
                # Print periodic heartbeat to show service is still running
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    queue_length = redis_client.llen(REDIS_QUEUE_KEY)
                    print(
                        f"⏳ Waiting for messages on queue: {REDIS_QUEUE_KEY} (current length: {queue_length})"
                    )
                    last_heartbeat = current_time
                time.sleep(0.1)

        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "connectionerror" in error_str:
                print(f"✗ Redis connection error: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                # Try to reconnect
                try:
                    redis_client.ping()
                    print(f"✓ Redis connection restored")
                except:
                    pass
            else:
                print(f"✗ Unexpected error in consume loop: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(1)


def start():
    """Start the updater service consumer"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")
    consume_from_redis()
