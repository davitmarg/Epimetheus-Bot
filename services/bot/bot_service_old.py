"""
Bot Service

Handles Slack bot events including message buffering and app mentions.
Processes mentions using agentic repository for document updates and Q&A.
"""

import os
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from repository.llm_repository import get_agentic_repository
from repository.slack_repository import get_slack_repository
from utils.db_utils import get_redis_client, REDIS_QUEUE_KEY
from utils.message_utils import extract_message_text
from utils.constants import (
    LOADING_EMOJI,
    SUCCESS_EMOJI,
    ERROR_EMOJI,
    DEFAULT_NO_RESPONSE_MESSAGE,
    DEFAULT_PROCESSING_ERROR_MESSAGE,
    DEFAULT_ERROR_MESSAGE,
    DEFAULT_GREETING_MESSAGE,
)

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")

slack_app = App(token=SLACK_BOT_TOKEN, name="Listener Bot")
BATCH_SIZE = 2


class MessageBuffer:
    """Buffers messages by thread and dispatches to Redis queue when batch size is reached"""
    
    def __init__(self):
        self.client = get_redis_client()

    def _get_keys(self, team_id: str):
        """Generate Redis keys for thread tracking and batching"""
        base = f"botbuffer:{team_id}"
        return (
            f"{base}:dirty_list",
            f"{base}:dirty_set",
            f"{base}:msg_count",
            f"{base}:thread:",
        )

    def ingest(self, event: Dict[str, Any], team_id: str):
        """Ingest a single message and buffer it by thread"""
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

        is_new_thread = results[2] == 1
        current_count = results[1]

        if is_new_thread:
            self.client.rpush(dirty_list_key, thread_id)

        if current_count >= BATCH_SIZE:
            self._dispatch(team_id)

    def _dispatch(self, team_id: str):
        """Send all buffered threads to the updater and reset tracking keys"""
        dirty_list_key, dirty_set_key, msg_count_key, thread_prefix = self._get_keys(
            team_id
        )

        total_count = self.client.getset(msg_count_key, 0)
        if not total_count or int(total_count) == 0:
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
        """Push payload to Redis queue for the updater"""
        serialized_payload = json.dumps(payload)
        self.client.rpush(REDIS_QUEUE_KEY, serialized_payload)


# Global buffer instance
buffer = MessageBuffer()


@slack_app.event("message")
def handle_message(event: Dict[str, Any], body: Dict[str, Any], ack):
    """
    Handle regular messages - send to queue for log-based knowledge extraction.
    Ignores bot messages and app_mentions.
    """
    try:
        ack()
    except Exception:
        pass
    
    # Ignore bot messages (including our own)
    if event.get("bot_id"):
        return
    
    # Fallback: Check if message contains bot mention
    # Sometimes app_mention events don't come through, so check message text
    text = event.get("text", "")
    channel = event.get("channel")
    
    if "<@" in text and ">" in text and channel:
        try:
            bot_info = slack_app.client.auth_test()
            bot_user_id = bot_info.get("user_id")
            
            if bot_user_id and f"<@{bot_user_id}>" in text:
                event_ts = event.get("ts")
                _add_loading_reaction(channel, event_ts, slack_app.client)
                
                def say_wrapper(text: str, thread_ts: str = None):
                    try:
                        slack_app.client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts or event.get("ts"),
                            text=text
                        )
                        return True
                    except Exception:
                        return False
                
                try:
                    handle_app_mention(
                        event=event,
                        body=body,
                        say=say_wrapper,
                        ack=lambda: None,
                        client=slack_app.client
                    )
                    return
                except Exception as e:
                    _replace_reaction(channel, event_ts, LOADING_EMOJI, ERROR_EMOJI, slack_app.client)
        except Exception:
            pass
    
    team_id = body.get("team_id")
    if not team_id:
        return
    
    # Send to buffer/queue for log-based processing
    try:
        buffer.ingest(event, team_id)
    except Exception:
        pass


