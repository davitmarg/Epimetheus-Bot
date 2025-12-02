"""
The Archivist (Updater Service)

This service consumes messages from Redis and immediately processes them,
updating documents with each message.

Supports multiple dynamic documents in a Google Drive folder.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Import database utilities
from utils.db_utils import (
    get_redis_client,
    REDIS_QUEUE_KEY
)

# Import repositories
from repository.drive_repository import (
    get_document_content,
    update_document_content,
    create_document
)
from repository.document_repository import get_document_repository
from repository.slack_repository import send_document_update_notification

load_dotenv()

# Configuration
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

# Initialize OpenAI client (supports OpenRouter)
openai_base_url = os.environ.get("OPENAI_BASE_URL")
openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")

openai_client = OpenAI(
    base_url=openai_base_url,
    api_key=openai_api_key,
)

# Initialize database connections using utils
redis_client = get_redis_client()

# Initialize document repository
document_repo = get_document_repository()


def determine_target_documents(messages: List[Dict[str, Any]], team_id: str) -> List[str]:
    """
    Determine which document(s) should receive these messages.
    
    This function can be customized to route messages to documents based on:
    - Content analysis (using vector search)
    - Channel/topic tags
    - Document metadata/tags
    - Default document selection
    
    Returns a list of document IDs.
    """
    # Strategy 1: Use vector search to find most relevant documents
    if messages:
        # Combine all message text
        combined_text = " ".join([msg.get('text', '') for msg in messages])
        
        if combined_text.strip():
            try:
                # Search for similar content in vector DB
                results = document_repo.search_similar_documents(combined_text, n_results=3)
                
                if results and results.get('ids') and results['ids'][0]:
                    # Extract unique doc_ids from results
                    doc_ids = set()
                    for id_list in results['ids']:
                        for chunk_id in id_list:
                            # Extract doc_id from chunk_id (format: doc_id_chunk_N)
                            doc_id = chunk_id.rsplit('_chunk_', 1)[0]
                            doc_ids.add(doc_id)
                    
                    if doc_ids:
                        return list(doc_ids)
            except Exception as e:
                print(f"Warning: Vector search failed: {e}")
    
    # Strategy 2: Check for explicit document mentions or tags in messages
    # (This could be enhanced with NLP to detect document names)
    
    # Strategy 3: Use documents from Drive folder mapping
    if GOOGLE_DRIVE_FOLDER_ID:
        try:
            # Get documents from mapping or list from folder
            docs = document_repo.get_documents_from_mapping(GOOGLE_DRIVE_FOLDER_ID)
            if docs:
                # For now, return all documents (could be filtered by relevance)
                return [doc['id'] for doc in docs]
        except Exception as e:
            print(f"Drive Warning: Could not list documents in folder: {e}")
    
    # Last resort: create a default document
    if GOOGLE_DRIVE_FOLDER_ID:
        try:
            default_doc = create_document(
                name=f"Team {team_id} Documentation",
                folder_id=GOOGLE_DRIVE_FOLDER_ID,
                initial_content=""
            )
            return [default_doc['id']]
        except Exception as e:
            print(f"Drive Warning: Error creating default document: {e}")
    
    return []


def save_document_version(doc_id: str, content: str, version_metadata: Dict[str, Any]):
    """Save a document version to MongoDB"""
    return document_repo.save_version(doc_id, content, version_metadata)


def load_document_version(doc_id: str, version_id: str) -> Optional[Dict[str, Any]]:
    """Load a document version from MongoDB"""
    return document_repo.load_version(doc_id, version_id)


def list_document_versions(doc_id: str) -> List[Dict[str, Any]]:
    """List all versions for a document from MongoDB"""
    return document_repo.list_versions(doc_id)


def chunk_document(content: str, chunk_size: int = 1000) -> List[str]:
    """Split document into chunks for vector storage"""
    chunks = []
    words = content.split()
    current_chunk = []
    current_size = 0
    
    for word in words:
        word_size = len(word) + 1  # +1 for space
        if current_size + word_size > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_size = len(word)
        else:
            current_chunk.append(word)
            current_size += word_size
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def update_vector_db(doc_id: str, content: str):
    """Update vector database with document chunks"""
    chunks = chunk_document(content)
    
    # Delete old chunks for this document
    document_repo.delete_document_chunks(doc_id)
    
    # Add new chunks
    if chunks:
        document_repo.add_document_chunks(doc_id, chunks)


def generate_document_update(old_content: str, new_messages: List[Dict[str, Any]]) -> str:
    """Use ChatGPT to generate updated document content"""
    if not openai_client:
        raise Exception("OpenAI API key not configured")
    
    # Format messages for context
    message_context = []
    for msg in new_messages:
        user = msg.get('user', 'unknown')
        text = msg.get('text', '')
        timestamp = msg.get('ts', '')
        message_context.append(f"[{timestamp}] {user}: {text}")
    
    messages_text = "\n".join(message_context)
    
    prompt = f"""You are an AI assistant that updates technical documentation based on Slack conversations.

