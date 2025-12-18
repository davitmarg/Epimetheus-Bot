import logging
from typing import Optional, Any
from repository.slack_repository import get_slack_repository
from repository.document_repository import get_document_repository
from utils.constants import LOADING_EMOJI, DEFAULT_NO_RESPONSE_MESSAGE


def send_reply(
    channel: str,
    thread_ts: str,
    text: str,
    say: Optional[Any] = None,
    client: Optional[Any] = None,
    team_id: Optional[str] = None,
    bot_id: Optional[str] = None,
) -> bool:
    """
    Send reply using say, client, or slack_repo.
    Also saves the bot response to MongoDB.

    Returns:
        True if successful, False otherwise
    """
    if not text or not text.strip():
        text = DEFAULT_NO_RESPONSE_MESSAGE

    response_ts = None
    success = False

    # Try say() first (Slack Bolt's built-in method)
    if say:
        try:
            result = say(text=text, thread_ts=thread_ts)
            if result:
                # Extract ts from result if available
                if isinstance(result, dict) and result.get("ok"):
                    response_ts = result.get("ts")
                success = True
        except Exception:
            pass

    # Try client directly
    if not success and client:
        try:
            response = client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=text
            )
            if response.get("ok"):
                response_ts = response.get("ts")
                success = True
        except Exception:
            pass

    # Fallback to slack_repo
    if not success:
        slack_repo = get_slack_repository()
        if slack_repo:
            try:
                result = slack_repo.send_reply(
                    channel=channel, thread_ts=thread_ts, text=text, team_id=team_id, bot_id=bot_id
                )
                if result:
                    success = True
            except Exception:
                pass

    # Save bot response to MongoDB if we have the necessary info
    if success and team_id and channel:
        try:
            # Get bot_id if not provided
            if not bot_id and client:
                try:
                    bot_info = client.auth_test()
                    bot_id = bot_info.get("user_id")
                except Exception:
                    pass
            
            if bot_id:
                # Generate timestamp if not available from response
                import time
                if not response_ts:
                    response_ts = str(time.time())
                
                document_repo = get_document_repository()
                if document_repo is None:
                    logging.error(f"✗ ERROR: document_repository is None, cannot save bot response")
                    logging.error(f"   Channel: {channel}, Thread: {thread_ts}, Text: {text[:50]}...")
                else:
                    message_data = {
                        "ts": response_ts,
                        "channel": channel,
                        "team_id": team_id,
                        "user": bot_id,  # Bot user ID
                        "text": text,
                        "thread_ts": thread_ts,
                        "bot_id": bot_id,
                    }
                    success = document_repo.save_message(message_data)
                    if not success:
                        logging.error(f"✗ ERROR: save_message returned False for bot response")
                        logging.error(f"   Channel: {channel}, Thread: {thread_ts}")
                        logging.error(f"   Message data: {message_data}")
            else:
                logging.warning(f"⚠ WARNING: Cannot save bot response - bot_id is None")
                logging.warning(f"   Channel: {channel}, Thread: {thread_ts}")
        except Exception as e:
            # Don't fail if message storage fails, but log the error
            import traceback
            logging.error(f"✗ EXCEPTION: Failed to store bot response in MongoDB: {e}")
            logging.error(f"   Channel: {channel}, Thread: {thread_ts}, Text: {text[:50]}...")
            logging.error(f"   Traceback:\n{traceback.format_exc()}")

    return success


def add_loading_reaction(
    channel: str, timestamp: str, client: Optional[Any] = None
) -> bool:
    """Add loading emoji reaction to a message"""
    try:
        if client:
            client.reactions_add(
                channel=channel, timestamp=timestamp, name=LOADING_EMOJI
            )
            return True
        else:
            slack_repo = get_slack_repository()
            if slack_repo:
                return slack_repo.add_reaction(channel, timestamp, LOADING_EMOJI)
    except Exception:
        pass
    return False


def replace_reaction(
    channel: str,
    timestamp: str,
    old_emoji: str,
    new_emoji: str,
    client: Optional[Any] = None,
) -> bool:
    """Replace one reaction with another"""
    try:
        if client:
            try:
                client.reactions_remove(
                    channel=channel, timestamp=timestamp, name=old_emoji
                )
            except Exception:
                pass
            try:
                client.reactions_add(
                    channel=channel, timestamp=timestamp, name=new_emoji
                )
            except Exception:
                pass
            return True
        else:
            slack_repo = get_slack_repository()
            if slack_repo:
                return slack_repo.replace_reaction(
                    channel, timestamp, old_emoji, new_emoji
                )
    except Exception:
        pass
    return False
