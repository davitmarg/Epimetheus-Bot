"""
The Archivist (Updater Service)

This service consumes message batches from Redis, stacks them on existing documents,
and generates new document versions when character thresholds are reached.

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
    get_chroma_collection
)

# Import repositories
from repository.drive_repository import (
    get_document_content,
    update_document_content,
    create_document
)
from repository.document_repository import get_document_repository
from repository.document_repository import get_documents_from_mapping

load_dotenv()

# Configuration
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
CHAR_THRESHOLD = int(os.environ.get("CHAR_THRESHOLD", 10000))
REDIS_QUEUE_KEY = "epimetheus:updater_queue"  # Queue for batches to be processed

# Initialize clients
openai_client = OpenAI(
    base_url=os.environ.get("OPENAI_BASE_URL", None),
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# Initialize database connections using utils
redis_client = get_redis_client()
collection = get_chroma_collection()

# Initialize document repository
document_repo = get_document_repository()

# In-memory state for character tracking per document
document_stacks: Dict[str, Dict[str, Any]] = {}  # doc_id -> {char_count, messages, last_version}


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
    if collection and messages:
        # Combine all message text
        combined_text = " ".join([msg.get('text', '') for msg in messages])
        
        if combined_text.strip():
            try:
                # Search for similar content in vector DB
                results = collection.query(
                    query_texts=[combined_text],
                    n_results=3
                )
                
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
            docs = get_documents_from_mapping(GOOGLE_DRIVE_FOLDER_ID)
            if docs:
                # For now, return all documents (could be filtered by relevance)
                return [doc['id'] for doc in docs]
        except Exception as e:
            print(f"Warning: Could not list documents in folder: {e}")
    
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
            print(f"Error creating default document: {e}")
    
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
    if not collection:
        print("Warning: ChromaDB collection not available, skipping vector update")
        return

    chunks = chunk_document(content)
    
    # Delete old chunks for this document
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        # Collection might not exist or have no chunks yet
        pass
    
    # Add new chunks
    if chunks:
        try:
            collection.add(
                documents=chunks,
                ids=[f"{doc_id}_chunk_{i}" for i in range(len(chunks))],
                metadatas=[{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]
            )
        except Exception as e:
            print(f"Error updating vector DB: {e}")


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
            model="gpt-4",
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


def process_document_update(doc_id: str, force: bool = False):
    """Process document update if threshold reached or forced"""
    if doc_id not in document_stacks:
        return
    
    stack = document_stacks[doc_id]
    char_count = stack['char_count']
    
    if not force and char_count < CHAR_THRESHOLD:
        return
    
    # Get current document content
    try:
        old_content = get_document_content(doc_id)
    except Exception as e:
        print(f"Error reading document {doc_id}: {e}")
        return
    
    # Generate new content
    try:
        new_content = generate_document_update(old_content, stack['messages'])
    except Exception as e:
        print(f"Error generating update for {doc_id}: {e}")
        return
    
    # Save version before update
    version_metadata = {
        "char_count": char_count,
        "message_count": len(stack['messages']),
        "trigger_type": "manual" if force else "threshold"
    }
    version_id = save_document_version(doc_id, old_content, version_metadata)
    
    # Update Google Doc
    try:
        update_document_content(doc_id, new_content)
    except Exception as e:
        print(f"Error updating Google Doc {doc_id}: {e}")
        return
    
    # Update vector database
    try:
        update_vector_db(doc_id, new_content)
    except Exception as e:
        print(f"Error updating vector DB for {doc_id}: {e}")
    
    # Reset stack
    document_stacks[doc_id] = {
        'char_count': 0,
        'messages': [],
        'last_version': version_id
    }
    
    print(f"✓ Successfully updated document {doc_id} (version {version_id})")


def ingest_messages(payload: Dict[str, Any]):
    """Process message batches from Redis queue"""
    team_id = payload.get('team_id')
    threads = payload.get('threads', [])
    
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
        return
    
    # Distribute messages to target documents
    # For now, distribute evenly across documents
    # (Could be enhanced with smarter routing)
    messages_per_doc = len(all_messages) // len(target_doc_ids)
    remainder = len(all_messages) % len(target_doc_ids)
    
    message_idx = 0
    for i, doc_id in enumerate(target_doc_ids):
        # Initialize stack if needed
        if doc_id not in document_stacks:
            document_stacks[doc_id] = {
                'char_count': 0,
                'messages': [],
                'last_version': None
            }
        
        # Assign messages to this document
        doc_message_count = messages_per_doc + (1 if i < remainder else 0)
        doc_messages = all_messages[message_idx:message_idx + doc_message_count]
        message_idx += doc_message_count
        
        # Add messages to stack
        for message in doc_messages:
            text = message.get('text', '')
            char_count = len(text)
            
            document_stacks[doc_id]['char_count'] += char_count
            document_stacks[doc_id]['messages'].append(message)
        
        # Check if threshold reached for this document
        stack = document_stacks[doc_id]
        if stack['char_count'] >= CHAR_THRESHOLD:
            process_document_update(doc_id, force=False)
        
        print(
            f"Processed batch for doc {doc_id}: "
            f"{len(doc_messages)} messages, "
            f"char_count: {stack['char_count']}/{CHAR_THRESHOLD}"
        )


def consume_from_redis():
    """Consume batches from Redis queue and process them"""
    print(f"Starting Redis consumer on queue: {REDIS_QUEUE_KEY}")
    
    while True:
        try:
            # Blocking pop from queue (wait up to 1 second)
            result = redis_client.blpop(REDIS_QUEUE_KEY, timeout=1)
            print(f"Received result: {result}")
            if result:
                _, payload_json = result
                payload = json.loads(payload_json)
                print(f"Received payload: {payload}")
                ingest_messages(payload)
            else:
                # No message available, continue polling
                time.sleep(0.1)
                
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON payload: {e}")
        except Exception as e:
            error_str = str(e).lower()
            if "connection" in error_str or "connectionerror" in error_str:
                print(f"Redis connection error: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"Error processing batch: {e}")
                time.sleep(1)


def start_updater_service():
    """Start the updater service consumer"""
    print("Starting Epimetheus Updater Service (Redis Consumer)...")
    consume_from_redis()