Current Document Content:
{old_content}

New Information from Slack Conversations:
{messages_text}

Please generate an updated version of the document that:
1. Preserves all existing valuable information
2. Integrates the new information from Slack conversations naturally
3. Maintains proper formatting and structure
4. Removes any outdated information that conflicts with the new information
5. Ensures the document is clear, comprehensive, and up-to-date

Return ONLY the updated document content, without any explanations or markdown formatting."""

    try:
        response = openai_client.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "system", "content": "You are a technical documentation expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise Exception(f"Error generating document update: {str(e)}")


def generate_change_summary(old_content: str, new_content: str, new_messages: List[Dict[str, Any]]) -> str:
    """Use ChatGPT to generate a concise summary of document changes"""
    if not openai_client:
        return "Document updated successfully."
    
    # Format messages for context
    message_context = []
    for msg in new_messages:
        user = msg.get('user', 'unknown')
        text = msg.get('text', '')
        message_context.append(f"{user}: {text}")
    
    messages_text = "\n".join(message_context[:5])  # Limit to first 5 messages for summary
    
    prompt = f"""You are an AI assistant that summarizes changes made to technical documentation.

Original Document Content (first 500 chars):
{old_content[:500]}

Updated Document Content (first 500 chars):
{new_content[:500]}

New Information from Slack Conversations:
{messages_text}

Please generate a brief, concise summary (2-3 sentences) describing what changed in the document based on the new information. Focus on:
- What new information was added
- What sections were updated
- Key changes or improvements

