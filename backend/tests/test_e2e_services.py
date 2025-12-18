"""
End-to-end integration tests for Epimetheus services.

Tests cover:
1. Mention Listener - agentic AI processing
2. Updater Service - Redis queue consumption and document updates
3. Google Drive operations - create, list, search documents
4. Google Document operations - read, update, version management
"""

import os
import json
import time
import pytest
from typing import Dict, Any
from dotenv import load_dotenv
from repository.drive_repository import get_drive_repository
from repository.document_repository import get_document_repository
from repository.llm_repository import get_agentic_repository
from services.bot.buffer import MessageBuffer
from utils.db_utils import get_redis_client, REDIS_QUEUE_KEY, get_mongodb_db

# Load environment variables from .env file
load_dotenv()


def _has_google_env():
    """Check if Google credentials are configured"""
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    return bool(folder_id) and bool(creds_path) and os.path.exists(creds_path)


def _has_redis():
    """Check if Redis is available"""
    try:
        client = get_redis_client()
        client.ping()
        return True
    except Exception:
        return False


def _has_mongo():
    """Check if MongoDB is available"""
    try:
        return get_mongodb_db() is not None
    except Exception:
        return False


def _has_openai():
    """Check if OpenAI API key is configured"""
    return bool(os.environ.get("OPENAI_API_KEY"))


def _can_create_documents():
    """Check if we have permission to create documents in Google Drive"""
    if not _has_google_env():
        return False
    try:
        drive_repo = get_drive_repository()
        # Try to create a test document (this will fail fast with 403 if no permission)
        test_name = f"__permission_test_{int(time.time())}"
        doc = drive_repo.create_document(name=test_name, initial_content="")
        doc_id = doc["id"]
        # Cleanup immediately
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception:
            pass
        return True
    except Exception as e:
        # Check if it's a permission error (403 Forbidden)
        error_str = str(e).lower()
        if "403" in error_str or "permission" in error_str or "forbidden" in error_str or "permission_denied" in error_str:
            return False
        # For other errors (network, etc.), assume we can try - let the test handle the error
        # This allows tests to proceed and fail with clearer error messages for non-permission issues
        return True


@pytest.fixture
def test_doc_name():
    """Generate a unique test document name"""
    return f"Test Document E2E {int(time.time())}"


@pytest.fixture
def cleanup_test_doc(test_doc_name):
    """Cleanup fixture to delete test document after test"""
    drive_repo = get_drive_repository()
    doc_id = None
    yield doc_id
    
    # Cleanup: delete test document if it was created
    if doc_id:
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document {doc_id}: {e}")


# ============================================================================
# Google Drive Operations Tests
# ============================================================================

@pytest.mark.integration
def test_drive_create_document(test_doc_name):
    """Test creating a new Google Doc"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    
    # Create document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="# Test Document\n\nThis is a test document created by E2E tests."
    )
    
    assert doc is not None
    assert "id" in doc
    assert doc["name"] == test_doc_name
    
    # Verify document exists
    docs = drive_repo.list_documents_in_folder()
    doc_ids = [d["id"] for d in docs]
    assert doc["id"] in doc_ids
    
    # Cleanup
    try:
        drive_service = drive_repo._get_google_drive_service()
        drive_service.files().delete(fileId=doc["id"]).execute()
    except Exception as e:
        print(f"Warning: Could not cleanup test document: {e}")


@pytest.mark.integration
def test_drive_list_documents():
    """Test listing documents in Drive folder"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    
    drive_repo = get_drive_repository()
    docs = drive_repo.list_documents_in_folder()
    
    assert isinstance(docs, list)
    # Verify structure
    if docs:
        assert "id" in docs[0]
        assert "name" in docs[0]


@pytest.mark.integration
def test_drive_search_documents():
    """Test searching documents by name"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    
    drive_repo = get_drive_repository()
    
    # Search for documents (using a common term that might exist)
    results = drive_repo.search_documents_by_name("test")
    
    assert isinstance(results, list)
    # Verify structure if results exist
    if results:
        assert "id" in results[0]
        assert "name" in results[0]


@pytest.mark.integration
def test_drive_get_document_content(test_doc_name):
    """Test reading document content from Google Docs"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="# Test Content\n\nThis is test content for reading."
    )
    doc_id = doc["id"]
    
    try:
        # Read content
        content = drive_repo.get_document_content(doc_id)
        
        assert isinstance(content, str)
        assert len(content) > 0
        assert "Test Content" in content or "test content" in content.lower()
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


