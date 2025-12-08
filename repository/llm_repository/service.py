"""
LLM Service Module
Contains the implementation of the LLMRepository class using LangChain.
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Import prompt functions
# Note: We use relative import assuming prompts.py is in the same folder
from .prompts import (
    document_update_prompt,
    change_summary_prompt,
    question_answering_prompt,
    intent_classification_prompt,
    knowledge_extraction_prompt,
)

load_dotenv()


class LLMRepository:
    """Repository for LLM operations using LangChain"""

    def __init__(self):
        """Initialize the LLM repository with LangChain ChatOpenAI"""
        openai_base_url = os.environ.get("OPENAI_BASE_URL")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")

        if not openai_api_key:
            raise Exception("OPENAI_API_KEY not configured")

        # Store base config for creating LLM instances per call
        self.base_llm_kwargs = {
            "model": openai_model,
            "api_key": openai_api_key,
            "temperature": 0.3,
        }

        # Add base_url if provided (for OpenRouter or custom endpoints)
        if openai_base_url:
            self.base_llm_kwargs["base_url"] = openai_base_url

    def generate_document_update(
        self,
        old_content: str,
        new_messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4000,
    ) -> str:
        """
        Generate updated document content using LangChain.
        """
        # Get prompt from prompts module
        prompt_text = document_update_prompt(old_content, new_messages)

        # Create messages for LangChain
        messages = [
            SystemMessage(content="You are a technical documentation expert."),
            HumanMessage(content=prompt_text),
        ]

        # Create LLM instance with specific parameters for this call
        llm_kwargs = {**self.base_llm_kwargs, "temperature": temperature}
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens

        llm = ChatOpenAI(**llm_kwargs)

        # Generate response using LangChain
        response = llm.invoke(messages)

        # Handle empty or None responses
        if not response or not hasattr(response, "content"):
            return "Document updated successfully."

        content = response.content.strip() if response.content else ""

        # Return a default message if content is empty
        if not content:
            return "Document updated successfully."

        return content

    def generate_change_summary(
        self,
        old_content: str,
        new_content: str,
        new_messages: List[Dict[str, Any]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = 200,
    ) -> str:
        """
        Generate a summary of document changes using LangChain.
        """
        # Get prompt from prompts module
        prompt_text = change_summary_prompt(old_content, new_content, new_messages)

        # Create messages for LangChain
        messages = [
            SystemMessage(
                content="You are a technical documentation expert who writes clear, concise summaries."
            ),
            HumanMessage(content=prompt_text),
        ]

        # Create LLM instance with specific parameters for this call
        llm_kwargs = {**self.base_llm_kwargs, "temperature": temperature}
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens

        llm = ChatOpenAI(**llm_kwargs)

        # Generate response using LangChain
        response = llm.invoke(messages)

        # Handle empty or None responses
        if not response or not hasattr(response, "content"):
            return "Document updated successfully."

        content = response.content.strip() if response.content else ""

        # Return a default message if content is empty
        if not content:
            return "Document updated successfully."

        return content

    def answer_question(
        self,
        question: str,
        relevant_chunks: List[str],
        document_context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
    ) -> str:
        """
        Answer a question based on relevant document chunks using LangChain.
        """
        # Get prompt from prompts module
        prompt_text = question_answering_prompt(
            question, relevant_chunks, document_context
        )

        # Create messages for LangChain
        messages = [
            SystemMessage(
                content="You are a helpful AI assistant that answers questions based on technical documentation."
            ),
            HumanMessage(content=prompt_text),
        ]

        # Create LLM instance with specific parameters for this call
        llm_kwargs = {**self.base_llm_kwargs, "temperature": temperature}
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens

        llm = ChatOpenAI(**llm_kwargs)

        # Generate response using LangChain
        response = llm.invoke(messages)

        # Handle empty or None responses
        if not response or not hasattr(response, "content"):
            return "Document updated successfully."

        content = response.content.strip() if response.content else ""

        # Return a default message if content is empty
        if not content:
            return "Document updated successfully."

        return content

    def classify_intent(
        self, message: str, temperature: float = 0.1, max_tokens: Optional[int] = 10
    ) -> str:
        """
        Classify user intent to determine if they want to ask a question or update documentation.
        """
        # Get prompt from prompts module
        prompt_text = intent_classification_prompt(message)

        # Create messages for LangChain
        messages = [
            SystemMessage(
                content="You are an AI assistant that classifies user intent. Respond with only ASK_QUESTION or UPDATE_DOCUMENT."
            ),
            HumanMessage(content=prompt_text),
        ]

        # Create LLM instance with specific parameters for this call
        llm_kwargs = {**self.base_llm_kwargs, "temperature": temperature}
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens

        llm = ChatOpenAI(**llm_kwargs)

        # Generate response using LangChain
        response = llm.invoke(messages)

        # Parse and normalize the response
        intent = response.content.strip().upper()
        if "ASK_QUESTION" in intent or "QUESTION" in intent:
            return "ASK_QUESTION"
        elif "UPDATE_DOCUMENT" in intent or "UPDATE" in intent:
            return "UPDATE_DOCUMENT"
        else:
            # Default fallback: check for question patterns
            if "?" in message or any(
                word in message.lower()
                for word in [
                    "what",
                    "how",
                    "why",
                    "when",
                    "where",
                    "who",
                    "explain",
                    "tell me",
                ]
            ):
                return "ASK_QUESTION"
            return "UPDATE_DOCUMENT"

    def extract_knowledge(
        self,
        conversation_text: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 500,
    ) -> str:
        """
        Extract knowledge from a Slack conversation using LangChain.
        """
        # Get prompt from prompts module
        prompt_text = knowledge_extraction_prompt(conversation_text)

        # Create messages for LangChain
        messages = [
            SystemMessage(
                content="You are a knowledge extraction system that analyzes conversations to identify information worth documenting."
            ),
            HumanMessage(content=prompt_text),
        ]

        # Create LLM instance with specific parameters for this call
        llm_kwargs = {**self.base_llm_kwargs, "temperature": temperature}
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens

        llm = ChatOpenAI(**llm_kwargs)

        # Generate response using LangChain
        response = llm.invoke(messages)

        # Handle empty or None responses
        if not response or not hasattr(response, "content"):
            return "Document updated successfully."

        content = response.content.strip() if response.content else ""

        # Return a default message if content is empty
        if not content:
            return "Document updated successfully."

        return content
