"""
AUREM LightRAG Adapter — Graph+Vector Hybrid RAG for Hermes
============================================================
Wraps lightrag-hku library using Emergent LLM key for entity extraction.
Falls back to Memobase when LightRAG unavailable.
"""
import os
import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_rag = None
_initialized = False
LIGHTRAG_DIR = "/app/backend/data/lightrag_store"


async def _emergent_llm_complete(prompt, system_prompt=None, history_messages=None, **kwargs):
    """LLM completion via Emergent integrations."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key:
            return ""
        sys_msg = system_prompt or "You are a knowledge graph entity extraction assistant. Extract entities and relationships from text."
        chat = LlmChat(api_key=api_key, session_id="lightrag_extract", system_message=sys_msg)
        msg = UserMessage(text=prompt[:4000])
        response = await chat.send_message(msg)
        return response if isinstance(response, str) else str(response)
    except Exception as e:
        logger.warning(f"[LIGHTRAG] LLM call failed: {e}")
        return ""


async def _simple_embed(texts: list[str]) -> np.ndarray:
    """Simple embedding using existing embeddings service."""
    try:
        from services.embeddings import embed_texts
        vectors = embed_texts(texts)
        return np.array(vectors)
    except Exception:
        # Return zero vectors as fallback
        return np.zeros((len(texts), 384))


async def _get_rag():
    """Lazy-init LightRAG instance."""
    global _rag, _initialized
    if _initialized:
        return _rag
    _initialized = True
    try:
        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key:
            logger.info("[LIGHTRAG] No LLM_API_KEY — running in fallback mode")
            return None

        try:
            from lightrag import LightRAG, QueryParam  # noqa: F401
            from lightrag.utils import EmbeddingFunc
        except ImportError:
            # iter 282al-28 — lightrag-hku is an optional heavy dependency
            # (~150MB torch+transformers). On deploy targets with tight
            # memory budgets it's intentionally NOT installed. Fail
            # silently into Memobase fallback rather than spamming WARNINGs.
            logger.info("[LIGHTRAG] Package not installed — Memobase fallback active")
            return None

        os.makedirs(LIGHTRAG_DIR, exist_ok=True)
        _rag = LightRAG(
            working_dir=LIGHTRAG_DIR,
            llm_model_func=_emergent_llm_complete,
            embedding_func=EmbeddingFunc(
                embedding_dim=384,
                max_token_size=512,
                func=_simple_embed,
            ),
        )
        await _rag.initialize_storages()
        logger.info("[LIGHTRAG] Initialized with Emergent LLM key — graph+vector hybrid active")
        return _rag
    except Exception as e:
        logger.warning(f"[LIGHTRAG] Init failed (falling back to Memobase): {e}")
        _rag = None
        return None


async def insert_knowledge(text: str, metadata: Dict = None) -> Dict:
    """Insert text into LightRAG knowledge graph."""
    rag = await _get_rag()
    if not rag:
        return {"inserted": False, "reason": "lightrag_not_available"}
    try:
        await rag.ainsert(text)
        return {"inserted": True, "text_length": len(text), "engine": "lightrag"}
    except Exception as e:
        logger.warning(f"[LIGHTRAG] Insert failed: {e}")
        return {"inserted": False, "reason": str(e)}


async def hybrid_query(query: str, mode: str = "hybrid") -> Dict:
    """Query using graph+vector hybrid retrieval."""
    rag = await _get_rag()
    if not rag:
        return await _memobase_fallback(query)
    try:
        from lightrag import QueryParam
        result = await rag.aquery(query, param=QueryParam(mode=mode))
        return {"answer": result, "mode": mode, "engine": "lightrag"}
    except Exception as e:
        logger.warning(f"[LIGHTRAG] Query failed: {e}")
        return await _memobase_fallback(query)


async def _memobase_fallback(query: str) -> Dict:
    """Fallback to existing Memobase."""
    try:
        from services.memobase import semantic_recall
        results = await semantic_recall("aurem_platform", query, limit=3)
        combined = " ".join([r.get("content", "") for r in results])
        return {"answer": combined, "mode": "memobase_fallback", "engine": "memobase", "sources": len(results)}
    except Exception:
        return {"answer": "", "mode": "fallback_failed", "engine": "none"}


async def get_stats() -> Dict:
    """Get LightRAG knowledge graph stats."""
    rag = await _get_rag()
    if not rag:
        has_key = bool(os.environ.get("LLM_API_KEY", ""))
        return {"status": "not_initialized", "has_llm_key": has_key,
                "reason": "init_pending" if has_key else "no_llm_key"}
    try:
        kg_path = os.path.join(LIGHTRAG_DIR, "graph_chunk_entity_relation.graphml")
        has_graph = os.path.exists(kg_path)
        graph_size = os.path.getsize(kg_path) if has_graph else 0
        return {"status": "active", "engine": "lightrag", "graph_exists": has_graph,
                "graph_size_bytes": graph_size, "working_dir": LIGHTRAG_DIR}
    except Exception as e:
        return {"status": "error", "error": str(e)}
