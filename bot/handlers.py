# bot/handlers.py
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from bot.utils import format_message
from dotenv import load_dotenv
import os

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

app = App(token=SLACK_BOT_TOKEN)


@app.event("message")
def handle_message_events(event, say):
    print("Raw event:", event)
    formatted = format_message(event)
    print(f"! {formatted}")


def start_bot():
    """Start the Slack bot using Socket Mode."""
    print("Starting Project Epimetheus bot...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    start_bot()
