"""
services/codebase_semantic_search.py — iter 326bb (Phase 2 P1.4).

Semantic codebase search. Cursor's @codebase uses embeddings; AUREM's
codebase is ~500 Python files, so a fast in-process AST + fuzzy match
gives ORA the same intent-based search ("find code that calculates
subscription cost") without paying for a vector DB.

Approach
────────
  1. Walk every `.py` file under /app/backend and /app/frontend/src.
  2. For each file: extract module docstring + every top-level
     function/method name + its docstring (one AST pass).
  3. Build a small in-memory index in the form:
        [
          { "path": "...", "kind": "function"|"class"|"module",
            "name": "...", "doc": "...", "lineno": int,
            "haystack_lc": "lowercased blob" },
          ...
        ]
  4. On query: tokenize → expand a small synonym dictionary →
     score each entry by token-hit frequency and AST kind (functions/
     classes outrank module preambles). Return top-N.

The index is built lazily on first call and re-built only when the user
sets `force_rebuild=True` or the underlying files change (we track an
mtime fingerprint of the project root).

Search is exposed as an ORA tool `search_codebase_semantic` so the
agent can ask intent-level questions instead of grepping exact strings.
"""
from __future__ import annotations

import ast
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Roots we'll index. Limited to keep the index small + fast.
_INDEX_ROOTS = (
    "/app/backend",
)

# Light synonym/expansion table. Keeps queries about money find
# `cost`/`price`/`billing`, etc. Tiny by design — heavyweight expansion
# adds noise.
_SYNONYMS: dict[str, list[str]] = {
    "cost":         ["price", "billing", "stripe", "charge", "amount"],
    "price":        ["cost", "billing", "amount"],
    "auth":         ["login", "signin", "jwt", "session", "credentials"],
    "login":        ["auth", "signin", "credentials"],
    "user":         ["customer", "tenant", "account", "founder"],
    "email":        ["resend", "mailer", "smtp"],
    "campaign":     ["blast", "outreach"],
    "lead":         ["prospect", "scout"],
    "rollback":     ["restore", "revert"],
    "deploy":       ["release", "ship", "publish"],
    "rate":         ["throttle", "limit"],
}

_index: Optional[list[dict]] = None
_index_fingerprint: Optional[str] = None
_index_built_at: float = 0.0
_MAX_FILES = 1500  # safety ceiling


def _fingerprint(roots: tuple) -> str:
    """Cheap mtime+count fingerprint of the project roots. We re-build
    the index if the fingerprint changes."""
    parts: list[str] = []
    for root in roots:
        try:
            count = 0
            newest = 0.0
            for dirpath, _, files in os.walk(root):
                if any(p in dirpath for p in ("/node_modules/", "/__pycache__",
                                               "/.git/", "/.venv/")):
                    continue
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    count += 1
                    try:
                        m = os.path.getmtime(os.path.join(dirpath, f))
                        if m > newest:
                            newest = m
                    except Exception:
                        pass
                    if count > _MAX_FILES:
                        break
                if count > _MAX_FILES:
                    break
            parts.append(f"{root}:{count}:{newest:.0f}")
        except Exception:
            parts.append(f"{root}:err")
    return "|".join(parts)


def _extract_entries(path: str) -> list[dict]:
    """Pull module/class/function names + docstrings from one Python file."""
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read(200_000)  # cap per file
    except Exception:
        return entries
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        return entries
    mod_doc = ast.get_docstring(tree) or ""
    if mod_doc:
        entries.append({
            "path": path, "kind": "module", "name": Path(path).stem,
            "doc": mod_doc[:500], "lineno": 1,
        })
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entries.append({
                "path": path, "kind": "function", "name": node.name,
                "doc": (ast.get_docstring(node) or "")[:500],
                "lineno": node.lineno,
            })
        elif isinstance(node, ast.ClassDef):
            entries.append({
                "path": path, "kind": "class", "name": node.name,
                "doc": (ast.get_docstring(node) or "")[:500],
                "lineno": node.lineno,
            })
    return entries


