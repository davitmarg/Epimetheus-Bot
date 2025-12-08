"""
Updater Service

Checks last x messages from queue and decides every x messages if knowledge base updates are needed.
Processes messages from Redis queue:
1. Chunks messages (last x messages)
2. Extracts knowledge from chunks
3. Determines if document needs update
4. If update needed: processes update
5. If not needed: flushes and continues

Also supports direct function calls for immediate processing (mentions, agent tools).
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Import database utilities
from utils.db_utils import get_redis_client, REDIS_QUEUE_KEY
from utils.message_utils import extract_doc_id_from_chunk_id

# Import repositories
from repository.drive_repository import get_drive_repository
from repository.document_repository import get_document_repository
from repository.slack_repository import get_slack_repository
from repository.llm_repository import get_llm_repository

load_dotenv()

GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

redis_client = get_redis_client()
document_repo = get_document_repository()
drive_repo = get_drive_repository()
llm_repo = get_llm_repository()
slack_repo = get_slack_repository()

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
                            doc_id = extract_doc_id_from_chunk_id(chunk_id)
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
            default_doc = drive_repo.create_document(
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
    """Use LLM repository to generate updated document content"""
    try:
        return llm_repo.generate_document_update(
            old_content=old_content,
            new_messages=new_messages,
            temperature=0.3,
            max_tokens=4000
        )
    except Exception as e:
        raise Exception(f"Error generating document update: {str(e)}")


def generate_change_summary(old_content: str, new_content: str, new_messages: List[Dict[str, Any]]) -> str:
    """Use LLM repository to generate a concise summary of document changes"""
    try:
        return llm_repo.generate_change_summary(
            old_content=old_content,
            new_content=new_content,
            new_messages=new_messages,
            temperature=0.5,
            max_tokens=200
        )
    except Exception as e:
        print(f"Warning: Error generating change summary: {str(e)}")
        return "Document updated successfully."


def chunk_messages(messages: List[Dict[str, Any]], chunk_size: int = None) -> List[List[Dict[str, Any]]]:
    """
    Chunk messages into groups of last N messages.
    
    Args:
        messages: List of message dictionaries
        chunk_size: Number of messages per chunk (defaults to MESSAGE_CHUNK_SIZE env var or 10)
        
    Returns:
        List of message chunks (each chunk is a list of messages)
    """
    if chunk_size is None:
        chunk_size = int(os.environ.get("MESSAGE_CHUNK_SIZE", "10"))
    
    if not messages:
        return []
    
    # Filter out bot messages
    user_messages = [msg for msg in messages if not msg.get("bot_id")]
    
    if not user_messages:
        return []
    
    # Sort messages by timestamp (oldest first)
    sorted_messages = sorted(user_messages, key=lambda x: float(x.get("ts", 0)))
    
    # Create chunks of last N messages
    chunks = []
    for i in range(len(sorted_messages)):
        chunk = sorted_messages[max(0, i - chunk_size + 1):i + 1]
        if len(chunk) >= 2:  # Only include chunks with at least 2 messages
            chunks.append(chunk)
    
    # Return the most recent chunk if we have messages
    if sorted_messages:
        recent_chunk = sorted_messages[-chunk_size:] if len(sorted_messages) >= chunk_size else sorted_messages
        return [recent_chunk]
    
    return []


def extract_knowledge_from_chunk(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract knowledge from a chunk of messages using LLM.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Dictionary with extracted knowledge and metadata
    """
    if not messages:
        return {
            "knowledge": "",
            "has_new_information": False,
            "relevance_score": 0.0
        }
    
    # Combine message texts
    message_texts = []
    for msg in messages:
        text = msg.get("text", "")
        user = msg.get("user", "unknown")
        timestamp = msg.get("ts", "")
        message_texts.append(f"[{timestamp}] {user}: {text}")
    
    combined_text = "\n".join(message_texts)
    
    # Use LLM repository to extract knowledge
    try:
        knowledge = llm_repo.extract_knowledge(
            conversation_text=combined_text,
            temperature=0.3,
            max_tokens=500
        )
        
        # Check if there's new information
        has_new_information = knowledge.upper() != "NO_NEW_INFORMATION" and len(knowledge) > 20
        
        # Calculate relevance score based on knowledge length and content
        relevance_score = 0.0
        if has_new_information:
            # Simple heuristic: longer, more detailed knowledge = higher relevance
            relevance_score = min(1.0, len(knowledge) / 500.0)
        
        return {
            "knowledge": knowledge,
            "has_new_information": has_new_information,
            "relevance_score": relevance_score,
            "message_count": len(messages)
        }
        
    except Exception as e:
        print(f"Error extracting knowledge: {e}")
        return {
            "knowledge": "",
            "has_new_information": False,
            "relevance_score": 0.0,
            "error": str(e)
        }


