"""
Agentic Functionality for LLM Repository

Provides agentic capabilities including LangChain agent, tools, and mention processing.
"""

import os
import time
import traceback
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from repository.document_repository import get_document_repository
from repository.drive_repository import get_drive_repository
from repository.slack_repository import get_slack_repository
from utils.message_utils import extract_doc_id_from_chunk_id, extract_document_mention
from utils.constants import DEFAULT_PROCESSING_ERROR_MESSAGE
from utils.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

MESSAGE_CHUNK_SIZE = int(os.environ.get("MESSAGE_CHUNK_SIZE", "10"))


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def answer_question_from_documentation(question: str) -> str:
    """
    Answer a question using RAG (Retrieval Augmented Generation) from documentation.
    Use this tool when the user is asking a question and wants to know information
    from existing documentation.
    
    Args:
        question: The user's question about the documentation
    
    Returns:
        Answer to the question based on documentation
    """
    try:
        # Lazy import to avoid circular dependency
        from repository.llm_repository import get_llm_repository
        
        document_repo = get_document_repository()
        llm_repo = get_llm_repository()
        
        # Search for relevant document chunks
        search_results = document_repo.search_similar_documents(question, n_results=5)
        
        if not search_results or not search_results.get('ids') or not search_results['ids'][0]:
            return f"I couldn't find any relevant information in the documentation to answer your question. The documents may not contain information about this topic."
        
        # Extract document chunks and metadata
        chunk_ids = search_results['ids'][0]
        documents_list = search_results.get('documents', [[]])[0]
        metadatas_list = search_results.get('metadatas', [[]])[0]
        distances_list = search_results.get('distances', [[]])[0]
        
        # Get unique document IDs and their metadata
        doc_id_to_metadata = {}
        relevant_chunks = []
        
        for i, chunk_id in enumerate(chunk_ids):
            if i < len(documents_list):
                chunk_text = documents_list[i]
                metadata = metadatas_list[i] if i < len(metadatas_list) else {}
                doc_id = metadata.get('doc_id', extract_doc_id_from_chunk_id(chunk_id))
                
                # Store document metadata
                if doc_id not in doc_id_to_metadata:
                    doc_metadata = document_repo.get_metadata(doc_id)
                    if doc_metadata:
                        doc_id_to_metadata[doc_id] = doc_metadata
                
                # Add chunk if it's relevant (distance threshold)
                distance = distances_list[i] if i < len(distances_list) else 1.0
                if distance < 1.0:  # Only include reasonably relevant chunks
                    relevant_chunks.append(chunk_text)
        
        if not relevant_chunks:
            return "I couldn't find any relevant information in the documentation to answer your question."
        
        # Get document context (use first document found)
        document_context = None
        if doc_id_to_metadata:
            first_doc_id = list(doc_id_to_metadata.keys())[0]
            doc_meta = doc_id_to_metadata[first_doc_id]
            document_context = {
                'doc_id': first_doc_id,
                'name': doc_meta.get('name', 'Unknown Document')
            }
        
        # Generate answer using LLM
        answer = llm_repo.answer_question(
            question=question,
            relevant_chunks=relevant_chunks[:5],  # Limit to top 5 chunks
            document_context=document_context,
            temperature=0.7,
            max_tokens=1000
        )
        
        # Add document link if available
        if document_context and document_context.get('doc_id'):
            doc_url = f"https://docs.google.com/document/d/{document_context['doc_id']}"
            answer += f"\n\n📄 <{doc_url}|View full document: {document_context['name']}>"
        
        return answer
        
    except Exception as e:
        return f"Error answering question: {str(e)}"


