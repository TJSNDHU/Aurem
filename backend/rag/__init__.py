# RAG Module for WhatsApp AI
from .retriever import (
    init_retriever,
    retrieve_context,
    build_rag_system_prompt,
    get_retriever_status
)
from .embedder import (
    refresh_index,
    ensure_index,
    get_index_stats
)

__all__ = [
    'init_retriever',
    'retrieve_context', 
    'build_rag_system_prompt',
    'get_retriever_status',
    'refresh_index',
    'ensure_index',
    'get_index_stats'
]
