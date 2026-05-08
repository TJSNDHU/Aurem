"""
AUREM Centralized Embedding Service
====================================
Attempts to use sentence-transformers locally. Falls back to a no-op
embedding if the ML dependencies are unavailable (e.g., on
resource-constrained deployments).
"""

import logging
import os
from typing import List

# Suppress HuggingFace unauthenticated request warnings in production
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

# Suppress the specific HF Hub warning about unauthenticated requests
import warnings
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

logger = logging.getLogger(__name__)

_model = None
# Opt-in only: production K8s pods have no GPU and no CUDA libs. Loading
# `sentence_transformers` triggers torch initialization which (a) takes
# 10-30s the first time, (b) tries to dlopen libcublas, (c) blocks the
# event loop the first time embed_text() is called from a request handler
# — which is precisely how the K8s liveness probe times out.
# Set `AUREM_EMBEDDINGS_ENABLED=1` only when running on a node that has
# torch + the model file pre-warmed (e.g. dedicated worker, not the
# web pod).
_ml_available = os.environ.get("AUREM_EMBEDDINGS_ENABLED", "").strip() in ("1", "true", "yes")
if not _ml_available:
    logger.info("[Embeddings] Disabled by default (set AUREM_EMBEDDINGS_ENABLED=1 to enable). Semantic search will use fallback no-op vectors.")
EMBEDDING_DIM = 384
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_VERSION = "v2"


def _load_model():
    global _model, _ml_available
    if _model is not None:
        return _model
    if not _ml_available:
        return None

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info(f"[Embeddings] Model '{EMBEDDING_MODEL_NAME}' loaded ({EMBEDDING_DIM}d)")
        return _model
    except Exception as e:
        _ml_available = False
        logger.warning(f"[Embeddings] ML model unavailable, semantic search disabled: {e}")
        # Log to sentinel_alerts so ORA Brain sees it (Phase 0 — no silent swallow)
        err_msg = str(e)[:300]
        try:
            import asyncio
            from datetime import datetime, timezone
            try:
                import server
                _db = getattr(server, "db", None)
            except Exception:
                _db = None
            if _db is not None:
                async def _alert(msg=err_msg, db=_db):
                    await db.sentinel_alerts.insert_one({
                        "kind": "embeddings_unavailable",
                        "error": msg,
                        "advisory": True,
                        "ts": datetime.now(timezone.utc),
                    })
                try:
                    asyncio.get_event_loop().create_task(_alert())
                except Exception:
                    pass
        except Exception:
            pass
        return None


def embed_text(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    model = _load_model()
    if model is None:
        return [0.0] * EMBEDDING_DIM

    try:
        return model.encode(text).tolist()
    except Exception as e:
        logger.error(f"[Embeddings] encode() failed: {e}")
        return [0.0] * EMBEDDING_DIM


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    model = _load_model()
    if model is None:
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    try:
        vectors = model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vectors]
    except Exception as e:
        logger.error(f"[Embeddings] batch encode() failed: {e}")
        return [[0.0] * EMBEDDING_DIM for _ in texts]