@tool
def update_documentation_with_information(
    information: str,
    doc_id: Optional[str] = None,
    channel: Optional[str] = None,
    thread_ts: Optional[str] = None
) -> str:
    """
    Update documentation with new information provided by the user.
    Use this tool when the user is providing new information, updates, corrections,
    or facts that should be added to the documentation.
    
    Args:
        information: The new information or updates to add to documentation
        doc_id: Optional specific document ID to update. If not provided, will find the most relevant document.
        channel: Optional Slack channel ID for notifications
        thread_ts: Optional Slack thread timestamp for notifications
    
    Returns:
        Confirmation message about the update with document details
    """
    try:
        # Lazy import to avoid circular dependency
        from services.updater_service import determine_target_documents, process_document_update
        
        slack_repo = get_slack_repository()
        
        # Create a message-like structure from the information
        message = {
            "text": information,
            "user": "user",
            "ts": thread_ts or str(time.time()) if thread_ts else str(time.time())
        }
        messages = [message]
        
        # Determine target document if not specified
        if not doc_id:
            target_doc_ids = determine_target_documents(messages, team_id="default")
            if not target_doc_ids:
                return "I couldn't determine which document to update. Please specify a document ID or ensure documents exist in the system."
            doc_id = target_doc_ids[0]
        
        # Process the document update
        result = process_document_update(
            doc_id=doc_id,
            messages=messages,
            trigger_type="agent_command"
        )
        
        if result["success"]:
            # Send notification if channel/thread available
            if channel and thread_ts:
                slack_repo.send_document_update_notification(
                    channel=channel,
                    thread_ts=thread_ts,
                    doc_id=result["doc_id"],
                    doc_name=result["doc_name"] or "Unknown Document",
                    message_count=result["message_count"],
                    success=True,
                    change_summary=result.get("change_summary")
                )
            
            # Return result data for agent to format
            return f"Document update successful. Document: {result.get('doc_name', 'Unknown')}, Change summary: {result.get('change_summary', 'Document updated')}, Version: {result.get('version_id', 'N/A')}"
        else:
            error_msg = result.get("error", "Unknown error")
            return f"Document update failed: {error_msg}"
            
    except Exception as e:
        traceback.print_exc()
        return f"Error updating documentation: {str(e)}"


@tool
def get_document_count() -> str:
    """
    Get the number of documents in the system.
    Use this tool when the user asks how many documents exist or wants to know the document count.
    
    Returns:
        Message with document count information
    """
    try:
        document_repo = get_document_repository()
        
        # Get documents from mapping
        docs = document_repo.get_documents_from_mapping()
        count = len(docs)
        
        return f"📊 There are {count} document(s) in the system"
            
    except Exception as e:
        return f"Error getting document count: {str(e)}"


@tool
def list_all_documents() -> str:
    """
    List all documents in the system with their names and links.
    Use this tool when the user asks to list documents, show all documents, or see what documents are available.
    
    Returns:
        Message with list of all documents
    """
    try:
        document_repo = get_document_repository()
        drive_repo = get_drive_repository()
        
        # Get all documents from Drive
        drive_docs = drive_repo.list_documents_in_folder()
        
        if not drive_docs:
            return f"📊 No documents found in folder."
        
        # Sort by name for easier reading
        sorted_docs = sorted(drive_docs, key=lambda x: x.get('name', '').lower())
        
        result = f"📚 All Documents ({len(sorted_docs)} total):\n\n"
        for i, doc in enumerate(sorted_docs, 1):
            doc_name = doc.get('name', 'Unknown')
            doc_id_item = doc.get('id', '')
            result += f"{i}. {doc_name}\n   🔗 <https://docs.google.com/document/d/{doc_id_item}|View Document>\n\n"
        
        return result
            
    except Exception as e:
        return f"Error listing documents: {str(e)}"


