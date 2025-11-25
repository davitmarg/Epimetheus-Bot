# bot/handlers.py
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from bot.buffer import buffer  # <-- import the shared buffer instance
from dotenv import load_dotenv
import os

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

app = App(token=SLACK_BOT_TOKEN)


@app.event("message")
def handle_message(event, say):
    # ignore bot messages
    if event.get("bot_id"):
        return

    buffer.ingest(event)
    print("Message ingested:", event.get("text", ""))


def start_bot():
    print("Starting Project Epimetheus bot...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
