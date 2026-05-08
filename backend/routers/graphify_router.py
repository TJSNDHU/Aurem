"""
AUREM Graphify Knowledge Graph Router
=======================================
API endpoints for building, querying, and monitoring the code knowledge graph.

iter 261 — Added shareable snapshots. Admin builds a graph snapshot, gets
a public share URL (+7 day expiry) which can be sent to any external AI
(Claude.ai, ChatGPT, etc.) for second-opinion code review / debugging
without granting the AI live access to the codebase.
"""
import os
import json
import uuid
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Knowledge Graph"])
logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("/app/backend/graphify-out/snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_EXPIRY_DAYS = 7

_db = None


def set_db(database):
    global _db
    _db = database


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _admin_only(authorization: str = Header(None)):
    payload = await _auth(authorization)
    role = (payload.get("role") or "").lower()
    is_admin = payload.get("is_admin") or role in ("admin", "super_admin", "owner")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


class BuildRequest(BaseModel):
    target_dir: str = "/app/backend"
    include_frontend: bool = False


class QueryRequest(BaseModel):
    query: str
    top_k: int = 10


class SnapshotRequest(BaseModel):
    include_frontend: bool = True
    note: Optional[str] = None
    expires_in_days: int = DEFAULT_EXPIRY_DAYS


# ═════════════════════════════════════════════════════════════════════
# ORIGINAL endpoints (graph build/query/stats)
# ═════════════════════════════════════════════════════════════════════
@router.post("/api/graphify/build")
async def build_graph(req: BuildRequest, background_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Build knowledge graph from codebase (background, deterministic AST)."""
    await _auth(authorization)
    from services.graphify_service import build_knowledge_graph
    background_tasks.add_task(build_knowledge_graph, req.target_dir, req.include_frontend)
    return {
        "status": "building",
        "message": f"Knowledge graph build started for {req.target_dir}. Check /api/graphify/stats for progress.",
        "include_frontend": req.include_frontend,
    }


@router.post("/api/graphify/build-sync")
async def build_graph_sync(req: BuildRequest, authorization: str = Header(None)):
    """Build knowledge graph synchronously."""
    await _auth(authorization)
    from services.graphify_service import build_knowledge_graph
    return build_knowledge_graph(req.target_dir, req.include_frontend)


@router.post("/api/graphify/query")
async def query_graph(req: QueryRequest, authorization: str = Header(None)):
    """Query the knowledge graph (keyword match, $0 cost)."""
    await _auth(authorization)
    from services.graphify_service import query_graph_local
    results = query_graph_local(req.query, req.top_k)
    return {
        "query": req.query,
        "results": results,
        "total": len(results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/graphify/stats")
async def graph_stats(authorization: str = Header(None)):
    await _auth(authorization)
    from services.graphify_service import get_graph_stats
    return get_graph_stats()


@router.get("/api/graphify/report")
async def graph_report(authorization: str = Header(None)):
    await _auth(authorization)
    from services.graphify_service import get_graph_report
    report = get_graph_report()
    if not report:
        return {"content": "", "message": "No graph built yet. POST /api/graphify/build to start."}
    return {"content": report}


@router.get("/api/graphify/context")
async def graph_context(query: str, max_tokens: int = 500, authorization: str = Header(None)):
    """Graph context block for ORA prompt injection."""
    await _auth(authorization)
    from services.graphify_service import get_graph_context
    context = get_graph_context(query, max_tokens)
    return {"query": query, "context": context, "chars": len(context)}


# ═════════════════════════════════════════════════════════════════════
# SHAREABLE SNAPSHOTS — "Brain on a USB stick"
# Admin triggers a fresh build → snapshot saved with short ID + expiry.
# Public URL allows any external AI to download graph.json / report.md /
# a ready-to-paste prompt, without backend auth or live codebase access.
# ═════════════════════════════════════════════════════════════════════

def _snapshot_paths(snapshot_id: str) -> dict:
    base = SNAPSHOT_DIR / snapshot_id
    return {
        "dir": base,
        "graph_json": base / "graph.json",
        "report_md": base / "GRAPH_REPORT.md",
    }


async def _load_snapshot_doc(snapshot_id: str) -> dict:
    if _db is None:
        raise HTTPException(503, "db not ready")
    doc = await _db.graph_snapshots.find_one({"snapshot_id": snapshot_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Snapshot not found")
    # Expiry check
    exp = doc.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                raise HTTPException(410, "Snapshot expired")
        except HTTPException:
            raise
        except Exception:
            pass
    if doc.get("revoked"):
        raise HTTPException(410, "Snapshot revoked")
    return doc


def _build_claude_prompt(doc: dict, base_url: str) -> str:
    """Return a ready-to-paste prompt that tells any AI how to use the snapshot."""
    stats = doc.get("stats", {})
    sid = doc["snapshot_id"]
    nodes = stats.get("nodes", 0)
    edges = stats.get("edges", 0)
    files = stats.get("files_scanned", 0)
    note = doc.get("note") or "General second-opinion review."
    graph_url = f"{base_url}/api/graphify/share/{sid}/download/graph.json"
    report_url = f"{base_url}/api/graphify/share/{sid}/download/report.md"
    share_url = f"{base_url}/graph/share/{sid}"
    gods = ", ".join((stats.get("god_nodes") or [])[:6]) or "(see report)"

    return (
        f"You are helping me review and debug the AUREM codebase. I cannot give "
        f"you direct repo access, so instead I've attached a compact knowledge "
        f"graph snapshot built with Graphify (AST-based, deterministic).\n\n"
        f"SNAPSHOT META\n"
        f"  id:         {sid}\n"
        f"  created:    {doc.get('created_at')}\n"
        f"  expires:    {doc.get('expires_at')}\n"
        f"  scope:      {'backend+frontend' if doc.get('include_frontend') else 'backend only'}\n"
        f"  files:      {files}\n"
        f"  nodes:      {nodes}\n"
        f"  edges:      {edges}\n"
        f"  god-nodes:  {gods}\n"
        f"  user note:  {note}\n\n"
        f"RESOURCES (paste/open these in your context)\n"
        f"  • Share page:  {share_url}\n"
        f"  • graph.json:  {graph_url}\n"
        f"  • Report.md:   {report_url}\n\n"
        f"INSTRUCTIONS\n"
        f"1. Treat the graph as the primary source of truth for architecture.\n"
        f"   Nodes are functions/classes/files; edges are imports/calls/uses.\n"
        f"2. Start from the \"god nodes\" (highest connectivity) to understand\n"
        f"   what is central, then traverse outward to the area I'm asking about.\n"
        f"3. When giving a fix, cite specific node labels and file paths from\n"
        f"   the graph. Do not invent files that aren't listed.\n"
        f"4. If the graph is insufficient, say exactly which file/function you\n"
        f"   need me to paste — don't guess.\n"
        f"5. Keep answers concrete and actionable. Prefer diffs over prose.\n\n"
        f"MY QUESTION / ISSUE\n"
        f"<describe the bug, feature, or review you want a second opinion on>\n"
    )


@router.post("/api/graphify/snapshot")
async def create_snapshot(req: SnapshotRequest, authorization: str = Header(None)):
    """Build a fresh graph and save it as a shareable snapshot (admin only)."""
    payload = await _admin_only(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")

    from services.graphify_service import build_knowledge_graph, GRAPH_JSON, GRAPH_REPORT

    # 1. Build fresh graph (blocks — could take 30-60s on a big codebase)
    logger.info(f"[graphify.snapshot] build start, include_frontend={req.include_frontend}")
    result = build_knowledge_graph("/app/backend", req.include_frontend)
    if result.get("status") != "built":
        raise HTTPException(500, f"Graph build failed: {result}")

    # 2. Copy artifacts into a dedicated snapshot dir
    snapshot_id = f"gs_{uuid.uuid4().hex[:12]}"
    paths = _snapshot_paths(snapshot_id)
    paths["dir"].mkdir(parents=True, exist_ok=True)

    try:
        import shutil
        shutil.copy(GRAPH_JSON, paths["graph_json"])
        if Path(GRAPH_REPORT).exists():
            shutil.copy(GRAPH_REPORT, paths["report_md"])
    except Exception as e:
        raise HTTPException(500, f"Failed to persist snapshot: {e}")

    # 3. Record metadata in Mongo
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=max(1, min(30, req.expires_in_days)))
    doc = {
        "snapshot_id": snapshot_id,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "created_by": payload.get("email") or payload.get("sub"),
        "include_frontend": req.include_frontend,
        "note": (req.note or "")[:300],
        "stats": {
            "nodes": result.get("nodes", 0),
            "edges": result.get("edges", 0),
            "files_scanned": result.get("files_scanned", 0),
            "god_nodes": result.get("god_nodes", []),
            "communities": result.get("communities", 0),
            "built_at": result.get("built_at"),
        },
        "revoked": False,
    }
    await _db.graph_snapshots.insert_one(dict(doc))

    logger.info(f"[graphify.snapshot] created {snapshot_id} — {doc['stats']['nodes']} nodes, {doc['stats']['edges']} edges")
    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "expires_at": doc["expires_at"],
        "stats": doc["stats"],
        "public_share_path": f"/graph/share/{snapshot_id}",
    }


@router.get("/api/graphify/snapshots")
async def list_snapshots(authorization: str = Header(None)):
    """List recent snapshots (admin only)."""
    await _admin_only(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cursor = _db.graph_snapshots.find({}, {"_id": 0}).sort("created_at", -1).limit(50)
    items = [doc async for doc in cursor]
    # Mark expired/active
    now = datetime.now(timezone.utc)
    for it in items:
        try:
            exp_dt = datetime.fromisoformat((it.get("expires_at") or "").replace("Z", "+00:00"))
            it["is_active"] = not it.get("revoked") and now <= exp_dt
        except Exception:
            it["is_active"] = False
    return {"snapshots": items, "count": len(items)}


@router.delete("/api/graphify/snapshot/{snapshot_id}")
async def revoke_snapshot(snapshot_id: str, authorization: str = Header(None)):
    """Revoke a snapshot (makes share URL return 410). Admin only."""
    await _admin_only(authorization)
    if _db is None:
        raise HTTPException(503, "db not ready")
    result = await _db.graph_snapshots.update_one(
        {"snapshot_id": snapshot_id},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Snapshot not found")
    return {"ok": True, "snapshot_id": snapshot_id, "revoked": True}


# ─── PUBLIC share endpoints (no auth) ────────────────────────────────
@router.get("/api/graphify/share/{snapshot_id}/meta")
async def share_meta(snapshot_id: str):
    """Public snapshot metadata — safe to expose (no code bodies, just stats)."""
    doc = await _load_snapshot_doc(snapshot_id)
    return {
        "snapshot_id": doc["snapshot_id"],
        "created_at": doc.get("created_at"),
        "expires_at": doc.get("expires_at"),
        "include_frontend": doc.get("include_frontend", False),
        "note": doc.get("note", ""),
        "stats": doc.get("stats", {}),
    }


@router.get("/api/graphify/share/{snapshot_id}/download/{file_type}")
async def share_download(snapshot_id: str, file_type: str):
    """Public download — graph.json, report.md, prompt.txt."""
    doc = await _load_snapshot_doc(snapshot_id)
    paths = _snapshot_paths(doc["snapshot_id"])

    if file_type in ("graph.json", "graph", "json"):
        if not paths["graph_json"].exists():
            raise HTTPException(404, "graph.json missing")
        return FileResponse(
            str(paths["graph_json"]),
            media_type="application/json",
            filename=f"aurem_graph_{snapshot_id}.json",
        )
    if file_type in ("report.md", "report", "md"):
        if not paths["report_md"].exists():
            # Return a stub so external AIs don't error
            return Response(content=f"# AUREM Graph Report\n\nSnapshot: {snapshot_id}\n(Full report unavailable.)\n",
                            media_type="text/markdown")
        return FileResponse(
            str(paths["report_md"]),
            media_type="text/markdown",
            filename=f"aurem_graph_report_{snapshot_id}.md",
        )
    if file_type in ("prompt.txt", "prompt", "txt"):
        # base_url from request
        from fastapi import Request  # noqa
        # reconstruct a safe public base; fall back to env
        base_url = os.environ.get("PUBLIC_BASE_URL", "https://aurem.live").rstrip("/")
        return Response(content=_build_claude_prompt(doc, base_url), media_type="text/plain")

    raise HTTPException(400, "Unknown file_type. Use graph.json | report.md | prompt.txt")


@router.get("/api/graphify/share/{snapshot_id}/prompt")
async def share_prompt(snapshot_id: str):
    """Public Claude/ChatGPT-ready prompt text for this snapshot."""
    doc = await _load_snapshot_doc(snapshot_id)
    base_url = os.environ.get("PUBLIC_BASE_URL", "https://aurem.live").rstrip("/")
    return {
        "snapshot_id": snapshot_id,
        "prompt": _build_claude_prompt(doc, base_url),
        "share_url": f"{base_url}/graph/share/{snapshot_id}",
    }
