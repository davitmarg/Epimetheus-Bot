"""
Slack Repository

Handles Slack API operations for sending notifications and replies.
"""

import os
from typing import Dict, Any, Optional, List
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
    
    def get_channel_history(self, channel: str, limit: int = 50, oldest: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get message history from a Slack channel
        
        Args:
            channel: Slack channel ID
            limit: Maximum number of messages to retrieve (default: 50)
            oldest: Optional timestamp of oldest message to retrieve
            
        Returns:
            List of message dictionaries
        """
        try:
            kwargs = {
                "channel": channel,
                "limit": limit
            }
            if oldest:
                kwargs["oldest"] = oldest
            
            response = self.client.conversations_history(**kwargs)
            if response["ok"]:
                return response.get("messages", [])
            return []
        except SlackApiError as e:
            print(f"Error fetching channel history: {e.response.get('error', str(e))}")
            return []
    
    def get_thread_replies(self, channel: str, thread_ts: str) -> List[Dict[str, Any]]:
        """
        Get all replies in a Slack thread
        
        Args:
            channel: Slack channel ID
            thread_ts: Thread timestamp
            
        Returns:
            List of message dictionaries in the thread
        """
        try:
            response = self.client.conversations_replies(
                channel=channel,
                ts=thread_ts
            )
            if response["ok"]:
                return response.get("messages", [])
            return []
        except SlackApiError as e:
            print(f"Error fetching thread replies: {e.response.get('error', str(e))}")
            return []
    
    def send_document_update_notification(
        self,
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

        return self.send_reply(channel, thread_ts, text)
    
    def add_reaction(self, channel: str, timestamp: str, emoji: str) -> bool:
        """
        Add a reaction emoji to a message.
        
        Args:
            channel: Slack channel ID
            timestamp: Message timestamp (ts)
            emoji: Emoji name (without colons, e.g., "hourglass_flowing_sand", "white_check_mark")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            return response.get("ok", False)
        except SlackApiError as e:
            print(f"Error adding reaction {emoji}: {e.response.get('error', str(e))}")
            return False
    
    def remove_reaction(self, channel: str, timestamp: str, emoji: str) -> bool:
        """
        Remove a reaction emoji from a message.
        
        Args:
            channel: Slack channel ID
            timestamp: Message timestamp (ts)
            emoji: Emoji name (without colons, e.g., "hourglass_flowing_sand", "white_check_mark")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.client.reactions_remove(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            return response.get("ok", False)
        except SlackApiError as e:
            print(f"Error removing reaction {emoji}: {e.response.get('error', str(e))}")
            return False
    
    def replace_reaction(self, channel: str, timestamp: str, old_emoji: str, new_emoji: str) -> bool:
        """
        Replace one reaction with another on a message.
        
        Args:
            channel: Slack channel ID
            timestamp: Message timestamp (ts)
            old_emoji: Emoji name to remove
            new_emoji: Emoji name to add
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        if old_emoji:
            success = self.remove_reaction(channel, timestamp, old_emoji) and success
        if new_emoji:
            success = self.add_reaction(channel, timestamp, new_emoji) and success
        return success

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