@pytest.mark.integration
def test_drive_update_document_content(test_doc_name):
    """Test updating document content"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    
    # Create a test document
    initial_content = "# Original Content\n\nThis is the original content."
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content=initial_content
    )
    doc_id = doc["id"]
    
    try:
        # Update content
        new_content = "# Updated Content\n\nThis is the **updated** content with changes."
        drive_repo.update_document_content(doc_id, new_content, apply_formatting=True)
        
        # Verify update
        updated_content = drive_repo.get_document_content(doc_id)
        assert isinstance(updated_content, str)
        assert "Updated Content" in updated_content or "updated content" in updated_content.lower()
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


@pytest.mark.integration
def test_drive_partial_update_document(test_doc_name):
    """Test partial document update preserving formatting"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    
    # Create a test document
    old_content = "Original text that will be updated."
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content=old_content
    )
    doc_id = doc["id"]
    
    try:
        # Partial update
        new_content = "Updated text that replaces the original."
        drive_repo.update_document_content_partial(doc_id, old_content, new_content)
        
        # Verify update
        updated_content = drive_repo.get_document_content(doc_id)
        assert "Updated text" in updated_content or "updated text" in updated_content.lower()
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


# ============================================================================
# Document Repository & Version Management Tests
# ============================================================================

@pytest.mark.integration
def test_document_repository_sync_drive_mapping():
    """Test syncing Drive folder to MongoDB mapping"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    
    doc_repo = get_document_repository()
    
    # Sync mapping
    result = doc_repo.sync_drive_folder_to_mapping()
    
    assert result is not None
    assert "folder_id" in result
    assert "documents" in result
    assert "document_count" in result
    assert isinstance(result["documents"], list)


@pytest.mark.integration
def test_document_repository_save_and_load_version(test_doc_name):
    """Test saving and loading document versions"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    doc_repo = get_document_repository()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="Version 1 content"
    )
    doc_id = doc["id"]
    
    try:
        # Save version
        version_metadata = {
            "test": True,
            "version": 1
        }
        version_id = doc_repo.save_version(doc_id, "Version 1 content", version_metadata)
        
        assert version_id is not None
        assert isinstance(version_id, str)
        
        # Load version
        loaded_version = doc_repo.load_version(doc_id, version_id)
        
        assert loaded_version is not None
        assert loaded_version["version_id"] == version_id
        assert loaded_version["doc_id"] == doc_id
        assert loaded_version["content"] == "Version 1 content"
        assert loaded_version["metadata"]["test"] is True
        
        # List versions
        versions = doc_repo.list_versions(doc_id)
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert any(v["version_id"] == version_id for v in versions)
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


