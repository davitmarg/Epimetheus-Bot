"""
Message formatting utilities

This module contains utility functions for message processing and document operations.
"""

import re
from typing import Optional


def extract_doc_id_from_chunk_id(chunk_id: str) -> str:
    """
    Extract document ID from a ChromaDB chunk ID.
    
    ChromaDB chunk IDs are formatted as: doc_id_chunk_N
    
    Args:
        chunk_id: ChromaDB chunk ID (e.g., "doc123_chunk_0")
        
    Returns:
        Document ID (e.g., "doc123")
    """
    return chunk_id.rsplit('_chunk_', 1)[0]


def extract_message_text(text: str) -> str:
    """
    Extract message text, removing bot mentions.
    
    Args:
        text: Raw message text with bot mentions
        
    Returns:
        Cleaned message text without mentions
    """
    return re.sub(r'<@[A-Z0-9]+>', '', text).strip()


def extract_document_mention(text: str) -> Optional[str]:
    """
    Extract document ID from a message that mentions a document.
    
    Looks for Google Docs URLs in the message text.
    
    Args:
        text: Message text
        
    Returns:
        Document ID if found, None otherwise
    """
    # Look for Google Docs URLs
    doc_url_pattern = r'docs\.google\.com/document/d/([a-zA-Z0-9-_]+)'
    match = re.search(doc_url_pattern, text)
    if match:
        return match.group(1)
    
    return None

