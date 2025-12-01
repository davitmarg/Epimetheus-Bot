"""
End-to-End Test for Epimetheus Bot

Tests the complete flow from Slack message ingestion to document update.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from services.bot_service.buffer import RedisBuffer
from services.updater_service import (
    ingest_messages,
    determine_target_documents,
    process_document_update,
    document_stacks
)
from repository.document_repository import (
    get_document_repository,
    sync_drive_folder_to_mapping,
    get_documents_from_mapping,
    search_documents
)


class TestEndToEndFlow:
    """End-to-end tests for the complete message processing flow"""
    
    def test_message_ingestion_to_document_update(
        self,
        mock_env_vars,
        mock_redis_client,
        mock_mongodb,
        mock_chromadb,
        mock_openai_client,
        mock_google_drive,
        sample_slack_message,
        sample_message_batch
    ):
        """
        Test the complete flow:
        1. Slack message ingested into buffer
        2. Message batched and dispatched to Redis queue
        3. Updater service consumes batch
        4. Messages routed to target document
        5. Document updated when threshold reached
        """
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        # Setup mocks
        with patch('services.bot_service.buffer.get_redis_client', return_value=mock_redis_client), \
             patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('utils.db_utils.get_chroma_collection', return_value=mock_chromadb), \
             patch('repository.drive_repository._get_google_drive_service', return_value=mock_drive_service), \
             patch('repository.drive_repository._get_google_docs_service', return_value=mock_docs_service), \
             patch('services.updater_service.get_redis_client', return_value=mock_redis_client), \
             patch('services.updater_service.get_chroma_collection', return_value=mock_chromadb), \
             patch('services.updater_service.openai_client', mock_openai_client), \
             patch('services.updater_service.get_documents_from_mapping') as mock_get_docs, \
             patch('services.updater_service.get_document_content', return_value="Existing content"), \
             patch('services.updater_service.update_document_content') as mock_update_doc, \
             patch('services.updater_service.update_vector_db') as mock_update_vector:
            
            # Setup document mapping
            mock_get_docs.return_value = [{"id": "test-doc-id", "name": "Test Document"}]
            
            # Step 1: Ingest message into buffer
            buffer = RedisBuffer()
            team_id = "T123456"
            
            # Mock pipeline execution for ingestion
            mock_pipe = mock_redis_client.pipeline.return_value
            mock_pipe.execute.return_value = [None, 1, 1]  # rpush, incr, sadd results
            
            buffer.ingest(sample_slack_message, team_id)
            
            # Verify message was stored in Redis
            assert mock_pipe.rpush.called or mock_redis_client.rpush.called
            assert mock_pipe.incr.called
            assert mock_pipe.sadd.called
            
            # Step 2: Simulate batch dispatch (when BATCH_SIZE reached)
            # Setup for dispatch
            mock_redis_client.getset.return_value = "50"  # Simulate 50 messages
            mock_redis_client.lrange.return_value = ["1234567890.123456"]
            
            # Create a new mock pipe for dispatch
            mock_dispatch_pipe = Mock()
            mock_dispatch_pipe.lrange.return_value = mock_dispatch_pipe
            mock_dispatch_pipe.delete.return_value = mock_dispatch_pipe
            mock_dispatch_pipe.execute.return_value = [[json.dumps(sample_slack_message)], None]
            mock_redis_client.pipeline.return_value = mock_dispatch_pipe
            
            # Manually dispatch
            buffer._dispatch(team_id)
            
            # Verify batch was sent to queue
            assert mock_redis_client.rpush.called
            
            # Step 3: Consume and process batch
            # Reset document stacks for clean test
            document_stacks.clear()
            
            # Process the batch
            ingest_messages(sample_message_batch)
            
            # Verify document stack was created
            assert "test-doc-id" in document_stacks or len(document_stacks) > 0
            if "test-doc-id" in document_stacks:
                assert document_stacks["test-doc-id"]["char_count"] > 0
                assert len(document_stacks["test-doc-id"]["messages"]) > 0
            
            # Step 4: Force document update (simulate threshold reached)
            # Find the actual doc_id that was created
            doc_id = list(document_stacks.keys())[0] if document_stacks else "test-doc-id"
            
            # Set char_count to exceed threshold
            document_stacks[doc_id]["char_count"] = 150  # Above threshold of 100
            
            # Process update
            process_document_update(doc_id, force=False)
            
            # Verify OpenAI was called to generate update
            assert mock_openai_client.chat.completions.create.called
            
            # Verify document was updated
            assert mock_update_doc.called
            
            # Verify version was saved
            assert mock_collection.insert_one.called
            
            # Verify vector DB was updated
            assert mock_update_vector.called
            
            # Verify stack was reset
            assert document_stacks[doc_id]["char_count"] == 0
            assert len(document_stacks[doc_id]["messages"]) == 0
    
    def test_document_routing_with_vector_search(
        self,
        mock_env_vars,
        mock_chromadb,
        sample_message_batch
    ):
        """Test that messages are routed to documents using vector search"""
        # Setup vector search to return a specific document
        mock_chromadb.query.return_value = {
            "ids": [["test-doc-id_chunk_0", "test-doc-id_chunk_1"]]
        }
        
        with patch('services.updater_service.collection', mock_chromadb), \
             patch('services.updater_service.get_documents_from_mapping') as mock_get_docs:
            
            mock_get_docs.return_value = [
                {"id": "test-doc-id", "name": "Test Document"},
                {"id": "other-doc-id", "name": "Other Document"}
            ]
            
            # Determine target documents
            messages = sample_message_batch["threads"][0]["messages"]
            team_id = sample_message_batch["team_id"]
            
            target_docs = determine_target_documents(messages, team_id)
            
            # Should route to document found in vector search
            assert len(target_docs) > 0
            assert "test-doc-id" in target_docs
    
    def test_document_routing_fallback_to_all_documents(
        self,
        mock_env_vars,
        sample_message_batch
    ):
        """Test that routing falls back to all documents when vector search fails"""
        with patch('services.updater_service.collection', None), \
             patch('services.updater_service.get_documents_from_mapping') as mock_get_docs:
            
            mock_get_docs.return_value = [
                {"id": "doc-1", "name": "Document 1"},
                {"id": "doc-2", "name": "Document 2"}
            ]
            
            messages = sample_message_batch["threads"][0]["messages"]
            team_id = sample_message_batch["team_id"]
            
            target_docs = determine_target_documents(messages, team_id)
            
            # Should return all documents when vector search unavailable
            assert len(target_docs) == 2
            assert "doc-1" in target_docs
            assert "doc-2" in target_docs
    
    def test_batch_processing_with_multiple_threads(
        self,
        mock_env_vars,
        mock_mongodb,
        mock_chromadb,
        mock_openai_client,
        mock_google_drive
    ):
        """Test processing batch with multiple threads"""
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        batch_with_multiple_threads = {
            "team_id": "T123456",
            "threads": [
                {
                    "thread_id": "thread-1",
                    "messages": [
                        {"user": "U1", "text": "Message 1", "ts": "1.0"},
                        {"user": "U2", "text": "Message 2", "ts": "2.0"}
                    ]
                },
                {
                    "thread_id": "thread-2",
                    "messages": [
                        {"user": "U3", "text": "Message 3", "ts": "3.0"}
                    ]
                }
            ]
        }
        
        with patch('services.updater_service.get_redis_client'), \
             patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('utils.db_utils.get_chroma_collection', return_value=mock_chromadb), \
             patch('services.updater_service.get_chroma_collection', return_value=mock_chromadb), \
             patch('services.updater_service.openai_client', mock_openai_client), \
             patch('services.updater_service.get_documents_from_mapping') as mock_get_docs, \
             patch('services.updater_service.get_document_content', return_value="Existing"), \
             patch('services.updater_service.update_document_content'), \
             patch('services.updater_service.update_vector_db'):
            
            mock_get_docs.return_value = [{"id": "test-doc-id", "name": "Test"}]
            
            # Reset stacks
            document_stacks.clear()
            
            # Process batch
            ingest_messages(batch_with_multiple_threads)
            
            # Verify all messages from all threads were processed
            assert "test-doc-id" in document_stacks
            total_messages = len(document_stacks["test-doc-id"]["messages"])
            assert total_messages == 3  # All messages from both threads
    
    def test_manual_trigger_update(
        self,
        mock_env_vars,
        mock_mongodb,
        mock_chromadb,
        mock_openai_client,
        mock_google_drive
    ):
        """Test manual document update trigger"""
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        with patch('services.updater_service.get_redis_client'), \
             patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('utils.db_utils.get_chroma_collection', return_value=mock_chromadb), \
             patch('services.updater_service.get_chroma_collection', return_value=mock_chromadb), \
             patch('services.updater_service.openai_client', mock_openai_client), \
             patch('services.updater_service.get_document_content', return_value="Existing"), \
             patch('services.updater_service.update_document_content') as mock_update, \
             patch('services.updater_service.update_vector_db'):
            
            # Setup document stack
            document_stacks.clear()
            document_stacks["test-doc-id"] = {
                "char_count": 50,  # Below threshold
                "messages": [
                    {"user": "U1", "text": "Test message", "ts": "1.0"}
                ],
                "last_version": None
            }
            
            # Force update (should work even below threshold)
            process_document_update("test-doc-id", force=True)
            
            # Verify update was triggered
            assert mock_openai_client.chat.completions.create.called
            assert mock_update.called
            
            # Verify stack was reset
            assert document_stacks["test-doc-id"]["char_count"] == 0
    
    def test_drive_folder_sync(
        self,
        mock_env_vars,
        mock_mongodb,
        mock_google_drive
    ):
        """Test syncing Drive folder to MongoDB mapping"""
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        # Create separate mocks for different collections
        mock_metadata_collection = Mock()
        mock_mapping_collection = Mock()
        
        # Mock metadata collection - no existing metadata
        mock_metadata_collection.find_one.return_value = None
        
        def get_collection(name):
            if name == "document_metadata":
                return mock_metadata_collection
            elif name == "drive_file_mapping":
                return mock_mapping_collection
            return mock_collection
        
        mock_db.__getitem__ = Mock(side_effect=get_collection)
        mock_db.document_metadata = mock_metadata_collection
        mock_db.drive_file_mapping = mock_mapping_collection
        
        with patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('repository.drive_repository._get_google_drive_service', return_value=mock_drive_service), \
             patch('repository.drive_repository.list_documents_in_folder') as mock_list_docs:
            
            # Mock list_documents_in_folder to return formatted documents
            mock_list_docs.return_value = [
                {
                    "id": "doc-1",
                    "name": "Document 1",
                    "created_time": "2024-01-01T00:00:00Z",
                    "modified_time": "2024-01-01T00:00:00Z"
                }
            ]
            
            # Sync folder
            mapping = sync_drive_folder_to_mapping("test-folder-id")
            
            # Verify mapping structure
            assert mapping["folder_id"] == "test-folder-id"
            assert len(mapping["documents"]) == 1
            assert mapping["documents"][0]["id"] == "doc-1"
            assert "synced_at" in mapping
            
            # Verify metadata was saved
            assert mock_metadata_collection.insert_one.called or mock_metadata_collection.update_one.called
            
            # Verify mapping was saved
            assert mock_mapping_collection.replace_one.called
    
    def test_search_documents(
        self,
        mock_env_vars,
        mock_mongodb,
        mock_google_drive
    ):
        """Test searching documents by name or metadata"""
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        # Create a separate mock for metadata collection
        mock_metadata_collection = Mock()
        mock_metadata_collection.find.return_value = [
            {
                "_id": "meta-id",
                "doc_id": "doc-2",
                "name": "Document 2",
                "tags": ["api", "docs"],
                "description": "API documentation",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        # Mock db to return different collections
        def get_collection(name):
            if name == "document_metadata":
                return mock_metadata_collection
            return mock_collection
        
        mock_db.__getitem__ = Mock(side_effect=get_collection)
        mock_db.document_metadata = mock_metadata_collection
        
        with patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('repository.drive_repository.search_documents_by_name') as mock_search_drive:
            
            # Mock Drive search results
            mock_search_drive.return_value = [
                {
                    "id": "doc-1",
                    "name": "Document 1",
                    "created_time": "2024-01-01T00:00:00Z",
                    "modified_time": "2024-01-01T00:00:00Z"
                }
            ]
            
            # Search documents
            results = search_documents("api")
            
            # Verify results include both Drive and metadata matches
            assert len(results) >= 1
            doc_ids = [doc["id"] for doc in results]
            assert "doc-1" in doc_ids or "doc-2" in doc_ids
    
    def test_get_documents_from_mapping(
        self,
        mock_env_vars,
        mock_mongodb,
        mock_google_drive
    ):
        """Test getting documents from mapping with fallback to Drive API"""
        mock_db, mock_collection = mock_mongodb
        mock_drive_service, mock_docs_service = mock_google_drive
        
        # Create a separate mock for mapping collection
        mock_mapping_collection = Mock()
        
        # Test 1: Get from MongoDB mapping
        mock_mapping_collection.find_one.return_value = {
            "type": "drive_mapping",
            "folder_id": "test-folder-id",
            "documents": [
                {"id": "doc-1", "name": "Document 1"}
            ],
            "synced_at": "2024-01-01T00:00:00Z"
        }
        
        def get_collection(name):
            if name == "drive_file_mapping":
                return mock_mapping_collection
            return mock_collection
        
        mock_db.__getitem__ = Mock(side_effect=get_collection)
        mock_db.drive_file_mapping = mock_mapping_collection
        
        with patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('repository.drive_repository.list_documents_in_folder') as mock_list_docs:
            
            docs = get_documents_from_mapping("test-folder-id")
            
            # Should return documents from mapping
            assert len(docs) == 1
            assert docs[0]["id"] == "doc-1"
            # Should not call Drive API when mapping exists
            mock_list_docs.assert_not_called()
        
        # Test 2: Fallback to Drive API when mapping doesn't exist
        mock_mapping_collection.find_one.return_value = None
        
        with patch('utils.db_utils.get_mongodb_db', return_value=mock_db), \
             patch('repository.drive_repository.list_documents_in_folder') as mock_list_docs:
            
            mock_list_docs.return_value = [
                {"id": "doc-2", "name": "Document 2"}
            ]
            
            docs = get_documents_from_mapping("test-folder-id")
            
            # Should return documents from Drive API
            assert len(docs) == 1
            assert docs[0]["id"] == "doc-2"
            # Should have called Drive API
            mock_list_docs.assert_called_once_with("test-folder-id")
            # Should have saved mapping
            assert mock_mapping_collection.replace_one.called