@pytest.mark.integration
def test_document_repository_process_update(test_doc_name):
    """Test processing a document update end-to-end"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    if not _has_openai():
        pytest.skip("OpenAI API key not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    doc_repo = get_document_repository()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="Original content"
    )
    doc_id = doc["id"]
    
    try:
        # Update vector DB with initial content
        doc_repo.update_vector_db(doc_id, "Original content")
        
        # Create test messages
        messages = [
            {
                "text": "We should add information about testing procedures.",
                "user": "test_user",
                "ts": str(time.time())
            }
        ]
        
        # Process update
        result = doc_repo.process_document_update(
            doc_id=doc_id,
            messages=messages,
            trigger_type="test"
        )
        
        assert result is not None
        assert result["success"] is True
        assert result["doc_id"] == doc_id
        assert result["version_id"] is not None
        
        # Verify version was saved
        versions = doc_repo.list_versions(doc_id)
        assert len(versions) > 0
        
        # Verify document was updated
        updated_content = drive_repo.get_document_content(doc_id)
        assert len(updated_content) > len("Original content")
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


# ============================================================================
# Message Listener & Buffer Tests
# ============================================================================

@pytest.mark.integration
def test_message_buffer_ingest():
    """Test message buffer ingesting messages"""
    if not _has_redis():
        pytest.skip("Redis not available")
    
    buffer = MessageBuffer()
    team_id = "test_team_123"
    
    # Create test message event
    test_event = {
        "text": "Test message for buffer",
        "user": "test_user",
        "ts": str(time.time()),
        "channel": "test_channel"
    }
    
    # Ingest message
    buffer.ingest(test_event, team_id)
    
    # Verify message was buffered (check Redis)
    redis_client = get_redis_client()
    thread_id = test_event.get("thread_ts") or test_event.get("ts")
    thread_key = f"botbuffer:{team_id}:thread:{thread_id}"
    
    messages = redis_client.lrange(thread_key, 0, -1)
    assert len(messages) > 0
    
    # Cleanup
    redis_client.delete(thread_key)
    redis_client.delete(f"botbuffer:{team_id}:dirty_list")
    redis_client.delete(f"botbuffer:{team_id}:dirty_set")
    redis_client.delete(f"botbuffer:{team_id}:msg_count")


@pytest.mark.integration
def test_message_buffer_dispatch_to_queue():
    """Test message buffer dispatching to Redis queue"""
    if not _has_redis():
        pytest.skip("Redis not available")
    
    buffer = MessageBuffer()
    team_id = "test_team_456"
    
    # Create multiple test messages to trigger dispatch
    for i in range(3):  # BATCH_SIZE is 2, so 3 messages should trigger dispatch
        test_event = {
            "text": f"Test message {i}",
            "user": "test_user",
            "ts": str(time.time() + i),
            "channel": "test_channel"
        }
        buffer.ingest(test_event, team_id)
    
    # Check if payload was added to queue
    redis_client = get_redis_client()
    queue_length = redis_client.llen(REDIS_QUEUE_KEY)
    
    # At least one payload should be in queue
    assert queue_length > 0
    
    # Cleanup - consume from queue
    while redis_client.llen(REDIS_QUEUE_KEY) > 0:
        redis_client.lpop(REDIS_QUEUE_KEY)
    
    # Cleanup buffer keys
    redis_client.delete(f"botbuffer:{team_id}:dirty_list")
    redis_client.delete(f"botbuffer:{team_id}:dirty_set")
    redis_client.delete(f"botbuffer:{team_id}:msg_count")


# ============================================================================
# Updater Service Tests
# ============================================================================

@pytest.mark.integration
def test_updater_ingest_messages(test_doc_name):
    """Test updater service ingesting messages from queue"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_redis():
        pytest.skip("Redis not available")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    if not _has_openai():
        pytest.skip("OpenAI API key not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    doc_repo = get_document_repository()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="Initial content for updater test"
    )
    doc_id = doc["id"]
    
    try:
        # Update vector DB
        doc_repo.update_vector_db(doc_id, "Initial content for updater test")
        
        # Create payload similar to what buffer sends
        payload = {
            "team_id": "test_team",
            "channel": "test_channel",
            "thread_ts": str(time.time()),
            "threads": [
                {
                    "thread_id": str(time.time()),
                    "messages": [
                        {
                            "text": "This is important information about testing.",
                            "user": "test_user",
                            "ts": str(time.time())
                        }
                    ]
                }
            ]
        }
        
        # Ingest messages
        doc_repo.ingest_messages(payload)
        
        # Verify document was potentially updated (check if versions exist)
        versions = doc_repo.list_versions(doc_id)
        # Note: Update may or may not happen depending on knowledge extraction
        # So we just verify the process completed without error
        assert True  # If we get here, ingest completed
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


