"""
Pytest configuration and fixtures for Epimetheus Bot tests
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing"""
    env_vars = {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "GOOGLE_DRIVE_FOLDER_ID": "test-folder-id",
        "GOOGLE_CREDENTIALS_PATH": "./test-credentials.json",
        "OPENAI_API_KEY": "sk-test-key",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_DB": "0",
        "MONGODB_HOST": "localhost",
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": "epimetheus_test",
        "MONGODB_USERNAME": "",
        "MONGODB_PASSWORD": "",
        "CHROMA_HOST": "localhost",
        "CHROMA_PORT": "8000",
        "CHROMA_USE_HTTP": "false",
        "CHAR_THRESHOLD": "100",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    mock_client = Mock()
    mock_client.pipeline.return_value = Mock()
    mock_client.blpop.return_value = None
    mock_client.rpush.return_value = None
    mock_client.lrange.return_value = []
    mock_client.delete.return_value = None
    mock_client.getset.return_value = "0"
    mock_client.sadd.return_value = 1
    mock_client.incr.return_value = 1
    mock_client.ping.return_value = True
    
    # Mock pipeline
    mock_pipe = Mock()
    mock_pipe.rpush.return_value = mock_pipe
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.sadd.return_value = mock_pipe
    mock_pipe.lrange.return_value = mock_pipe
    mock_pipe.delete.return_value = mock_pipe
    mock_pipe.execute.return_value = [None, 1, 1]  # [rpush_result, incr_result, sadd_result]
    mock_client.pipeline.return_value = mock_pipe
    
    return mock_client


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB database and collections"""
    mock_db = Mock()
    mock_collection = Mock()
    
    # Mock collections
    mock_db.__getitem__.return_value = mock_collection
    mock_db.document_versions = mock_collection
    mock_db.document_metadata = mock_collection
    mock_db.drive_file_mapping = mock_collection
    
    # Mock collection operations
    mock_collection.find_one.return_value = None
    mock_collection.find.return_value = []
    mock_collection.insert_one.return_value = Mock(inserted_id="test-id")
    mock_collection.update_one.return_value = Mock()
    mock_collection.replace_one.return_value = Mock()
    mock_collection.create_index.return_value = "test-index"
    
    return mock_db, mock_collection


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB collection"""
    mock_collection = Mock()
    mock_collection.query.return_value = {"ids": [[]]}
    mock_collection.add.return_value = None
    mock_collection.delete.return_value = None
    return mock_collection


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Updated document content"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_google_drive():
    """Mock Google Drive API"""
    mock_drive_service = Mock()
    mock_docs_service = Mock()
    
    # Mock Drive file list
    mock_file = {
        "id": "test-doc-id",
        "name": "Test Document",
        "createdTime": "2024-01-01T00:00:00Z",
        "modifiedTime": "2024-01-01T00:00:00Z"
    }
    mock_drive_service.files.return_value.list.return_value.execute.return_value = {
        "files": [mock_file]
    }
    
    # Mock Docs document
    mock_doc = {
        "documentId": "test-doc-id",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Existing content"}}
                        ]
                    },
                    "endIndex": 20
                }
            ]
        }
    }
    mock_docs_service.documents.return_value.get.return_value.execute.return_value = mock_doc
    mock_docs_service.documents.return_value.create.return_value.execute.return_value = {
        "documentId": "new-doc-id"
    }
    mock_docs_service.documents.return_value.batchUpdate.return_value.execute.return_value = {}
    
    return mock_drive_service, mock_docs_service


@pytest.fixture
def sample_slack_message():
    """Sample Slack message event"""
    return {
        "type": "message",
        "user": "U123456",
        "text": "This is a test message about API documentation",
        "ts": "1234567890.123456",
        "channel": "C123456",
        "thread_ts": None
    }


@pytest.fixture
def sample_message_batch():
    """Sample message batch payload"""
    return {
        "team_id": "T123456",
        "threads": [
            {
                "thread_id": "1234567890.123456",
                "messages": [
                    {
                        "user": "U123456",
                        "text": "This is a test message about API documentation",
                        "ts": "1234567890.123456"
                    },
                    {
                        "user": "U789012",
                        "text": "We should update the authentication section",
                        "ts": "1234567891.123456"
                    }
                ]
            }
        ]
    }

