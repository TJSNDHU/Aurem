"""
ORA Knowledge Sync Router
==========================
Force Knowledge Sync button for admin panel.
Re-crawls all training docs, re-embeds, upserts to vector collection.
Shows: last sync time + doc count.
"""

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
import jwt as pyjwt
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ora/knowledge", tags=["ORA Knowledge Sync"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

db = None


def set_db(database):
    global db
    db = database


def _get_user_id(authorization: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        return "anonymous"
    try:
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("user_id", payload.get("id", "anonymous"))
    except Exception:
        return "anonymous"


@router.get("/status")
async def knowledge_sync_status(authorization: str = Header(None)):
    """Get current knowledge sync status — last sync time and doc count."""
    try:
        from server import db as _db

        sync_doc = await _db.ora_knowledge_sync.find_one(
            {}, {"_id": 0}
        )

        training_count = await _db.ora_training_files.count_documents({"status": {"$in": ["crawled", "processed", "ready"]}})
        embedded_count = await _db.ora_knowledge_vectors.count_documents({})

        return {
            "last_sync": sync_doc.get("synced_at") if sync_doc else None,
            "docs_synced": sync_doc.get("docs_count", 0) if sync_doc else 0,
            "total_training_files": training_count,
            "total_vectors": embedded_count,
            "sync_duration": sync_doc.get("duration_ms", 0) if sync_doc else 0,
            "status": "synced" if sync_doc else "never_synced",
        }
    except Exception as e:
        logger.error(f"[KnowledgeSync] Status error: {e}")
        return {
            "last_sync": None,
            "docs_synced": 0,
            "total_training_files": 0,
            "total_vectors": 0,
            "status": "error",
        }


@router.post("/force-sync")
async def force_knowledge_sync(authorization: str = Header(None)):
    """
    Force sync: re-crawl all training docs, re-embed, upsert to vector collection.
    Returns: sync result with doc count and duration.
    """
    try:
        from server import db as _db
        from services.embeddings import embed_text
        import time

        user_id = _get_user_id(authorization)
        start = time.time()

        # 1. Get all training files
        cursor = _db.ora_training_files.find(
            {"status": {"$in": ["crawled", "processed", "ready"]}},
            {"_id": 0, "file_id": 1, "crawled_text": 1, "filename": 1, "source_type": 1, "url": 1}
        )
        training_docs = await cursor.to_list(length=500)

        if not training_docs:
            return {
                "success": True,
                "docs_synced": 0,
                "message": "No training documents found to sync.",
                "duration_ms": 0,
            }

        # 2. Re-embed each document and upsert to vector collection
        synced = 0
        errors = 0
        for doc in training_docs:
            text = doc.get("crawled_text", "")
            if not text or len(text.strip()) < 10:
                continue

            try:
                # Chunk text for embedding (max 512 tokens per chunk)
                chunks = _chunk_text(text, max_chars=2000)
                for i, chunk in enumerate(chunks):
                    embedding = embed_text(chunk)
                    if embedding and any(v != 0.0 for v in embedding):
                        await _db.ora_knowledge_vectors.update_one(
                            {"file_id": doc["file_id"], "chunk_index": i},
                            {"$set": {
                                "file_id": doc["file_id"],
                                "chunk_index": i,
                                "filename": doc.get("filename", ""),
                                "source_type": doc.get("source_type", ""),
                                "text": chunk,
                                "embedding": embedding,
                                "synced_at": datetime.now(timezone.utc).isoformat(),
                            }},
                            upsert=True,
                        )
                synced += 1
            except Exception as e:
                errors += 1
                logger.warning(f"[KnowledgeSync] Embed error for {doc.get('file_id')}: {e}")

        duration_ms = int((time.time() - start) * 1000)

        # 3. Update sync record
        await _db.ora_knowledge_sync.update_one(
            {},
            {"$set": {
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "docs_count": synced,
                "errors": errors,
                "duration_ms": duration_ms,
                "triggered_by": user_id,
            }},
            upsert=True,
        )

        # 4. Invalidate live context cache for fresh knowledge status
        try:
            from services.ora_live_context import invalidate_tenant_cache
            invalidate_tenant_cache("aurem_platform")
        except Exception:
            pass

        return {
            "success": True,
            "docs_synced": synced,
            "errors": errors,
            "duration_ms": duration_ms,
            "message": f"{synced} docs synced in {duration_ms / 1000:.1f}s",
        }

    except Exception as e:
        logger.error(f"[KnowledgeSync] Force sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _chunk_text(text: str, max_chars: int = 2000) -> list:
    """Split text into chunks for embedding."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        # Try to split at paragraph or sentence boundary
        if len(text) <= max_chars:
            chunks.append(text)
            break
        # Find last newline within max_chars
        split_at = text.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = text.rfind(". ", 0, max_chars)
        if split_at < max_chars // 4:
            split_at = max_chars
        chunks.append(text[:split_at + 1].strip())
        text = text[split_at + 1:].strip()
    return [c for c in chunks if c]