@tool
def get_document_last_updated(doc_id: Optional[str] = None) -> str:
    """
    Check when documents were last updated.
    Use this tool when the user asks about document update times or when documents were last modified.
    
    Args:
        doc_id: Optional specific document ID to check. If not provided, returns info for all documents.
    
    Returns:
        Message with last updated information
    """
    try:
        document_repo = get_document_repository()
        drive_repo = get_drive_repository()
        
        if doc_id:
            # Get specific document
            metadata = document_repo.get_metadata(doc_id)
            if not metadata:
                return f"❌ Document {doc_id} not found."
            
            # Get from Drive for most accurate modified time
            try:
                drive_docs = drive_repo.list_documents_in_folder()
                doc_info = next((d for d in drive_docs if d['id'] == doc_id), None)
                
                if doc_info:
                    modified_time = doc_info.get('modified_time', 'Unknown')
                    doc_name = metadata.get('name', 'Unknown Document')
                    return f"📄 Document: {doc_name}\n🕒 Last updated: {modified_time}\n🔗 <https://docs.google.com/document/d/{doc_id}|View Document>"
                else:
                    updated_at = metadata.get('updated_at', 'Unknown')
                    doc_name = metadata.get('name', 'Unknown Document')
                    return f"📄 Document: {doc_name}\n🕒 Last updated (from metadata): {updated_at}\n🔗 <https://docs.google.com/document/d/{doc_id}|View Document>"
            except Exception:
                updated_at = metadata.get('updated_at', 'Unknown')
                doc_name = metadata.get('name', 'Unknown Document')
                return f"📄 Document: {doc_name}\n🕒 Last updated (from metadata): {updated_at}\n🔗 <https://docs.google.com/document/d/{doc_id}|View Document>"
        else:
            # Get all documents
            drive_docs = drive_repo.list_documents_in_folder()
            
            if not drive_docs:
                return f"📊 No documents found in folder."
            
            # Sort by modified time
            sorted_docs = sorted(drive_docs, key=lambda x: x.get('modified_time', ''), reverse=True)
            
            result = f"📊 Last updated documents ({len(sorted_docs)} total):\n\n"
            for i, doc in enumerate(sorted_docs[:10], 1):  # Show top 10
                modified_time = doc.get('modified_time', 'Unknown')
                doc_name = doc.get('name', 'Unknown')
                doc_id_item = doc.get('id', '')
                result += f"{i}. {doc_name}\n   🕒 {modified_time}\n   🔗 <https://docs.google.com/document/d/{doc_id_item}|View>\n\n"
            
            if len(sorted_docs) > 10:
                result += f"... and {len(sorted_docs) - 10} more document(s)"
            
            return result
            
    except Exception as e:
        return f"Error getting document update times: {str(e)}"


@tool
def search_documents_by_name_or_content(query: str, max_results: int = 10) -> str:
    """
    Search for documents by name or content and return their document IDs.
    Use this tool when the user wants to find a specific document by searching for its name or content.
    
    Args:
        query: Search query - can be a document name or content keywords
        max_results: Maximum number of results to return (default: 10)
    
    Returns:
        Message with list of matching documents including their IDs, names, and links
    """
    try:
        document_repo = get_document_repository()
        drive_repo = get_drive_repository()
        
        # Track unique documents by ID
        found_documents = {}
        
        # Search by name/metadata
        try:
            name_results = document_repo.search_documents(query)
            for doc in name_results:
                doc_id = doc.get('id')
                if doc_id and doc_id not in found_documents:
                    found_documents[doc_id] = {
                        'id': doc_id,
                        'name': doc.get('name', 'Unknown'),
                        'match_type': doc.get('match_type', 'name'),
                        'modified_time': doc.get('modified_time')
                    }
        except Exception as e:
            logger.warning(f"Error searching by name: {e}")
        
        # Search by content using vector search
        try:
            content_results = document_repo.search_similar_documents(query, n_results=max_results)
            if content_results and content_results.get('ids') and content_results['ids'][0]:
                chunk_ids = content_results['ids'][0]
                metadatas_list = content_results.get('metadatas', [[]])[0]
                distances_list = content_results.get('distances', [[]])[0]
                
                # Extract unique document IDs from chunks
                for i, chunk_id in enumerate(chunk_ids):
                    doc_id = extract_doc_id_from_chunk_id(chunk_id)
                    if doc_id and doc_id not in found_documents:
                        # Get document metadata
                        metadata = document_repo.get_metadata(doc_id)
                        if metadata:
                            found_documents[doc_id] = {
                                'id': doc_id,
                                'name': metadata.get('name', 'Unknown'),
                                'match_type': 'content',
                                'relevance_score': 1.0 - (distances_list[i] if i < len(distances_list) else 1.0)
                            }
        except Exception as e:
            logger.warning(f"Error searching by content: {e}")
        
        if not found_documents:
            return f"🔍 No documents found matching '{query}'."
        
        # Sort results: name matches first, then by relevance score
        sorted_docs = sorted(
            found_documents.values(),
            key=lambda x: (
                0 if x.get('match_type') == 'name' else 1,  # Name matches first
                -x.get('relevance_score', 0) if x.get('match_type') == 'content' else 0  # Higher relevance first
            )
        )[:max_results]
        
        result = f"🔍 Found {len(sorted_docs)} document(s) matching '{query}':\n\n"
        for i, doc in enumerate(sorted_docs, 1):
            doc_name = doc.get('name', 'Unknown')
            doc_id = doc.get('id', '')
            match_type = doc.get('match_type', 'unknown')
            match_info = "📝 Name match" if match_type == 'name' else f"📄 Content match (relevance: {doc.get('relevance_score', 0):.2f})"
            
            result += f"{i}. {doc_name}\n   ID: {doc_id}\n   {match_info}\n   🔗 <https://docs.google.com/document/d/{doc_id}|View Document>\n\n"
        
        return result
            
    except Exception as e:
        return f"Error searching documents: {str(e)}"