Return ONLY the summary text, without any formatting or markdown."""

    try:
        response = openai_client.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "system", "content": "You are a technical documentation expert who writes clear, concise summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Error generating change summary: {str(e)}")
        return "Document updated successfully."


def process_document_update(doc_id: str, messages: List[Dict[str, Any]], trigger_type: str = "automatic") -> Dict[str, Any]:
    """
    Process document update immediately with the given messages
    
    Returns:
        Dict with 'success' (bool), 'doc_id', 'doc_name', 'message_count', 'version_id', 'change_summary', 'error' (optional)
    """
    result = {
        "success": False,
        "doc_id": doc_id,
        "doc_name": None,
        "message_count": len(messages),
        "version_id": None,
        "change_summary": None,
        "error": None
    }
    
    if not messages:
        result["error"] = "No messages provided"
        print(f"No messages provided for document {doc_id}")
        return result
    
    # Get document name from metadata
    try:
        metadata = document_repo.get_metadata(doc_id)
        result["doc_name"] = metadata.get("name", "Unknown Document") if metadata else "Unknown Document"
    except Exception as e:
        result["doc_name"] = "Unknown Document"
        print(f"Warning: Could not get document metadata: {e}")
    
    # Get current document content
    try:
        old_content = get_document_content(doc_id)
    except Exception as e:
        result["error"] = f"Error reading document: {str(e)}"
        print(f"Error reading document {doc_id}: {e}")
        return result
    
    # Generate new content
    try:
        new_content = generate_document_update(old_content, messages)
    except Exception as e:
        result["error"] = f"Error generating update: {str(e)}"
        print(f"Error generating update for {doc_id}: {e}")
        return result
    
    # Generate change summary
    try:
        result["change_summary"] = generate_change_summary(old_content, new_content, messages)
    except Exception as e:
        print(f"Warning: Error generating change summary: {e}")
        result["change_summary"] = "Document updated successfully."
    
    # Calculate metadata
    char_count = sum(len(msg.get('text', '')) for msg in messages)
    
    # Save version before update
    version_metadata = {
        "char_count": char_count,
        "message_count": len(messages),
        "trigger_type": trigger_type
    }
    try:
        version_id = save_document_version(doc_id, old_content, version_metadata)
        result["version_id"] = version_id
    except Exception as e:
        result["error"] = f"Error saving version: {str(e)}"
        print(f"Error saving version for {doc_id}: {e}")
        return result
    
    # Update Google Doc
    try:
        update_document_content(doc_id, new_content)
    except Exception as e:
        result["error"] = f"Error updating Google Doc: {str(e)}"
        print(f"Error updating Google Doc {doc_id}: {e}")
        return result
    
    # Update vector database
    try:
        update_vector_db(doc_id, new_content)
    except Exception as e:
        # Don't fail the update if vector DB fails, just log it
        print(f"Warning: Error updating vector DB for {doc_id}: {e}")
    
    result["success"] = True
    print(f"✓ Successfully updated document {doc_id} (version {version_id}) with {len(messages)} message(s)")
    return result


def ingest_messages(payload: Dict[str, Any]):
    """Process messages from Redis queue immediately"""
    team_id = payload.get('team_id')
    threads = payload.get('threads', [])
    channel = payload.get('channel')  # Channel for Slack notification
    thread_ts = payload.get('thread_ts')  # Thread timestamp for Slack notification
    
    if not threads:
        return
    
    # Collect all messages from all threads
    all_messages = []
    for thread_batch in threads:
        all_messages.extend(thread_batch.get('messages', []))
    
    if not all_messages:
        return
    
    # Determine which document(s) should receive these messages
    target_doc_ids = determine_target_documents(all_messages, team_id)
    
    if not target_doc_ids:
        print("Warning: No target documents found for messages")
        # Send notification about failure if channel/thread available
        if channel and thread_ts:
            send_document_update_notification(
                channel=channel,
                thread_ts=thread_ts,
                doc_id="",
                doc_name="Unknown",
                message_count=len(all_messages),
                success=False,
                error_message="No target documents found for messages"
            )
        return
    
    # Process each message immediately - assign to first target document
    doc_id = target_doc_ids[0]
    
    # Process update immediately with all messages
    result = process_document_update(doc_id, all_messages, trigger_type="automatic")
    
    # Send Slack notification if channel and thread_ts are available
    if channel and thread_ts:
        send_document_update_notification(
            channel=channel,
            thread_ts=thread_ts,
            doc_id=result["doc_id"],
            doc_name=result["doc_name"] or "Unknown Document",
            message_count=result["message_count"],
            success=result["success"],
            error_message=result.get("error"),
            change_summary=result.get("change_summary")
        )
    
    if result["success"]:
        print(f"✓ Processed {len(all_messages)} message(s) for doc {doc_id}")
    else:
        print(f"✗ Failed to process {len(all_messages)} message(s) for doc {doc_id}: {result.get('error')}")


def consume_from_redis():
    """Consume messages from Redis queue pushed by RedisBuffer"""
    print(f"Starting Redis consumer on queue: {REDIS_QUEUE_KEY}")
    print(f"Waiting for batches from RedisBuffer...")
    
    # Verify Redis connection and queue status
    try:
        redis_client.ping()
        queue_length = redis_client.llen(REDIS_QUEUE_KEY)
        print(f"✓ Redis connected. Queue '{REDIS_QUEUE_KEY}' length: {queue_length}")
        if queue_length > 0:
            print(f"  Found {queue_length} message(s) already in queue")
    except Exception as e:
        print(f"✗ Redis connection check failed: {e}")
    
    last_heartbeat = time.time()
    heartbeat_interval = 30  # Print heartbeat every 30 seconds
    
    while True:
        try:
            # Blocking pop from queue (wait up to 1 second)
            # blpop returns (key, value) tuple or None if timeout
            result = redis_client.blpop(REDIS_QUEUE_KEY, timeout=1)
            if result:
                # result is a tuple: (key, value)
                queue_key, payload_json = result
                
                try:
                    payload = json.loads(payload_json)
                    team_id = payload.get('team_id', 'unknown')
                    thread_count = len(payload.get('threads', []))
                    
                    total_messages = sum(len(t.get('messages', [])) for t in payload.get('threads', []))
                    print(f"✓ Received message(s) for team {team_id}: {thread_count} thread(s), {total_messages} message(s)")
                    ingest_messages(payload)
                    print(f"✓ Successfully processed message(s) for team {team_id}")
                    
                except json.JSONDecodeError as e:
                    print(f"✗ Error decoding JSON payload: {e}")
                    print(f"  Raw payload: {payload_json[:200]}...")
                    continue
                except Exception as e:
                    print(f"✗ Error processing batch: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            else:
                # No message available, continue polling
                # Print periodic heartbeat to show service is still running
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    queue_length = redis_client.llen(REDIS_QUEUE_KEY)
                    print(f"⏳ Waiting for messages on queue: {REDIS_QUEUE_KEY} (current length: {queue_length})")
                    last_heartbeat = current_time
                time.sleep(0.1)
                
        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "connectionerror" in error_str:
                print(f"✗ Redis connection error: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                # Try to reconnect
                try:
                    redis_client.ping()
                    print(f"✓ Redis connection restored")
                except:
                    pass
            else:
                print(f"✗ Unexpected error in consume loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)


def start_updater_service():
    """Start the updater service consumer"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")    
    consume_from_redis()
