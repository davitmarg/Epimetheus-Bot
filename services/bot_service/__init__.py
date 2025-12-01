"""
Bot Service

Slack bot listener that ingests messages and buffers them for processing.
"""

import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from services.bot_service.buffer import buffer

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")

slack_app = App(token=SLACK_BOT_TOKEN)


@slack_app.event("message")
def handle_message(event, body, say):
    """Handle incoming Slack message events"""
    
    if event.get("bot_id"):
        return

    team_id = body.get("team_id")
    buffer.ingest(event, team_id)
    print(f"Message ingested for team {team_id}")


@slack_app.event("app_mention")
def handle_message(event, body, say):
    """Handle incoming Slack message events"""
    
    if event.get("bot_id"):
        return

    team_id = body.get("team_id")
    buffer.ingest(event, team_id)
    print(f"Message ingested for team {team_id}")


def start_bot_service():
    """Start the Slack bot service"""
    print("Starting Project Epimetheus bot...")
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()