@tool
def update_document_formatting(
    doc_id: str,
    formatting_instructions: str,
    channel: Optional[str] = None,
    thread_ts: Optional[str] = None
) -> str:
    """
    Update the formatting of a document (headings, bold, italic, lists, etc.) without changing content.
    Use this tool when the user wants to improve or fix document formatting, structure, or styling.
    
    Args:
        doc_id: Document ID to update
        formatting_instructions: Description of formatting changes needed (e.g., "Make section titles headings", "Bold important terms")
        channel: Optional Slack channel ID for notifications
        thread_ts: Optional Slack thread timestamp for notifications
    
    Returns:
        Confirmation message about the formatting update
    """
    try:
        from repository.llm_repository.prompts import document_formatting_prompt
        from repository.llm_repository import get_llm_repository
        from repository.drive_repository import get_drive_repository
        
        document_repo = get_document_repository()
        drive_repo = get_drive_repository()
        llm_repo = get_llm_repository()
        
        # Get document metadata
        metadata = document_repo.get_metadata(doc_id)
        if not metadata:
            return f"Document {doc_id} not found."
        
        doc_name = metadata.get('name', 'Unknown Document')
        
        # Get current document content
        old_content = drive_repo.get_document_content(doc_id)
        
        # Generate formatted content using LLM
        prompt_text = document_formatting_prompt(old_content, formatting_instructions)
        
        from langchain_core.messages import SystemMessage, HumanMessage
        from langchain_openai import ChatOpenAI
        
        # Get LLM configuration
        openai_base_url = os.environ.get("OPENAI_BASE_URL")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")
        
        llm_kwargs = {
            "model": openai_model,
            "api_key": openai_api_key,
            "temperature": 0.3,
        }
        if openai_base_url:
            llm_kwargs["base_url"] = openai_base_url
        
        formatted_llm = ChatOpenAI(**llm_kwargs)
        messages = [
            SystemMessage(content="You are a document formatting expert. Apply formatting changes while preserving all content."),
            HumanMessage(content=prompt_text)
        ]
        response = formatted_llm.invoke(messages)
        new_content = response.content.strip()
        
        # Apply partial update to preserve formatting
        drive_repo.update_document_content_partial(doc_id, old_content, new_content)
        
        # Update vector database
        from services.updater_service import update_vector_db
        update_vector_db(doc_id, new_content)
        
        # Return result data for agent to format
        return f"Document formatting updated successfully. Document: {doc_name}, Formatting instructions applied: {formatting_instructions}"
        
    except Exception as e:
        traceback.print_exc()
        return f"Error updating document formatting: {str(e)}"


