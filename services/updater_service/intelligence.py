"""
Intelligence Module
Delegates message chunking, knowledge extraction, and document routing to
DocumentRepository to keep a single source of truth.
"""

from typing import Dict, Any, List, Optional

from repository.document_repository import get_document_repository

document_repo = get_document_repository()


def determine_target_documents(
    messages: List[Dict[str, Any]], team_id: str
) -> List[str]:
    """Delegate target document selection to DocumentRepository."""
    return document_repo.determine_target_documents(messages, team_id)


def generate_document_update(
    old_content: str, new_messages: List[Dict[str, Any]]
) -> str:
    """Use repository implementation for document updates."""
    return document_repo.generate_document_update(old_content, new_messages)


def generate_change_summary(
    old_content: str,
    new_content: str,
    new_messages: List[Dict[str, Any]],
    doc_id: Optional[str] = None,
) -> str:
    """Use repository implementation for change summary."""
    return document_repo.generate_change_summary(
        old_content=old_content,
        new_content=new_content,
        new_messages=new_messages,
        doc_id=doc_id,
    )


def chunk_messages(
    messages: List[Dict[str, Any]], chunk_size: int = None
) -> List[List[Dict[str, Any]]]:
    """Route chunking to repository to avoid divergence."""
    return document_repo.chunk_messages(messages, chunk_size)


def extract_knowledge_from_chunk(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use repository knowledge extraction to keep logic consistent."""
    return document_repo.extract_knowledge_from_chunk(messages)


def determine_if_document_needs_update(
    knowledge: str, messages: List[Dict[str, Any]], team_id: str
) -> Optional[Dict[str, Any]]:
    """Use repository logic for update decision."""
    return document_repo.determine_if_document_needs_update(
        knowledge=knowledge, messages=messages, team_id=team_id
    )
