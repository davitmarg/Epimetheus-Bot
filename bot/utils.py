# bot/utils.py


def format_message(event: dict) -> str:
    """
    Format a Slack message event into a readable string.
    """
    user = event.get("user", "unknown")
    channel = event.get("channel", "unknown")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts")

    formatted = f"New message from {user} in channel {channel}"
    if thread_ts:
        formatted += f" (thread reply to {thread_ts})"
    formatted += f":\n{text}\n"
    return formatted
