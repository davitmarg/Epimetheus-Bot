"""
Slack Repository

Handles Slack API operations for sending notifications and replies.
"""

import os
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")


class SlackRepository:
    """Repository for Slack API operations"""
    
    def __init__(self):
        if not SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN must be set")
        self.client = WebClient(token=SLACK_BOT_TOKEN)
    
    def send_reply(self, channel: str, thread_ts: str, text: str) -> bool:
        """
        Send a reply to a Slack message thread
        
        Args:
            channel: Slack channel ID
            thread_ts: Thread timestamp (ts) of the message to reply to
            text: Message text to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text
            )
            return response["ok"]
        except SlackApiError as e:
            print(f"Error sending Slack reply: {e.response['error']}")
            return False
    
    def send_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> bool:
        """
        Send a message to a Slack channel
        
        Args:
            channel: Slack channel ID
            text: Message text to send
            thread_ts: Optional thread timestamp to reply in thread
            
        Returns:
            True if successful, False otherwise
        """
        try:
            kwargs = {
                "channel": channel,
                "text": text
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            
            response = self.client.chat_postMessage(**kwargs)
            return response["ok"]
        except SlackApiError as e:
            print(f"Error sending Slack message: {e.response['error']}")
            return False
    
    def send_blocks(self, channel: str, blocks: list, thread_ts: Optional[str] = None) -> bool:
        """
        Send a message with Slack Block Kit blocks
        
        Args:
            channel: Slack channel ID
            blocks: List of Slack Block Kit blocks
            thread_ts: Optional thread timestamp to reply in thread
            
        Returns:
            True if successful, False otherwise
        """
        try:
            kwargs = {
                "channel": channel,
                "blocks": blocks
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            
            response = self.client.chat_postMessage(**kwargs)
            return response["ok"]
        except SlackApiError as e:
            print(f"Error sending Slack blocks: {e.response['error']}")
            return False


_slack_repository = None


def get_slack_repository() -> Optional[SlackRepository]:
    """Get or create the Slack repository singleton"""
    global _slack_repository
    if _slack_repository is None:
        try:
            _slack_repository = SlackRepository()
        except ValueError:
            # Slack token not configured, return None
            return None
    return _slack_repository


def send_document_update_notification(
    channel: str,
    thread_ts: str,
    doc_id: str,
    doc_name: str,
    message_count: int,
    success: bool = True,
    error_message: Optional[str] = None,
    change_summary: Optional[str] = None
) -> bool:
    """
    Send a notification about a document update
    
    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp to reply to
        doc_id: Google Docs document ID
        doc_name: Document name
        message_count: Number of messages processed
        success: Whether the update was successful
        error_message: Error message if update failed
        change_summary: Optional summary of changes made to the document
        
    Returns:
        True if notification sent successfully, False otherwise
    """
    repo = get_slack_repository()
    if not repo:
        print("Slack repository not available, skipping notification")
        return False
    
    # Generate Google Docs URL
    doc_url = f"https://docs.google.com/document/d/{doc_id}"
    
    if success:
        text = (
            f"✅ Document updated successfully!\n"
            f"📄 *{doc_name}*\n"
            f"📊 Processed {message_count} message(s)\n"
        )
        
        # Add change summary if available
        if change_summary:
            text += f"\n📝 *Summary of Changes:*\n{change_summary}\n"
        
        text += f"\n🔗 <{doc_url}|View Document>"
    else:
        text = (
            f"❌ Document update failed\n"
            f"📄 *{doc_name}*\n"
            f"Error: {error_message or 'Unknown error'}"
        )
    
    return repo.send_reply(channel, thread_ts, text)

