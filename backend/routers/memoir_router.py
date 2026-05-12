"""
Memoir Router — REST surface for AUREM's Git-versioned semantic memory.

All under /api/admin/memoir. Endpoints:

  GET  /info                       — store path + availability
  GET  /stats                      — read/write/search counts, total_keys
  GET  /recall?path=&key=          — fetch a single value
  GET  /search?path=&limit=        — list (namespace,key,value) tuples
  GET  /history?path=&key=&limit=  — Git commit history for a key
  POST /remember                   — write a value (admin)
  POST /commit                     — force a commit message
  GET  /ora/session/{session_id}   — replay last N turns
  GET  /founder/save-history/{save_id}
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import memoir_service as M

router = APIRouter(prefix="/api/admin/memoir", tags=["memoir"])


class RememberRequest(BaseModel):
    path: str
    key: str
    value: Any
    commit_msg: Optional[str] = None


class CommitRequest(BaseModel):
    message: str


def _serialize_search(rows: list[tuple]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if isinstance(row, tuple) and len(row) >= 3:
            ns, key, val = row[0], row[1], row[2]
            out.append({
                "namespace": list(ns) if isinstance(ns, (tuple, list)) else [str(ns)],
                "key": str(key),
                "value": val,
            })
    return out


@router.get("/info")
async def info():
    return M.info()


@router.get("/stats")
async def stats():
    return M.stats()


@router.get("/recall")
async def recall(path: str, key: str):
    val = M.recall(path, key)
    if val is None:
        raise HTTPException(404, f"No value at {path}.{key}")
    return {"path": path, "key": key, "value": val}


@router.get("/search")
async def search(path: str, limit: int = Query(20, ge=1, le=500)):
    rows = M.search(path, limit=limit)
    return {"path": path, "count": len(rows), "items": _serialize_search(rows)}


@router.get("/history")
async def history(path: str, key: str, limit: int = Query(20, ge=1, le=200)):
    h = M.history(path, key, limit=limit)
    return {"path": path, "key": key, "history": h}


@router.post("/remember")
async def remember(req: RememberRequest):
    sha = M.remember(req.path, req.key, req.value, commit_msg=req.commit_msg)
    return {"ok": True, "commit": sha}


@router.post("/commit")
async def force_commit(req: CommitRequest):
    sha = M.commit(req.message)
    return {"commit": sha}


@router.get("/ora/session/{session_id}")
async def ora_session(session_id: str, limit: int = Query(20, ge=1, le=200)):
    return {"session_id": session_id, "turns": M.ora_recall_session(session_id, limit=limit)}


@router.get("/founder/save-history/{save_id}")
async def founder_save_history(save_id: str, limit: int = Query(50, ge=1, le=200)):
    return {"save_id": save_id, "history": M.founder_save_history(save_id, limit=limit)}


@router.get("/_/health", include_in_schema=False)
async def health():
    return {"ok": True, "available": M.available(), **M.info()}
