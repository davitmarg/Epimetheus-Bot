"""
Prompt Management Module

Central place to manage all prompts used in the LLM repository.
Each prompt is a function that takes input arguments, formats them into prompt text,
and returns a string for use with LangChain.
"""

from typing import List, Dict, Any, Optional


def document_update_prompt(old_content: str, new_messages: List[Dict[str, Any]]) -> str:
    """
    Generate a prompt for updating technical documentation based on Slack conversations.
    
    Args:
        old_content: Current document content
        new_messages: List of message dictionaries with 'user', 'text', 'ts' keys
    
    Returns:
        Formatted prompt string
    """
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
3. Maintains proper formatting and structure (headings, paragraphs, lists, etc.)
4. Preserves Google Docs formatting elements including:
   - Bold and italic text styling
   - Heading levels and hierarchy
   - Bullet points and numbered lists
   - Paragraph breaks and spacing
   - Code blocks and inline code formatting
5. Removes any outdated information that conflicts with the new information
6. Ensures the document is clear, comprehensive, and up-to-date

IMPORTANT: You can use markdown formatting in your output, which will be automatically converted to Google Docs formatting:
- Use # for headings (# H1, ## H2, ### H3, etc.)
- Use **text** or __text__ for bold
- Use *text* or _text_ for italic
- Use - or * for bullet lists
- Use 1. 2. 3. for numbered lists
- Use `code` for inline code

When updating the document, maintain the existing formatting structure. If the document has headings, keep them. If text is bold or italic, preserve that styling.

Return ONLY the updated document content with markdown formatting, without any explanations."""
    
    return prompt


def change_summary_prompt(old_content: str, new_content: str, new_messages: List[Dict[str, Any]], doc_id: Optional[str] = None) -> str:
    """
    Generate a prompt for summarizing changes made to technical documentation.
    
    Args:
        old_content: Original document content (first 500 chars will be used)
        new_content: Updated document content (first 500 chars will be used)
        new_messages: List of message dictionaries with 'user', 'text' keys
        doc_id: Optional document ID to include a link in the summary
    
    Returns:
        Formatted prompt string
    """
    # Format messages for context
    message_context = []
    for msg in new_messages[:5]:  # Limit to first 5 messages for summary
        user = msg.get('user', 'unknown')
        text = msg.get('text', '')
        message_context.append(f"{user}: {text}")
    
    messages_text = "\n".join(message_context)
    
    # Build document link instruction if doc_id is provided
    doc_link_instruction = ""
    if doc_id:
        doc_url = f"https://docs.google.com/document/d/{doc_id}"
        doc_link_instruction = f"\n\nIMPORTANT: Always end your summary with the document link. Format it as: \"View document: {doc_url}\""
    
    prompt = f"""You are an AI assistant that summarizes changes made to technical documentation.

Original Document Content (first 500 chars):
{old_content[:500]}

Updated Document Content (first 500 chars):
{new_content[:500]}

New Information from Slack Conversations:
{messages_text}

Please generate a brief, concise summary (2-3 sentences) describing what changed in the document based on the new information. Focus on:
- What new information was added
- What sections were updated
- Key changes or improvements{doc_link_instruction}

Return ONLY the summary text, without any formatting or markdown."""
    
    return prompt


def question_answering_prompt(question: str, relevant_chunks: List[str], document_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a prompt for answering questions based on document content.
    
    Args:
        question: The user's question
        relevant_chunks: List of relevant document chunks from vector search
        document_context: Optional dict with document metadata (name, doc_id, etc.)
    
    Returns:
        Formatted prompt string
    """
    # Combine relevant chunks
    context_text = "\n\n".join([f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(relevant_chunks)])
    
    # Add document context if available
    context_info = ""
    if document_context:
        doc_name = document_context.get('name', 'Unknown')
        doc_id = document_context.get('doc_id', '')
        if doc_id:
            doc_url = f"https://docs.google.com/document/d/{doc_id}"
            context_info = f"\n\nDocument: {doc_name}\nLink: {doc_url}"
    
    prompt = f"""You are a helpful AI assistant that answers questions based on technical documentation.

User Question:
{question}

Relevant Documentation Context:
{context_text}{context_info}

Please provide a clear, accurate answer to the question based on the documentation provided above. 
- If the answer is found in the documentation, provide a detailed answer with relevant details
- If the answer is not fully covered in the documentation, say so and provide what information is available
- If the documentation doesn't contain relevant information, politely indicate that the answer isn't in the available documentation
- Be concise but thorough
- Use bullet points or formatting when helpful for clarity

Return ONLY your answer, without any preamble or "Based on the documentation" phrases."""
    
    return prompt