def send_reply(channel: str, thread_ts: str, text: str, say: Optional[Any] = None, client: Optional[Any] = None) -> bool:
    """
    Send reply using say, client, or slack_repo.
    
    Returns:
        True if successful, False otherwise
    """
    if not text or not text.strip():
        text = DEFAULT_NO_RESPONSE_MESSAGE
    
    # Try say() first (Slack Bolt's built-in method)
    if say:
        try:
            say(text=text, thread_ts=thread_ts)
            return True
        except Exception:
            pass
    
    # Try client directly
    if client:
        try:
            response = client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
            if response.get("ok"):
                return True
        except Exception:
            pass
    
    # Fallback to slack_repo
    slack_repo = get_slack_repository()
    if slack_repo:
        try:
            return slack_repo.send_reply(channel=channel, thread_ts=thread_ts, text=text)
        except Exception:
            pass
    
    return False


def _add_loading_reaction(channel: str, timestamp: str, client: Optional[Any] = None) -> bool:
    """Add loading emoji reaction to a message"""
    try:
        if client:
            client.reactions_add(channel=channel, timestamp=timestamp, name=LOADING_EMOJI)
            return True
        else:
            slack_repo = get_slack_repository()
            if slack_repo:
                return slack_repo.add_reaction(channel, timestamp, LOADING_EMOJI)
    except Exception:
        pass
    return False


def _replace_reaction(channel: str, timestamp: str, old_emoji: str, new_emoji: str, client: Optional[Any] = None) -> bool:
    """Replace one reaction with another"""
    try:
        if client:
            try:
                client.reactions_remove(channel=channel, timestamp=timestamp, name=old_emoji)
            except Exception:
                pass
            try:
                client.reactions_add(channel=channel, timestamp=timestamp, name=new_emoji)
            except Exception:
                pass
            return True
        else:
            slack_repo = get_slack_repository()
            if slack_repo:
                return slack_repo.replace_reaction(channel, timestamp, old_emoji, new_emoji)
    except Exception:
        pass
    return False


@slack_app.event("app_mention")
def handle_app_mention(event: Dict[str, Any], body: Dict[str, Any], say, ack, client):
    """Handle app mentions - process using agentic repository and reply"""
    try:
        ack()
    except Exception:
        return
    
    # Ignore bot messages
    if event.get("bot_id"):
        return
    
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    team_id = body.get("team_id")
    event_ts = event.get("ts")
    
    if not channel or not team_id:
        return
    
    # Add loading reaction immediately
    _add_loading_reaction(channel, event_ts, client)
    
    try:
        text = event.get("text", "")
        message_text = extract_message_text(text)
        
        if not message_text or not message_text.strip():
            reply_text = DEFAULT_GREETING_MESSAGE
            _replace_reaction(channel, event_ts, LOADING_EMOJI, SUCCESS_EMOJI, client)
            send_reply(channel, thread_ts, reply_text, say, client)
            return
        
        # Process mention using agentic repository
        agentic_repo = get_agentic_repository()
        reply_text = agentic_repo.process_mention(
            message_text=message_text,
            event=event,
            team_id=team_id,
            channel=channel,
            thread_ts=thread_ts
        )
        
        # Ensure we have a reply
        if not reply_text or not reply_text.strip():
            reply_text = DEFAULT_PROCESSING_ERROR_MESSAGE
        
        # Send reply
        send_reply(channel, thread_ts, reply_text, say, client)
        
        # Replace loading reaction with checkmark
        _replace_reaction(channel, event_ts, LOADING_EMOJI, SUCCESS_EMOJI, client)
        
    except Exception as e:
        _replace_reaction(channel, event_ts, LOADING_EMOJI, ERROR_EMOJI, client)
        error_reply = f"{DEFAULT_ERROR_MESSAGE} Error: {str(e)}"
        send_reply(channel, thread_ts, error_reply, say, client)


def start():
    """Start the Listener Bot service"""
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()
