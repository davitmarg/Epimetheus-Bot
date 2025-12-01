# bot/handlers.py
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from bot.buffer import buffer
from dotenv import load_dotenv
import os

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

app = App(token=SLACK_BOT_TOKEN)


@app.event("message")
def handle_message(event, body, say):
    if event.get("bot_id"):
        return

    team_id = body.get("team_id")
    buffer.ingest(event, team_id)
    print(f"Message ingested for team {team_id}")


def start_bot():
    print("Starting Project Epimetheus bot...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