def intent_classification_prompt(message: str) -> str:
    """
    Generate a prompt for classifying user intent - whether they want to ask a question
    or provide information to update documentation.
    
    Args:
        message: The user's message text
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are an AI assistant that analyzes user messages to determine their intent.

User Message:
{message}

Analyze this message and determine the user's primary intent. The user can either:
1. ASK_QUESTION - They want to ask a question about existing documentation and get an answer
2. UPDATE_DOCUMENT - They want to provide new information or updates that should be added to documentation

Consider these indicators:
- Questions (with "?", question words like "what", "how", "why", "explain", "tell me") → ASK_QUESTION
- Statements providing new information, updates, corrections, or facts → UPDATE_DOCUMENT
- Requests for information retrieval → ASK_QUESTION
- Sharing knowledge, updates, or corrections → UPDATE_DOCUMENT
- Ambiguous cases: If the message could be both, prefer ASK_QUESTION if it contains question words or "?", otherwise prefer UPDATE_DOCUMENT

Respond with ONLY one of these two words: ASK_QUESTION or UPDATE_DOCUMENT
Do not include any explanation or additional text."""
    return prompt


def knowledge_extraction_prompt(conversation_text: str) -> str:
    """
    Generate a prompt for extracting knowledge from Slack conversations.
    
    Args:
        conversation_text: Formatted conversation text with timestamps and users
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""Analyze the following Slack conversation and extract key knowledge, facts, updates, or information that might be relevant for technical documentation.

Conversation:
{conversation_text}

Please extract:
1. Key facts, information, or knowledge shared
2. Updates or corrections mentioned
3. New information that should be documented
4. Technical details or procedures discussed

If there is no substantial knowledge or information worth documenting, respond with "NO_NEW_INFORMATION".
Otherwise, provide a concise summary of the knowledge extracted.

Response:"""
    
    return prompt


def document_formatting_prompt(old_content: str, formatting_instructions: str) -> str:
    """
    Generate a prompt for updating document formatting without changing content.
    
    Args:
        old_content: Current document content
        formatting_instructions: Instructions for formatting changes
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are a document formatting expert. Update the formatting of the following document based on the instructions, while preserving ALL content exactly as written.

Current Document Content:
{old_content}

Formatting Instructions:
{formatting_instructions}

Please apply the formatting changes while:
1. Preserving ALL text content exactly as written (do not change, add, or remove any words)
2. Applying the requested formatting (headings, bold, italic, lists, etc.)
3. Maintaining document structure and readability
4. Using appropriate Google Docs formatting conventions

You can use markdown formatting in your output:
- Use # for headings (# H1, ## H2, ### H3, etc.)
- Use **text** or __text__ for bold
- Use *text* or _text_ for italic
- Use - or * for bullet lists
- Use 1. 2. 3. for numbered lists
- Use `code` for inline code

Return ONLY the formatted document content with markdown formatting applied."""
    
    return prompt


def agent_system_prompt() -> str:
    """
    Generate the system prompt for the Epimetheus agent.
    
    Returns:
        System prompt string for the agent
    """
    return """You are Epimetheus, an AI assistant that helps manage technical documentation.

Your available tools and when to use them:

1. answer_question_from_documentation - Use when users ask questions about existing documentation
2. update_documentation_with_information - Use when users provide new information, updates, or corrections to add to documentation
3. get_document_count - Use when users ask how many documents exist or want a document count
4. list_all_documents - Use when users ask to list documents, show all documents, or see what documents are available
5. get_document_last_updated - Use when users ask about when documents were last updated or modified
6. search_documents_by_name_or_content - Use when users want to find a specific document by searching for its name or content keywords. Returns document IDs.
7. update_document_formatting - Use when users want to improve or fix document formatting (headings, bold, italic, lists) without changing content
8. update_document_partial - Use when users want to update only a specific section of a document (preserves formatting and enables versioning)

Guidelines:
- Be helpful, clear, and concise in your responses
- Choose the appropriate tool based on the user's intent
- When updating documents, you can use markdown formatting which will be automatically converted to Google Docs formatting:
  * Use # for headings (# H1, ## H2, ### H3, etc.)
  * Use **text** or __text__ for bold
  * Use *text* or _text_ for italic
  * Use - or * for bullet lists
  * Use 1. 2. 3. for numbered lists
  * Use `code` for inline code
- For questions → use answer_question_from_documentation
- For providing information → use update_documentation_with_information
- For listing documents → use list_all_documents
- For finding specific documents → use search_documents_by_name_or_content
- For formatting improvements → use update_document_formatting
- For partial updates → use update_document_partial
- For document statistics → use get_document_count or get_document_last_updated"""