@tool
def update_document_partial(
    doc_id: str,
    section_to_update: str,
    new_content: str,
    channel: Optional[str] = None,
    thread_ts: Optional[str] = None
) -> str:
    """
    Perform a partial update to a specific section of a document.
    This preserves formatting and allows Google Docs versioning to track where edits occurred.
    Use this tool when the user wants to update only a specific part of a document.
    
    Args:
        doc_id: Document ID to update
        section_to_update: The section or text to replace (helps identify location)
        new_content: The new content for that section
        channel: Optional Slack channel ID for notifications
        thread_ts: Optional Slack thread timestamp for notifications
    
    Returns:
        Confirmation message about the partial update
    """
    try:
        from repository.drive_repository import get_drive_repository
        from services.updater_service import update_vector_db, save_document_version
        
        document_repo = get_document_repository()
        drive_repo = get_drive_repository()
        
        # Get document metadata
        metadata = document_repo.get_metadata(doc_id)
        if not metadata:
            return f"Document {doc_id} not found."
        
        doc_name = metadata.get('name', 'Unknown Document')
        
        # Get current document content
        old_content = drive_repo.get_document_content(doc_id)
        
        # Create updated content by replacing the section
        # Find the section in old content and replace it
        section_found = section_to_update in old_content
        if section_found:
            new_full_content = old_content.replace(section_to_update, new_content, 1)
            update_type = "replaced"
        else:
            # If exact match not found, append the new content
            new_full_content = old_content + "\n\n" + new_content
            update_type = "appended"
        
        # Save version before update (for versioning)
        version_metadata = {
            "char_count": len(new_content),
            "message_count": 1,
            "trigger_type": "agent_partial_update",
            "section_updated": section_to_update[:100]  # Store first 100 chars of section
        }
        version_id = save_document_version(doc_id, old_content, version_metadata)
        
        # Apply partial update (this preserves formatting and enables versioning)
        drive_repo.update_document_content_partial(doc_id, old_content, new_full_content)
        
        # Update vector database
        update_vector_db(doc_id, new_full_content)
        
        # Return result data for agent to format
        return f"Partial update successful. Document: {doc_name}, Action: {update_type}, Version: {version_id}"
        
    except Exception as e:
        traceback.print_exc()
        return f"Error performing partial update: {str(e)}"