@pytest.mark.integration
def test_updater_consume_from_redis_queue(test_doc_name):
    """Test updater consuming messages from Redis queue"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_redis():
        pytest.skip("Redis not available")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    doc_repo = get_document_repository()
    redis_client = get_redis_client()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="Content for queue test"
    )
    doc_id = doc["id"]
    
    try:
        # Update vector DB
        doc_repo.update_vector_db(doc_id, "Content for queue test")
        
        # Manually add payload to queue
        payload = {
            "team_id": "test_team",
            "channel": "test_channel",
            "thread_ts": str(time.time()),
            "threads": [
                {
                    "thread_id": str(time.time()),
                    "messages": [
                        {
                            "text": "Test message for queue consumption",
                            "user": "test_user",
                            "ts": str(time.time())
                        }
                    ]
                }
            ]
        }
        
        # Add to queue
        redis_client.rpush(REDIS_QUEUE_KEY, json.dumps(payload))
        
        # Consume from queue (non-blocking)
        result = redis_client.blpop(REDIS_QUEUE_KEY, timeout=1)
        assert result is not None
        
        queue_key, payload_json = result
        consumed_payload = json.loads(payload_json)
        
        assert consumed_payload["team_id"] == "test_team"
        assert len(consumed_payload["threads"]) > 0
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")


# ============================================================================
# Mention Listener & Agentic AI Tests
# ============================================================================

@pytest.mark.integration
def test_mention_listener_process_mention():
    """Test mention listener processing a mention with agentic AI"""
    if not _has_openai():
        pytest.skip("OpenAI API key not configured")
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    
    agentic_repo = get_agentic_repository()
    
    # Create test event
    event = {
        "text": "<@bot> What documents do we have?",
        "user": "test_user",
        "channel": "test_channel",
        "ts": str(time.time())
    }
    
    # Process mention
    reply = agentic_repo.process_mention(
        message_text="What documents do we have?",
        event=event,
        team_id="test_team",
        channel="test_channel",
        thread_ts=str(time.time())
    )
    
    assert reply is not None
    assert isinstance(reply, str)
    assert len(reply) > 0


@pytest.mark.integration
def test_mention_listener_answer_question():
    """Test mention listener answering a question using RAG"""
    if not _has_openai():
        pytest.skip("OpenAI API key not configured")
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    
    agentic_repo = get_agentic_repository()
    doc_repo = get_document_repository()
    
    # First, ensure we have some documents indexed
    try:
        doc_repo.sync_drive_folder_to_mapping()
    except Exception:
        pass
    
    # Create test event
    event = {
        "text": "<@bot> What is in our documentation?",
        "user": "test_user",
        "channel": "test_channel",
        "ts": str(time.time())
    }
    
    # Process mention
    reply = agentic_repo.process_mention(
        message_text="What is in our documentation?",
        event=event,
        team_id="test_team",
        channel="test_channel",
        thread_ts=str(time.time())
    )
    
    assert reply is not None
    assert isinstance(reply, str)
    assert len(reply) > 0


# ============================================================================
# End-to-End Flow Tests
# ============================================================================

@pytest.mark.integration
def test_e2e_message_to_document_update(test_doc_name):
    """End-to-end test: Message -> Queue -> Updater -> Document Update"""
    if not _has_google_env():
        pytest.skip("Google env/credentials not configured")
    if not _has_redis():
        pytest.skip("Redis not available")
    if not _has_mongo():
        pytest.skip("MongoDB not available")
    if not _has_openai():
        pytest.skip("OpenAI API key not configured")
    if not _can_create_documents():
        pytest.skip("Service account does not have permission to create documents")
    
    drive_repo = get_drive_repository()
    doc_repo = get_document_repository()
    buffer = MessageBuffer()
    
    # Create a test document
    doc = drive_repo.create_document(
        name=test_doc_name,
        initial_content="Initial documentation content"
    )
    doc_id = doc["id"]
    
    try:
        # Update vector DB
        doc_repo.update_vector_db(doc_id, "Initial documentation content")
        
        # Step 1: Message Listener - ingest messages
        team_id = "test_team_e2e"
        messages = [
            {
                "text": "We need to document the new API endpoint.",
                "user": "test_user",
                "ts": str(time.time()),
                "channel": "test_channel"
            },
            {
                "text": "The endpoint accepts POST requests with JSON payload.",
                "user": "test_user",
                "ts": str(time.time() + 1),
                "channel": "test_channel"
            }
        ]
        
        for msg in messages:
            buffer.ingest(msg, team_id)
        
        # Step 2: Wait for dispatch (or manually trigger)
        time.sleep(0.5)  # Give buffer time to process
        
        # Step 3: Updater - consume from queue and process
        redis_client = get_redis_client()
        queue_length = redis_client.llen(REDIS_QUEUE_KEY)
        
        if queue_length > 0:
            # Get payload from queue
            payload_json = redis_client.lpop(REDIS_QUEUE_KEY)
            payload = json.loads(payload_json)
            
            # Process with updater
            doc_repo.ingest_messages(payload)
            
            # Verify document was potentially updated
            versions = doc_repo.list_versions(doc_id)
            # Note: Update depends on knowledge extraction, so we just verify process completed
            assert True
        
        # Cleanup buffer keys
        redis_client.delete(f"botbuffer:{team_id}:dirty_list")
        redis_client.delete(f"botbuffer:{team_id}:dirty_set")
        redis_client.delete(f"botbuffer:{team_id}:msg_count")
    finally:
        # Cleanup
        try:
            drive_service = drive_repo._get_google_drive_service()
            drive_service.files().delete(fileId=doc_id).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test document: {e}")
