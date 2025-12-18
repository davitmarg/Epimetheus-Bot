from typing import Dict, Any
from services.bot.app import slack_app
from services.bot.buffer import buffer
from services.bot import ui
from repository.llm_repository import get_agentic_repository
from utils.message_utils import extract_message_text
from utils.constants import (
    LOADING_EMOJI,
    SUCCESS_EMOJI,
    ERROR_EMOJI,
    DEFAULT_PROCESSING_ERROR_MESSAGE,
    DEFAULT_ERROR_MESSAGE,
    DEFAULT_GREETING_MESSAGE,
)


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
                ui.add_loading_reaction(channel, event_ts, slack_app.client)

                def say_wrapper(text: str, thread_ts: str = None):
                    try:
                        slack_app.client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts or event.get("ts"),
                            text=text,
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
                        client=slack_app.client,
                    )
                    return
                except Exception as e:
                    ui.replace_reaction(
                        channel, event_ts, LOADING_EMOJI, ERROR_EMOJI, slack_app.client
                    )
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
    ui.add_loading_reaction(channel, event_ts, client)

    try:
        text = event.get("text", "")
        message_text = extract_message_text(text)

        if not message_text or not message_text.strip():
            reply_text = DEFAULT_GREETING_MESSAGE
            ui.replace_reaction(channel, event_ts, LOADING_EMOJI, SUCCESS_EMOJI, client)
            ui.send_reply(channel, thread_ts, reply_text, say, client)
            return

        # Process mention using agentic repository
        agentic_repo = get_agentic_repository()
        reply_text = agentic_repo.process_mention(
            message_text=message_text,
            event=event,
            team_id=team_id,
            channel=channel,
            thread_ts=thread_ts,
        )

        # Ensure we have a reply
        if not reply_text or not reply_text.strip():
            reply_text = DEFAULT_PROCESSING_ERROR_MESSAGE

        # Send reply
        ui.send_reply(channel, thread_ts, reply_text, say, client)

        # Replace loading reaction with checkmark
        ui.replace_reaction(channel, event_ts, LOADING_EMOJI, SUCCESS_EMOJI, client)

    except Exception as e:
        ui.replace_reaction(channel, event_ts, LOADING_EMOJI, ERROR_EMOJI, client)
        error_reply = f"{DEFAULT_ERROR_MESSAGE} Error: {str(e)}"
        ui.send_reply(channel, thread_ts, error_reply, say, client)
