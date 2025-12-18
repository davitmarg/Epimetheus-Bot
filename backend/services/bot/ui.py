from typing import Optional, Any
from repository.slack_repository import get_slack_repository
from utils.constants import LOADING_EMOJI, DEFAULT_NO_RESPONSE_MESSAGE


def send_reply(
    channel: str,
    thread_ts: str,
    text: str,
    say: Optional[Any] = None,
    client: Optional[Any] = None,
) -> bool:
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
            response = client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=text
            )
            if response.get("ok"):
                return True
        except Exception:
            pass

    # Fallback to slack_repo
    slack_repo = get_slack_repository()
    if slack_repo:
        try:
            return slack_repo.send_reply(
                channel=channel, thread_ts=thread_ts, text=text
            )
        except Exception:
            pass

    return False


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
