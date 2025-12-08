"""
LLM Repository Package
"""

from typing import Dict, Any, Optional

# Import the implementation class
from .service import LLMRepository

# Singleton instance
_llm_repository: Optional[LLMRepository] = None


def get_llm_repository() -> LLMRepository:
    """Get or create the singleton LLM repository instance"""
    global _llm_repository
    if _llm_repository is None:
        _llm_repository = LLMRepository()
    return _llm_repository


# Lazy imports for agentic functionality to avoid circular dependencies
def get_agentic_repository():
    """Get agentic repository (lazy import)"""
    from .agentic import get_agentic_repository as _get_agentic_repository

    return _get_agentic_repository()


def get_agent(base_llm_kwargs: Dict[str, Any] = None):
    """Get agent (lazy import)"""
    from .agentic import get_agent as _get_agent

    return _get_agent(base_llm_kwargs)


def run_agent(message: str, event: Dict[str, Any], team_id: str) -> str:
    """Run agent (lazy import)"""
    from .agentic import run_agent as _run_agent

    return _run_agent(message, event, team_id)


__all__ = [
    "LLMRepository",
    "get_llm_repository",
    "get_agentic_repository",
    "get_agent",
    "run_agent",
]
