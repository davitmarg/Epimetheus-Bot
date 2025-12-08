"""
Intelligence Module
Handles LLM generation, message chunking, and decision making (RAG).
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Import utilities and repos
from utils.message_utils import extract_doc_id_from_chunk_id
from repository.llm_repository import get_llm_repository
from repository.document_repository import get_document_repository
from repository.drive_repository import get_drive_repository

load_dotenv()

GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

llm_repo = get_llm_repository()
document_repo = get_document_repository()
drive_repo = get_drive_repository()


def determine_target_documents(
    messages: List[Dict[str, Any]], team_id: str
) -> List[str]:
    """
    Determine which document(s) should receive these messages.
    """
    # Strategy 1: Use vector search to find most relevant documents
    if messages:
        # Combine all message text
        combined_text = " ".join([msg.get("text", "") for msg in messages])

        if combined_text.strip():
            try:
                # Search for similar content in vector DB
                results = document_repo.search_similar_documents(
                    combined_text, n_results=3
                )

                if results and results.get("ids") and results["ids"][0]:
                    # Extract unique doc_ids from results
                    doc_ids = set()
                    for id_list in results["ids"]:
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
                return [doc["id"] for doc in docs]
        except Exception as e:
            print(f"Drive Warning: Could not list documents in folder: {e}")

    # Last resort: create a default document
    if GOOGLE_DRIVE_FOLDER_ID:
        try:
            default_doc = drive_repo.create_document(
                name=f"Team {team_id} Documentation",
                folder_id=GOOGLE_DRIVE_FOLDER_ID,
                initial_content="",
            )
            return [default_doc["id"]]
        except Exception as e:
            print(f"Drive Warning: Error creating default document: {e}")

    return []


def generate_document_update(
    old_content: str, new_messages: List[Dict[str, Any]]
) -> str:
    """Use LLM repository to generate updated document content"""
    try:
        return llm_repo.generate_document_update(
            old_content=old_content,
            new_messages=new_messages,
            temperature=0.3,
            max_tokens=4000,
        )
    except Exception as e:
        raise Exception(f"Error generating document update: {str(e)}")


def generate_change_summary(
    old_content: str, new_content: str, new_messages: List[Dict[str, Any]]
) -> str:
    """Use LLM repository to generate a concise summary of document changes"""
    try:
        return llm_repo.generate_change_summary(
            old_content=old_content,
            new_content=new_content,
            new_messages=new_messages,
            temperature=0.5,
            max_tokens=200,
        )
    except Exception as e:
        print(f"Warning: Error generating change summary: {str(e)}")
        return "Document updated successfully."


def chunk_messages(
    messages: List[Dict[str, Any]], chunk_size: int = None
) -> List[List[Dict[str, Any]]]:
    """Chunk messages into groups of last N messages."""
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
        chunk = sorted_messages[max(0, i - chunk_size + 1) : i + 1]
        if len(chunk) >= 2:  # Only include chunks with at least 2 messages
            chunks.append(chunk)

    # Return the most recent chunk if we have messages
    if sorted_messages:
        recent_chunk = (
            sorted_messages[-chunk_size:]
            if len(sorted_messages) >= chunk_size
            else sorted_messages
        )
        return [recent_chunk]

    return []


def extract_knowledge_from_chunk(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract knowledge from a chunk of messages using LLM."""
    if not messages:
        return {"knowledge": "", "has_new_information": False, "relevance_score": 0.0}

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
            conversation_text=combined_text, temperature=0.3, max_tokens=500
        )

        # Check if there's new information
        has_new_information = (
            knowledge.upper() != "NO_NEW_INFORMATION" and len(knowledge) > 20
        )

        # Calculate relevance score based on knowledge length and content
        relevance_score = 0.0
        if has_new_information:
            # Simple heuristic: longer, more detailed knowledge = higher relevance
            relevance_score = min(1.0, len(knowledge) / 500.0)

        return {
            "knowledge": knowledge,
            "has_new_information": has_new_information,
            "relevance_score": relevance_score,
            "message_count": len(messages),
        }

    except Exception as e:
        print(f"Error extracting knowledge: {e}")
        return {
            "knowledge": "",
            "has_new_information": False,
            "relevance_score": 0.0,
            "error": str(e),
        }


def determine_if_document_needs_update(
    knowledge: str, messages: List[Dict[str, Any]], team_id: str
) -> Optional[Dict[str, Any]]:
    """Determine if a document needs updating based on extracted knowledge."""
    knowledge_extraction_threshold = float(
        os.environ.get("KNOWLEDGE_EXTRACTION_THRESHOLD", "0.7")
    )

    if not knowledge or len(knowledge.strip()) < 20:
        return None

    try:
        # Use vector search to find relevant documents
        search_results = document_repo.search_similar_documents(knowledge, n_results=3)

        if (
            not search_results
            or not search_results.get("ids")
            or not search_results["ids"][0]
        ):
            # No relevant documents found, but knowledge exists
            # Could create a new document or return None
            return None

        # Get the most relevant document
        chunk_ids = search_results["ids"][0]
        distances_list = search_results.get("distances", [[]])[0]

        if not chunk_ids or not distances_list:
            return None

        # Extract doc_id from first chunk
        first_chunk_id = chunk_ids[0]
        doc_id = extract_doc_id_from_chunk_id(first_chunk_id)
        distance = distances_list[0] if len(distances_list) > 0 else 1.0

        # Check if relevance is high enough (lower distance = more relevant)
        relevance_threshold = (
            1.0 - knowledge_extraction_threshold
        )  # Convert threshold to distance

        if distance < relevance_threshold:
            return {
                "doc_id": doc_id,
                "confidence": 1.0 - distance,  # Convert distance to confidence
                "distance": distance,
            }

        return None

    except Exception as e:
        print(f"Error determining document update need: {e}")
        return None