def _build_index(roots: tuple = _INDEX_ROOTS) -> list[dict]:
    """Walk roots and build the searchable list. Single-threaded; ~200 ms
    for AUREM's backend on a warm pod."""
    out: list[dict] = []
    seen = 0
    for root in roots:
        for dirpath, _, files in os.walk(root):
            if any(p in dirpath for p in ("/node_modules/", "/__pycache__",
                                           "/.git/", "/.venv/", "/tests/")):
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                full = os.path.join(dirpath, f)
                for e in _extract_entries(full):
                    blob = (
                        e["name"] + " " + (e.get("doc") or "")
                        + " " + Path(e["path"]).stem
                    ).lower()
                    e["haystack_lc"] = blob
                    out.append(e)
                seen += 1
                if seen > _MAX_FILES:
                    return out
    return out


def _ensure_index(force_rebuild: bool = False) -> None:
    global _index, _index_fingerprint, _index_built_at
    fp = _fingerprint(_INDEX_ROOTS)
    if not force_rebuild and _index is not None and _index_fingerprint == fp:
        return
    t = time.time()
    _index = _build_index(_INDEX_ROOTS)
    _index_fingerprint = fp
    _index_built_at = t
    logger.info(
        f"[code-search] built index: {len(_index)} entries in "
        f"{(time.time() - t) * 1000:.0f} ms"
    )


def _tokenize(q: str) -> list[str]:
    """Split query, lowercase, drop stop-words and 1-char tokens."""
    stop = {"the", "a", "an", "for", "to", "of", "in", "is", "and",
            "or", "that", "with", "by", "on", "this"}
    toks: list[str] = []
    for w in (q or "").lower().split():
        w = "".join(ch for ch in w if ch.isalnum() or ch == "_")
        if len(w) >= 2 and w not in stop:
            toks.append(w)
    return toks


def _expand(toks: list[str]) -> list[str]:
    """Expand each token with a tiny synonym list (capped at +6 terms)."""
    out = list(toks)
    extra = 0
    for t in toks:
        for syn in _SYNONYMS.get(t, ()):
            if syn not in out and extra < 6:
                out.append(syn)
                extra += 1
    return out


def search(query: str, *, limit: int = 20,
           force_rebuild: bool = False) -> dict:
    """Score every entry by token-hit frequency and AST kind.

    Returns: {ok, query, expanded_tokens, total_indexed, matches: [...]}.
    Each match has {path, lineno, kind, name, doc, score}.
    """
    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "error": "query required"}
    _ensure_index(force_rebuild=bool(force_rebuild))
    if not _index:
        return {"ok": False, "error": "index empty (no files indexed)"}
    toks = _expand(_tokenize(query))
    if not toks:
        return {"ok": False, "error": "no usable tokens in query"}
    limit = max(1, min(int(limit or 20), 100))
    scored: list[tuple[float, dict]] = []
    kind_boost = {"function": 1.0, "class": 0.9, "module": 0.5}
    for e in _index:
        hay = e["haystack_lc"]
        # cheap hit-count
        hits = 0
        for t in toks:
            if t in hay:
                hits += hay.count(t)
        if hits == 0:
            continue
        # Boost: exact name match for any token
        name_lc = e["name"].lower()
        name_bonus = 4.0 if name_lc in toks else (
            2.0 if any(t == name_lc or t in name_lc for t in toks) else 0.0
        )
        score = hits * kind_boost.get(e["kind"], 0.5) + name_bonus
        scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    matches = [
        {
            "path":   e["path"],
            "lineno": e["lineno"],
            "kind":   e["kind"],
            "name":   e["name"],
            "doc":    (e.get("doc") or "")[:200],
            "score":  round(score, 2),
        }
        for score, e in scored[:limit]
    ]
    return {
        "ok":              True,
        "query":           query,
        "expanded_tokens": toks,
        "total_indexed":   len(_index),
        "matches":         matches,
        "count":           len(matches),
    }


def index_stats() -> dict:
    """Debug helper — admin can call to see how big the index is."""
    return {
        "ok":           True,
        "entries":      len(_index) if _index is not None else 0,
        "fingerprint":  _index_fingerprint,
        "built_at_ts":  _index_built_at,
        "roots":        list(_INDEX_ROOTS),
    }
