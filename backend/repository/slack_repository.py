"""
Slack Repository

Handles Slack API operations for sending notifications and replies.
"""

import os
import logging
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
    
    def send_reply(self, channel: str, thread_ts: str, text: str, team_id: Optional[str] = None, bot_id: Optional[str] = None) -> bool:
        """
        Send a reply to a Slack message thread
        Also saves the bot response to MongoDB.
        
        Args:
            channel: Slack channel ID
            thread_ts: Thread timestamp (ts) of the message to reply to
            text: Message text to send
            team_id: Optional team ID for saving the message
            bot_id: Optional bot user ID for saving the message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text
            )
            success = response.get("ok", False)
            response_ts = response.get("ts")
            
            # Save bot response to MongoDB if we have the necessary info
            if success and team_id and channel:
                try:
                    # Get bot_id if not provided
                    if not bot_id:
                        try:
                            bot_info = self.client.auth_test()
                            bot_id = bot_info.get("user_id")
                        except Exception:
                            pass
                    
                    if bot_id:
                        # Generate timestamp if not available from response
                        import time
                        if not response_ts:
                            response_ts = str(time.time())
                        
                        from repository.document_repository import get_document_repository
                        document_repo = get_document_repository()
                        if document_repo is None:
                            logging.error(f"✗ ERROR: document_repository is None, cannot save bot response")
                            logging.error(f"   Channel: {channel}, Thread: {thread_ts}, Text: {text[:50]}...")
                        else:
                            message_data = {
                                "ts": response_ts,
                                "channel": channel,
                                "team_id": team_id,
                                "user": bot_id,  # Bot user ID
                                "text": text,
                                "thread_ts": thread_ts,
                                "bot_id": bot_id,
                            }
                            success = document_repo.save_message(message_data)
                            if not success:
                                logging.error(f"✗ ERROR: save_message returned False for bot response")
                                logging.error(f"   Channel: {channel}, Thread: {thread_ts}")
                                logging.error(f"   Message data: {message_data}")
                    else:
                        logging.warning(f"⚠ WARNING: Cannot save bot response - bot_id is None")
                        logging.warning(f"   Channel: {channel}, Thread: {thread_ts}")
                except Exception as e:
                    # Don't fail if message storage fails, but log the error
                    import traceback
                    logging.error(f"✗ EXCEPTION: Failed to store bot response in MongoDB: {e}")
                    logging.error(f"   Channel: {channel}, Thread: {thread_ts}, Text: {text[:50]}...")
                    logging.error(f"   Traceback:\n{traceback.format_exc()}")
            
            return success
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
        change_summary: Optional[str] = None,
        team_id: Optional[str] = None,
        bot_id: Optional[str] = None
    ) -> bool:
        """
        Send a notification about a document update
        Also saves the bot response to MongoDB.
        
        Args:
            channel: Slack channel ID
            thread_ts: Thread timestamp to reply to
            doc_id: Google Docs document ID
            doc_name: Document name
            message_count: Number of messages processed
            success: Whether the update was successful
            error_message: Error message if update failed
            change_summary: Optional summary of changes made to the document
            team_id: Optional team ID for saving the message
            bot_id: Optional bot user ID for saving the message
            
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

        return self.send_reply(channel, thread_ts, text, team_id=team_id, bot_id=bot_id)
    
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
