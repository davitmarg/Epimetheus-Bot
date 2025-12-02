"""
Redis Buffer

Handles message buffering for the Slack bot. Processes messages one by one.
"""

import json
from typing import Dict, Any
from utils.db_utils import get_redis_client, REDIS_QUEUE_KEY


class BotBuffer:
    def __init__(self):
        self.client = get_redis_client()

    def ingest(self, event: Dict[str, Any], team_id: str):
        """Ingest a single message and dispatch it immediately to the updater queue"""
        if not team_id:
            return

        # Create payload with single message
        thread_id = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        
        payload = {
            "team_id": team_id,
            "channel": channel,  # Include channel for Slack replies
            "thread_ts": thread_id,  # Include thread_ts for Slack replies
            "threads": [
                {
                    "thread_id": thread_id,
                    "messages": [event]
                }
            ]
        }
        
        self._send_to_updater(payload)
        print(f"✓ Message ingested and dispatched for team {team_id}, thread {thread_id}")

    def _send_to_updater(self, payload: Dict[str, Any]):
        """Push message payload to Redis queue for updater service to consume"""
        serialized_payload = json.dumps(payload)
        result = self.client.rpush(REDIS_QUEUE_KEY, serialized_payload)
        queue_length = self.client.llen(REDIS_QUEUE_KEY)
        print(f"✓ Pushed to queue '{REDIS_QUEUE_KEY}'. Queue length: {queue_length}")

buffer = BotBuffer()
