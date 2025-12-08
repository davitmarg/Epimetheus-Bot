"""
Storage Module
Handles interactions with Document Repository, Drive Repository, and Vector Database.
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Import repositories
from repository.drive_repository import get_drive_repository
from repository.document_repository import get_document_repository

load_dotenv()

document_repo = get_document_repository()
drive_repo = get_drive_repository()


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
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_size = len(word)
        else:
            current_chunk.append(word)
            current_size += word_size

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def update_vector_db(doc_id: str, content: str):
    """Update vector database with document chunks"""
    chunks = chunk_document(content)

    # Delete old chunks for this document
    document_repo.delete_document_chunks(doc_id)

    # Add new chunks
    if chunks:
        document_repo.add_document_chunks(doc_id, chunks)


def get_document_metadata(doc_id: str) -> Optional[Dict[str, Any]]:
    """Helper to safely get metadata"""
    return document_repo.get_metadata(doc_id)


def get_current_content(doc_id: str) -> str:
    """Helper to get current content from Drive"""
    return drive_repo.get_document_content(doc_id)


def update_drive_content(doc_id: str, old_content: str, new_content: str):
    """Helper to update drive content"""
    drive_repo.update_document_content_partial(doc_id, old_content, new_content)