class EpimetheusAgent:
    """Agent for processing user messages and handling document operations"""
    
    def __init__(self, base_llm_kwargs: Dict[str, Any] = None):
        """
        Initialize the agent with LLM and tools.
        
        Args:
            base_llm_kwargs: Optional base LLM configuration (uses default if not provided)
        """
        self.llm = None
        self.tools = None
        self.base_llm_kwargs = base_llm_kwargs or self._get_default_llm_kwargs()
        self._initialize_agent()
    
    def _get_default_llm_kwargs(self) -> Dict[str, Any]:
        """Get default LLM configuration from environment"""
        openai_base_url = os.environ.get("OPENAI_BASE_URL")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")
        
        if not openai_api_key:
            raise Exception("OPENAI_API_KEY not configured")
        
        llm_kwargs = {
            "model": openai_model,
            "api_key": openai_api_key,
            "temperature": 0.3,
        }
        
        if openai_base_url:
            llm_kwargs["base_url"] = openai_base_url
        
        return llm_kwargs
    
    def _initialize_agent(self):
        """Create and configure the LangChain agent"""
        # Create LLM with agent-specific temperature
        llm_kwargs = {**self.base_llm_kwargs, "temperature": 0.3}
        llm = ChatOpenAI(**llm_kwargs)
        self.tools = [
            answer_question_from_documentation,
            update_documentation_with_information,
            get_document_count,
            list_all_documents,
            get_document_last_updated,
            search_documents_by_name_or_content,
            update_document_formatting,
            update_document_partial,
        ]
        self.llm = llm.bind_tools(self.tools)
    
    def run(self, message: str, event: Dict[str, Any], team_id: str) -> str:
        """
        Run the agent with a user message and handle tool calls.
        
        Args:
            message: User's message
            event: Slack event (for document updates - contains channel, thread_ts, etc.)
            team_id: Slack team ID
        
        Returns:
            Agent's response
        """
        # Extract channel and thread_ts from event for tool calls
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        # Import prompt function
        from repository.llm_repository.prompts import agent_system_prompt
        
        # Create messages
        messages = [
            SystemMessage(content=agent_system_prompt()),
            HumanMessage(content=message)
        ]
        
        # Invoke agent
        response = self.llm.invoke(messages)
        logger.debug(f"Response: {response}")
        logger.debug(f"Tool calls: {response.tool_calls}")
        logger.debug(f"Invalid tool calls: {getattr(response, 'invalid_tool_calls', [])}")
        
        # Handle tool calls (including invalid ones that we can recover from)
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        while (response.tool_calls or getattr(response, 'invalid_tool_calls', [])) and iteration < max_iterations:
            iteration += 1
            tool_messages = []
            
            # Process valid tool calls
            for tool_call in response.tool_calls or []:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args")
                tool_call_id = tool_call.get("id")
                
                # Handle None args - convert to empty dict
                if tool_args is None:
                    tool_args = {}
                elif not isinstance(tool_args, dict):
                    tool_args = {}
                
                if not tool_name:
                    continue
                
                # Find the tool
                tool_func = None
                for tool in self.tools:
                    if tool.name == tool_name:
                        tool_func = tool
                        break
                
                if tool_func:
                    try:
                        # Add channel and thread_ts to tool args for tools that support notifications
                        if tool_name in ["update_documentation_with_information", "update_document_formatting", "update_document_partial"]:
                            tool_args["channel"] = channel
                            tool_args["thread_ts"] = thread_ts
                        
                        # Execute tool
                        result = tool_func.invoke(tool_args)
                        tool_messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call_id
                        ))
                    except Exception as e:
                        # Handle tool execution errors
                        error_msg = f"Error executing {tool_name}: {str(e)}"
                        tool_messages.append(ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id
                        ))
                else:
                    # Tool not found
                    tool_messages.append(ToolMessage(
                        content=f"Tool {tool_name} not found",
                        tool_call_id=tool_call_id
                    ))
            
            # Process invalid tool calls - try to recover for tools that don't need args
            invalid_tool_calls = getattr(response, 'invalid_tool_calls', [])
            tools_without_args = ["get_document_count", "list_all_documents", "get_document_last_updated"]  # Tools that don't require arguments
            
            for invalid_call in invalid_tool_calls:
                tool_call_id = invalid_call.get("id")
                tool_name = invalid_call.get("name", "unknown")
                error = invalid_call.get("error", "Invalid tool call")
                invalid_args = invalid_call.get("args")
                
                # If it's a tool that doesn't need args and args is None, try to execute it anyway
                if tool_name in tools_without_args and invalid_args is None:
                    # Find the tool
                    tool_func = None
                    for tool in self.tools:
                        if tool.name == tool_name:
                            tool_func = tool
                            break
                    
                    if tool_func:
                        try:
                            # Execute with empty args
                            result = tool_func.invoke({})
                            tool_messages.append(ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call_id
                            ))
                            continue
                        except Exception as e:
                            # If execution fails, fall through to error message
                            pass
                
                # Send error message back to LLM for other invalid calls
                error_msg = f"Invalid tool call for {tool_name}: {error}. Please retry with correct arguments."
                tool_messages.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id
                ))
            
            # Only continue if we have tool messages to process
            if not tool_messages:
                break
            
            # Check if we've hit max iterations before invoking LLM again
            if iteration >= max_iterations:
                # Return tool results from this iteration if available
                tool_results = []
                for tool_msg in tool_messages:
                    if hasattr(tool_msg, 'content'):
                        tool_results.append(tool_msg.content)
                if tool_results:
                    return "\n\n".join(tool_results)
                raise Exception("Agent reached maximum iterations. The request may be too complex or the LLM is having issues.")
            
            # Add tool messages and get next response
            messages.append(response)
            for tool_msg in tool_messages:
                messages.append(tool_msg)
            
            try:
                response = self.llm.invoke(messages)
            except (ValueError, Exception) as e:
                # If LLM invocation fails after tool execution, try to return tool results
                # This handles cases where the LLM provider fails but we successfully executed tools
                error_str = str(e)
                logger.error(f"LLM invocation failed after tool execution: {error_str}")
                
                # If we have tool messages, try to synthesize a response from them
                if tool_messages:
                    # Extract results from tool messages
                    tool_results = []
                    for tool_msg in tool_messages:
                        if hasattr(tool_msg, 'content'):
                            tool_results.append(tool_msg.content)
                    
                    # Return a synthesized response from tool results
                    if tool_results:
                        combined_result = "\n\n".join(tool_results)
                        return combined_result
                
                # If no tool results available, re-raise the error
                raise Exception(f"LLM provider error after tool execution: {error_str}")
        
        # Ensure we always return a non-empty string
        content = response.content if hasattr(response, 'content') else str(response)
        logger.debug(f"Agent response: {response}")
        if not content or not content.strip():
            raise Exception("I processed your request but didn't generate a response. Please try rephrasing your question or providing more context.\n%s" % content)

        return content


