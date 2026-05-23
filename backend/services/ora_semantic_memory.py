"""
services/ora_semantic_memory.py — iter 331a Sprint 3.7 (Gap 2)

Intent-based memory retrieval using SQLite FTS5 (BM25-ranked).

Why FTS5 and not real vector embeddings?
  - sqlite-vec is installed but needs a transformer model to produce
    vectors. Real sentence-transformers is 200 MB+ — too heavy for a
    "no new dependency" requirement, and would need a GPU on Hetzner.
  - SQLite FTS5 is built-in to Python's sqlite3 (no extension needed).
  - BM25 ranking is a proper IR algorithm — strictly better than
    substring keyword matching.
  - Returns ranked snippets, not full files. Token cost goes from
    ~3000 chars/file injected → ~400 chars/snippet.
  - Portable to any platform with no extra setup.

When AUREM gets more memory headroom (or moves off this container),
swap this module's `query()` body for a vector-based one — same API.

Public API:
    reindex()                          → builds the FTS5 table
    semantic_memory_search(q, top_k=3) → returns ranked chunks
    last_reindex_time()                → epoch float
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────
_MEMORY_ROOT = Path(os.environ.get("ORA_MEMORY_ROOT", "/app/memory"))
_INDEX_PATH  = _MEMORY_ROOT / "semantic_index.db"
_SKILLS_DIR  = Path(os.environ.get("ORA_SKILLS_DIR", "/app/backend/ora_skills"))

_CHUNK_SIZE  = 600  # chars per chunk
_CHUNK_OVERLAP = 80

_LAST_INDEX_TS = 0.0


# ── Index build ─────────────────────────────────────────────────────

def _all_md_files() -> list[Path]:
    """Every .md file inside memory/* and ora_skills/. Symlinks resolved
    so we don't double-index the backward-compat symlinks at /app/memory."""
    seen: set[Path] = set()
    out: list[Path] = []
    for root in (_MEMORY_ROOT / "tier1", _MEMORY_ROOT / "tier2",
                  _MEMORY_ROOT / "tier3", _SKILLS_DIR):
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            try:
                real = p.resolve()
            except Exception:
                continue
            if real in seen:
                continue
            seen.add(real)
            out.append(p)
    return out


def _chunk_text(text: str, size: int = _CHUNK_SIZE,
                  overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Sliding-window chunks. Splits on paragraph boundaries when possible."""
    text = text.replace("\r\n", "\n")
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    i = 0
    while i < len(text):
        end = min(i + size, len(text))
        # Try to back up to a paragraph or sentence boundary.
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                idx = text.rfind(sep, i + size // 2, end)
                if idx > i:
                    end = idx + len(sep)
                    break
        chunks.append(text[i:end])
        if end >= len(text):
            break
        i = max(i + 1, end - overlap)
    return chunks


def reindex(force: bool = False) -> dict:
    """(Re)build the FTS5 index from all memory + skill .md files.

    Returns counts so the caller can log them.
    """
    files = _all_md_files()
    conn = sqlite3.connect(str(_INDEX_PATH))
    try:
        cur = conn.cursor()
        # Drop+recreate is cheap and avoids stale entries.
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute("""
            CREATE VIRTUAL TABLE chunks
            USING fts5(file_path, label, chunk_idx UNINDEXED, body,
                       tokenize = 'porter unicode61');
        """)
        n_files = 0
        n_chunks = 0
        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace").strip()
            except Exception as e:
                logger.debug(f"[semantic] skip {fp}: {e}")
                continue
            if not text:
                continue
            label = fp.stem.replace("_", " ").replace("-", " ")
            for idx, chunk in enumerate(_chunk_text(text)):
                cur.execute(
                    "INSERT INTO chunks (file_path, label, chunk_idx, body) "
                    "VALUES (?, ?, ?, ?)",
                    (str(fp), label, idx, chunk),
                )
                n_chunks += 1
            n_files += 1
        conn.commit()
    finally:
        conn.close()
    global _LAST_INDEX_TS
    _LAST_INDEX_TS = time.time()
    logger.info(
        f"[semantic] FTS5 reindex complete — {n_files} files, "
        f"{n_chunks} chunks, db at {_INDEX_PATH}"
    )
    return {"ok": True, "files_indexed": n_files,
             "chunks_indexed": n_chunks, "db_path": str(_INDEX_PATH)}


def last_reindex_time() -> float:
    return _LAST_INDEX_TS


# ── Query ───────────────────────────────────────────────────────────

# FTS5 has a strict syntax — quote unsafe chars / treat the user query
# as a simple OR of terms.
_FTS_SAFE_RE = re.compile(r"[A-Za-z0-9_]+")


def _fts_query_from(q: str) -> str:
    tokens = _FTS_SAFE_RE.findall(q or "")
    # Lowercase, dedup, drop very short tokens.
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        t = t.lower()
        if len(t) < 2 or t in seen:
            continue
        seen.add(t)
        out.append(t)
    if not out:
        return ""
    # `term1 OR term2 OR …` so any keyword match scores.
    return " OR ".join(out)


async def semantic_memory_search(query: str, top_k: int = 3) -> dict:
    """Return the top-k BM25-ranked chunks across all memory files.

    Args:
        query:  natural-language query
        top_k:  hard-capped at 10
    """
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "query is empty", "results": []}
    if not _INDEX_PATH.exists():
        # Lazy-build the index on first call.
        reindex()
    fts = _fts_query_from(q)
    if not fts:
        return {"ok": False, "error": "no searchable tokens in query",
                 "results": []}
    k = max(1, min(int(top_k or 3), 10))
    conn = sqlite3.connect(str(_INDEX_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_path, label, chunk_idx, body, rank "
            "FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT ?",
            (fts, k),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        return {"ok": False, "error": f"fts query failed: {e}",
                 "results": []}
    finally:
        conn.close()
    results: list[dict] = []
    for file_path, label, chunk_idx, body, rank in rows:
        results.append({
            "file":     file_path,
            "label":    label,
            "chunk":    int(chunk_idx),
            "score":    float(rank) if rank is not None else None,
            "snippet":  body[:800],
        })
    return {
        "ok":         True,
        "query":      q,
        "fts_query":  fts,
        "top_k":      k,
        "count":      len(results),
        "results":    results,
    }


# ── Registry patch ──────────────────────────────────────────────────

TOOL_REGISTRY_PATCH = {
    "semantic_memory_search": {
        "fn": semantic_memory_search,
        "args_spec": {
            "query": "str — natural language query",
            "top_k": "int — number of chunks to return (1-10)",
        },
        "description": (
            "TIER 1 (auto, read-only). Search ORA's memory + skills "
            "with BM25 ranking. Returns ranked snippets, not full files "
            "— much cheaper than dumping every tier-2 doc. Use this "
            "when you need specific knowledge from memory."
        ),
    },
}


def splice_into(tool_registry: dict) -> int:
    tool_registry.update(TOOL_REGISTRY_PATCH)
    return len(TOOL_REGISTRY_PATCH)
