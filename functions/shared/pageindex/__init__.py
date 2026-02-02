"""
PageIndex - Vectorless reasoning-based retrieval module.

This module implements a PageIndex-style retrieval system that uses LLM reasoning
to navigate a hierarchical index structure instead of vector similarity search.

Components:
- IndexLoader: Loads and caches the index from JSON files
- Navigator: LLM-based navigation through the index hierarchy
- PageIndexRetriever: Main retrieval class combining navigation and extraction
"""

from .index_loader import IndexLoader
from .retrieval import PageIndexRetriever, RetrievalResult, NavigationState

__all__ = [
    "IndexLoader",
    "PageIndexRetriever",
    "RetrievalResult",
    "NavigationState",
]
