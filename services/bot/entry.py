import os
from slack_bolt.adapter.socket_mode import SocketModeHandler
from services.bot.app import slack_app, SLACK_APP_TOKEN

import services.bot.handlers


def start():
    """Start the Listener Bot service"""
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()
