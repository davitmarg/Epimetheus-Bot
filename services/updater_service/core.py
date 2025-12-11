"""
Core Module
Orchestrates the update process by combining Intelligence and Storage modules.
"""

from typing import Dict, Any, List

from repository.document_repository import get_document_repository

document_repo = get_document_repository()


def process_document_update(
    doc_id: str, messages: List[Dict[str, Any]], trigger_type: str = "agent_command"
) -> Dict[str, Any]:
    """
    Process document update immediately with the given messages
    """
    return document_repo.process_document_update(
        doc_id=doc_id, messages=messages, trigger_type=trigger_type
    )


def ingest_messages(payload: Dict[str, Any]):
    """
    Process messages from Redis queue as a log.
    """
    return document_repo.ingest_messages(payload)