def determine_if_document_needs_update(
    knowledge: str,
    messages: List[Dict[str, Any]],
    team_id: str
) -> Optional[Dict[str, Any]]:
    """
    Determine if a document needs updating based on extracted knowledge.
    Uses RAG to find relevant documents.
    
    Args:
        knowledge: Extracted knowledge string
        messages: Original messages that generated the knowledge
        team_id: Slack team ID
        
    Returns:
        Dictionary with doc_id and confidence, or None if no update needed
    """
    knowledge_extraction_threshold = float(os.environ.get("KNOWLEDGE_EXTRACTION_THRESHOLD", "0.7"))
    
    if not knowledge or len(knowledge.strip()) < 20:
        return None
    
    try:
        # Use vector search to find relevant documents
        search_results = document_repo.search_similar_documents(knowledge, n_results=3)
        
        if not search_results or not search_results.get('ids') or not search_results['ids'][0]:
            # No relevant documents found, but knowledge exists
            # Could create a new document or return None
            return None
        
        # Get the most relevant document
        chunk_ids = search_results['ids'][0]
        distances_list = search_results.get('distances', [[]])[0]
        
        if not chunk_ids or not distances_list:
            return None
        
        # Extract doc_id from first chunk
        first_chunk_id = chunk_ids[0]
        doc_id = extract_doc_id_from_chunk_id(first_chunk_id)
        distance = distances_list[0] if len(distances_list) > 0 else 1.0
        
        # Check if relevance is high enough (lower distance = more relevant)
        relevance_threshold = 1.0 - knowledge_extraction_threshold  # Convert threshold to distance
        
        if distance < relevance_threshold:
            return {
                "doc_id": doc_id,
                "confidence": 1.0 - distance,  # Convert distance to confidence
                "distance": distance
            }
        
        return None
        
    except Exception as e:
        print(f"Error determining document update need: {e}")
        return None


def process_document_update(doc_id: str, messages: List[Dict[str, Any]], trigger_type: str = "agent_command") -> Dict[str, Any]:
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
        old_content = drive_repo.get_document_content(doc_id)
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
    
    try:
        drive_repo.update_document_content_partial(doc_id, old_content, new_content)
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
    """
    Process messages from Redis queue as a log.
    
    Works as a log that:
    1. Chunks messages
    2. Extracts knowledge from chunks
    3. Checks if document needs update
    4. If update needed: processes update
    5. If not needed: flushes and continues
    """
    team_id = payload.get('team_id')
    threads = payload.get('threads', [])
    channel = payload.get('channel')
    thread_ts = payload.get('thread_ts')
    
    if not threads:
        return
    
    # Collect all messages from all threads
    all_messages = []
    for thread_batch in threads:
        all_messages.extend(thread_batch.get('messages', []))
    
    if not all_messages:
        print(f"⏭️  No messages to process, flushing")
        return
    
    # Chunk messages
    message_chunks = chunk_messages(all_messages)
    
    if not message_chunks:
        print(f"⏭️  No valid chunks from {len(all_messages)} messages, flushing")
        return
    
    # Process the most recent chunk
    latest_chunk = message_chunks[-1]
    
    # Extract knowledge from the chunk
    knowledge_result = extract_knowledge_from_chunk(latest_chunk)
    
    if not knowledge_result.get("has_new_information"):
        print(f"⏭️  No new knowledge extracted from {len(latest_chunk)} messages, flushing")
        return
    
    knowledge = knowledge_result.get("knowledge", "")
    print(f"📝 Extracted knowledge from {len(latest_chunk)} messages: {knowledge[:100]}...")
    
    # Determine if a document needs updating
    update_decision = determine_if_document_needs_update(
        knowledge=knowledge,
        messages=latest_chunk,
        team_id=team_id
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
        doc_id=doc_id,
        messages=latest_chunk,
        trigger_type="redis_queue"
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
            change_summary=result.get("change_summary")
        )
    
    if result["success"]:
        print(f"✓ Successfully updated document {doc_id} based on queue log")
    else:
        print(f"✗ Failed to update document {doc_id}: {result.get('error')}")


def consume_from_redis():
    """
    Consume messages from Redis queue as a log.
    
    Continuously processes messages from queue, checking chunks for knowledge extraction
    and only updating documents when needed.
    """
    print(f"Starting Redis consumer on queue: {REDIS_QUEUE_KEY}")
    print(f"Update processing uses BOTH direct calls and Redis queue consumption.")
    print(f"Waiting for messages from Redis queue...")
    
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


def start():
    """Start the updater service consumer"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")    
    consume_from_redis()
