import os
from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")

# Initialize the Bolt App
slack_app = App(token=SLACK_BOT_TOKEN, name="Listener Bot")
