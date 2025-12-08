"""
Core Module
Orchestrates the update process by combining Intelligence and Storage modules.
"""

from typing import Dict, Any, List

# Import repositories
from repository.slack_repository import get_slack_repository

# Import local modules
from services.updater import storage
from services.updater import intelligence

slack_repo = get_slack_repository()


def process_document_update(
    doc_id: str, messages: List[Dict[str, Any]], trigger_type: str = "agent_command"
) -> Dict[str, Any]:
    """
    Process document update immediately with the given messages
    """
    result = {
        "success": False,
        "doc_id": doc_id,
        "doc_name": None,
        "message_count": len(messages),
        "version_id": None,
        "change_summary": None,
        "error": None,
    }

    if not messages:
        result["error"] = "No messages provided"
        print(f"No messages provided for document {doc_id}")
        return result

    # Get document name from metadata
    try:
        metadata = storage.get_document_metadata(doc_id)
        result["doc_name"] = (
            metadata.get("name", "Unknown Document") if metadata else "Unknown Document"
        )
    except Exception as e:
        result["doc_name"] = "Unknown Document"
        print(f"Warning: Could not get document metadata: {e}")

    # Get current document content
    try:
        old_content = storage.get_current_content(doc_id)
    except Exception as e:
        result["error"] = f"Error reading document: {str(e)}"
        print(f"Error reading document {doc_id}: {e}")
        return result

    # Generate new content
    try:
        new_content = intelligence.generate_document_update(old_content, messages)
    except Exception as e:
        result["error"] = f"Error generating update: {str(e)}"
        print(f"Error generating update for {doc_id}: {e}")
        return result

    # Generate change summary
    try:
        result["change_summary"] = intelligence.generate_change_summary(
            old_content, new_content, messages
        )
    except Exception as e:
        print(f"Warning: Error generating change summary: {e}")
        result["change_summary"] = "Document updated successfully."

    # Calculate metadata
    char_count = sum(len(msg.get("text", "")) for msg in messages)

    # Save version before update
    version_metadata = {
        "char_count": char_count,
        "message_count": len(messages),
        "trigger_type": trigger_type,
    }
    try:
        version_id = storage.save_document_version(
            doc_id, old_content, version_metadata
        )
        result["version_id"] = version_id
    except Exception as e:
        result["error"] = f"Error saving version: {str(e)}"
        print(f"Error saving version for {doc_id}: {e}")
        return result

    # Update Google Doc
    try:
        storage.update_drive_content(doc_id, old_content, new_content)
    except Exception as e:
        result["error"] = f"Error updating Google Doc: {str(e)}"
        print(f"Error updating Google Doc {doc_id}: {e}")
        return result

    # Update vector database
    try:
        storage.update_vector_db(doc_id, new_content)
    except Exception as e:
        # Don't fail the update if vector DB fails, just log it
        print(f"Warning: Error updating vector DB for {doc_id}: {e}")

    result["success"] = True
    print(
        f"✓ Successfully updated document {doc_id} (version {version_id}) with {len(messages)} message(s)"
    )
    return result


def ingest_messages(payload: Dict[str, Any]):
    """
    Process messages from Redis queue as a log.
    """
    team_id = payload.get("team_id")
    threads = payload.get("threads", [])
    channel = payload.get("channel")
    thread_ts = payload.get("thread_ts")

    if not threads:
        return

    # Collect all messages from all threads
    all_messages = []
    for thread_batch in threads:
        all_messages.extend(thread_batch.get("messages", []))

    if not all_messages:
        print(f"⏭️  No messages to process, flushing")
        return

    # Chunk messages
    message_chunks = intelligence.chunk_messages(all_messages)

    if not message_chunks:
        print(f"⏭️  No valid chunks from {len(all_messages)} messages, flushing")
        return

    # Process the most recent chunk
    latest_chunk = message_chunks[-1]

    # Extract knowledge from the chunk
    knowledge_result = intelligence.extract_knowledge_from_chunk(latest_chunk)

    if not knowledge_result.get("has_new_information"):
        print(
            f"⏭️  No new knowledge extracted from {len(latest_chunk)} messages, flushing"
        )
        return

    knowledge = knowledge_result.get("knowledge", "")
    print(
        f"📝 Extracted knowledge from {len(latest_chunk)} messages: {knowledge[:100]}..."
    )

    # Determine if a document needs updating
    update_decision = intelligence.determine_if_document_needs_update(
        knowledge=knowledge, messages=latest_chunk, team_id=team_id
    )

    if not update_decision:
        print(f"⏭️  No document update needed, flushing")
        return

    # Document needs update - process it
    doc_id = update_decision["doc_id"]
    confidence = update_decision["confidence"]

    print(f"📄 Document {doc_id} needs update (confidence: {confidence:.2f})")

    # Process the document update
    result = process_document_update(
        doc_id=doc_id, messages=latest_chunk, trigger_type="redis_queue"
    )

    # Send Slack notification if channel and thread_ts are available
    if channel and thread_ts:
        slack_repo.send_document_update_notification(
            channel=channel,
            thread_ts=thread_ts,
            doc_id=result["doc_id"],
            doc_name=result["doc_name"] or "Unknown Document",
            message_count=result["message_count"],
            success=result["success"],
            error_message=result.get("error"),
            change_summary=result.get("change_summary"),
        )

    if result["success"]:
        print(f"✓ Successfully updated document {doc_id} based on queue log")
    else:
        print(f"✗ Failed to update document {doc_id}: {result.get('error')}")