class AgenticRepository:
    """Repository for agentic processing of mentions and commands"""
    
    def __init__(self):
        """Initialize the agentic repository"""
        self.message_chunk_size = MESSAGE_CHUNK_SIZE
        self.document_repo = get_document_repository()
        self.slack_repo = get_slack_repository()
        self._agent = None
    
    def _get_agent(self) -> EpimetheusAgent:
        """Get or create the agent instance"""
        if self._agent is None:
            self._agent = EpimetheusAgent()
        return self._agent
    
    def process_mention(
        self,
        message_text: str,
        event: Dict[str, Any],
        team_id: str,
        channel: str,
        thread_ts: str
    ) -> str:
        """
        Process a mention command using agentic behavior.
        Reads channel history for context and processes the command.
        
        Args:
            message_text: The user's message text (without mentions)
            event: Slack event dictionary
            team_id: Slack team ID
            channel: Slack channel ID
            thread_ts: Thread timestamp
            
        Returns:
            Reply text to send to the user
        """
        # Extract document mention
        doc_id = extract_document_mention(event.get("text", ""))
        
        # If no document ID found, try RAG search
        if not doc_id:
            try:
                if self.document_repo:
                    search_results = self.document_repo.search_similar_documents(message_text, n_results=1)
                    if search_results and search_results.get('ids') and search_results['ids'][0]:
                        first_chunk_id = search_results['ids'][0][0]
                        doc_id = extract_doc_id_from_chunk_id(first_chunk_id)
            except Exception:
                pass
        
        # Always use agent to generate response
        try:
            agent = self._get_agent()
            response = agent.run(message_text, event, team_id)
            return response or DEFAULT_PROCESSING_ERROR_MESSAGE
        except Exception as e:
            traceback.print_exc()
            return f"Error processing your request: {str(e)}"


# ============================================================================
# Singleton instances
# ============================================================================

_agent_instance = None
_agentic_repository = None


def get_agent(base_llm_kwargs: Dict[str, Any] = None) -> EpimetheusAgent:
    """
    Get or create the agent singleton.
    
    Args:
        base_llm_kwargs: Optional base LLM configuration
    
    Returns:
        EpimetheusAgent instance
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EpimetheusAgent(base_llm_kwargs)
    return _agent_instance


def run_agent(message: str, event: Dict[str, Any], team_id: str) -> str:
    """
    Convenience function to run the agent.
    
    Args:
        message: User's message
        event: Slack event
        team_id: Slack team ID
    
    Returns:
        Agent's response
    """
    agent = get_agent()
    return agent.run(message, event, team_id)


def get_agentic_repository() -> AgenticRepository:
    """Get or create the agentic repository singleton"""
    global _agentic_repository
    if _agentic_repository is None:
        _agentic_repository = AgenticRepository()
    return _agentic_repository
