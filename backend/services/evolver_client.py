"""
EvoMap Evolver Client — Iteration 212
=====================================
Graceful-degradation HTTP client that talks to the EvoMap `evolver` node
(https://github.com/EvoMap/evolver) typically running on the user's Legion PC.

Runtime contract (HTTP over LAN / tunnel):
    POST {EVOLVER_URL}/analyze-failure       — body: {context, error, code_files}
    POST {EVOLVER_URL}/track-performance     — body: {template, response_rate, ...}
    POST {EVOLVER_URL}/review                — triggers a nightly review pass
    GET  {EVOLVER_URL}/genes                 — list genes the Evolver has produced

We NEVER auto-apply genes. Every gene the Evolver emits is saved in the
`evolver_genes` collection with status="pending_review". An admin flips the
status to `approved` from the Control Center before any runtime action
uses it.

When `EVOLVER_URL` is empty, all calls no-op gracefully (returns
{"ok": False, "reason": "offline"}). AUREM keeps working; the dashboard
shows Evolver as "offline".

ENV
---
EVOLVER_URL             — Legion node URL, e.g. http://192.168.1.20:7777
EVOLVER_STRATEGY        — harden | innovate | repair-only   (default: harden)
EVOLVER_REVIEW_MODE     — "true" to queue genes for admin approval (default: true)
EVOLVER_ALLOW_SELF_MODIFY — "true" to allow auto-apply (NEVER default this)
EVOLVER_TIMEOUT_S       — per-call timeout (default 8)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

EVOLVER_URL = (os.environ.get("EVOLVER_URL") or os.environ.get("EVOLVE_URL") or "").rstrip("/")
# Prefer EVOLVE_* prefix (official EvoMap convention) with fallback to EVOLVER_*.
EVOLVER_STRATEGY = (os.environ.get("EVOLVE_STRATEGY") or os.environ.get("EVOLVER_STRATEGY") or "harden").lower()
EVOLVER_REVIEW_MODE = (
    (os.environ.get("EVOLVE_REVIEW_MODE") or os.environ.get("EVOLVER_REVIEW_MODE") or "true").lower() == "true"
)
EVOLVER_ALLOW_SELF_MODIFY = (
    (os.environ.get("EVOLVE_ALLOW_SELF_MODIFY") or os.environ.get("EVOLVER_ALLOW_SELF_MODIFY") or "false").lower() == "true"
)
EVOLVER_TIMEOUT_S = float(os.environ.get("EVOLVER_TIMEOUT_S") or os.environ.get("EVOLVE_TIMEOUT_S") or "8")
GENES_COLLECTION = "evolver_genes"
EVENTS_COLLECTION = "evolver_events"


# ─────────────────────────────────────────────────────────────
# Low-level transport
# ─────────────────────────────────────────────────────────────
def is_configured() -> bool:
    return bool(EVOLVER_URL)


async def _post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if not is_configured():
        return {"ok": False, "reason": "offline", "evolver_configured": False}
    try:
        async with httpx.AsyncClient(timeout=EVOLVER_TIMEOUT_S) as client:
            resp = await client.post(
                f"{EVOLVER_URL}{path}",
                json={
                    "strategy": EVOLVER_STRATEGY,
                    "review_mode": EVOLVER_REVIEW_MODE,
                    "allow_self_modify": EVOLVER_ALLOW_SELF_MODIFY,
                    **body,
                },
            )
        if resp.status_code < 400:
            try:
                return {"ok": True, "data": resp.json()}
            except Exception:
                return {"ok": True, "data": {"raw": resp.text[:500]}}
        return {"ok": False, "reason": f"http_{resp.status_code}",
                "body_preview": resp.text[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


async def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not is_configured():
        return {"ok": False, "reason": "offline", "evolver_configured": False}
    try:
        async with httpx.AsyncClient(timeout=EVOLVER_TIMEOUT_S) as client:
            resp = await client.get(f"{EVOLVER_URL}{path}", params=params or {})
        if resp.status_code < 400:
            return {"ok": True, "data": resp.json()}
        return {"ok": False, "reason": f"http_{resp.status_code}"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


# ─────────────────────────────────────────────────────────────
# Local gene store
# ─────────────────────────────────────────────────────────────
async def _record_event(db, kind: str, payload: Dict[str, Any]) -> None:
    """Append to evolver_events collection for dashboard + audit."""
    if db is None:
        return
    try:
        await db[EVENTS_COLLECTION].insert_one({
            "kind": kind,
            "payload": payload,
            "strategy": EVOLVER_STRATEGY,
            "review_mode": EVOLVER_REVIEW_MODE,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[Evolver] event log failed: {e}")


async def _save_genes(db, genes: List[Dict[str, Any]], source: str) -> int:
    """Upsert genes returned by the Evolver into MongoDB as pending review."""
    if db is None or not genes:
        return 0
    saved = 0
    for g in genes:
        gene_id = g.get("id") or g.get("gene_id") or uuid4().hex[:12]
        try:
            await db[GENES_COLLECTION].update_one(
                {"gene_id": gene_id},
                {"$set": {
                    "gene_id": gene_id,
                    "source": source,
                    "pattern": g.get("pattern"),
                    "diagnosis": g.get("diagnosis") or g.get("reason"),
                    "remediation": g.get("remediation") or g.get("fix"),
                    "confidence": g.get("confidence"),
                    "raw": g,
                    "status": "approved" if (not EVOLVER_REVIEW_MODE and EVOLVER_ALLOW_SELF_MODIFY)
                    else "pending_review",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            saved += 1
        except Exception as e:
            logger.warning(f"[Evolver] gene save failed: {e}")
    return saved


# ─────────────────────────────────────────────────────────────
# Public hooks — called from Builder / ORA / scheduler
# ─────────────────────────────────────────────────────────────
async def analyze_failure(
    db,
    build_id: str,
    description: str,
    files: List[Dict[str, Any]],
    error: str,
) -> Dict[str, Any]:
    """
    Called by AUREM Builder when a build fails.
    Returns: {ok, genes_saved, evolver_configured}
    """
    await _record_event(db, "analyze_failure_attempt", {
        "build_id": build_id, "description": description, "error": error[:500],
    })
    resp = await _post("/analyze-failure", {
        "build_id": build_id,
        "description": description,
        "error": error[:2000],
        "files": [{"path": f.get("path"),
                   "ok": f.get("ok"),
                   "security_issues": f.get("security_issues"),
                   "syntax_error": f.get("syntax_error"),
                   "import_error": f.get("import_error")}
                  for f in files[:20]],
    })
    genes_saved = 0
    if resp.get("ok"):
        data = resp.get("data") or {}
        genes = data.get("genes") or data.get("new_genes") or []
        genes_saved = await _save_genes(db, genes, source=f"builder_fail:{build_id}")
        await _record_event(db, "analyze_failure_success",
                            {"build_id": build_id, "genes_saved": genes_saved})
    else:
        await _record_event(db, "analyze_failure_offline",
                            {"build_id": build_id, "reason": resp.get("reason")})
    return {
        "ok": resp.get("ok", False),
        "genes_saved": genes_saved,
        "evolver_configured": is_configured(),
        "reason": resp.get("reason"),
    }


async def track_performance(
    db,
    template: str,
    response_rate: float,
    channel: str = "whatsapp",
    tenant_id: Optional[str] = None,
    sample_size: int = 0,
) -> Dict[str, Any]:
    """Called by ORA after a campaign run — Evolver keeps the winners as genes."""
    await _record_event(db, "track_performance", {
        "template_preview": (template or "")[:160],
        "response_rate": response_rate,
        "channel": channel,
        "tenant_id": tenant_id,
        "sample_size": sample_size,
    })
    resp = await _post("/track-performance", {
        "template": template,
        "response_rate": response_rate,
        "channel": channel,
        "tenant_id": tenant_id,
        "sample_size": sample_size,
    })
    genes_saved = 0
    if resp.get("ok"):
        data = resp.get("data") or {}
        genes = data.get("genes") or []
        genes_saved = await _save_genes(db, genes, source=f"campaign:{channel}")
    return {"ok": resp.get("ok", False), "genes_saved": genes_saved,
            "evolver_configured": is_configured()}


async def run_review(db) -> Dict[str, Any]:
    """
    Nightly 2:30 AM hook — asks the Evolver to review the previous 24 h of
    runtime data and emit any new genes. Pulls gene list back and saves pending.
    """
    await _record_event(db, "review_run_attempt", {})
    resp = await _post("/review", {"window_hours": 24})
    genes_saved = 0
    patterns = 0
    if resp.get("ok"):
        data = resp.get("data") or {}
        genes = data.get("genes") or []
        patterns = int(data.get("patterns_learned", len(genes)))
        genes_saved = await _save_genes(db, genes, source="nightly_review")
        await _record_event(db, "review_run_success",
                            {"genes_saved": genes_saved, "patterns_learned": patterns})
    else:
        await _record_event(db, "review_run_offline", {"reason": resp.get("reason")})
    return {
        "ok": resp.get("ok", False),
        "genes_saved": genes_saved,
        "patterns_learned": patterns,
        "evolver_configured": is_configured(),
        "reason": resp.get("reason"),
    }


# ─────────────────────────────────────────────────────────────
# Dashboard reads
# ─────────────────────────────────────────────────────────────
async def get_status(db) -> Dict[str, Any]:
    """Summary card payload for the Admin Control Center."""
    configured = is_configured()
    remote_ok = False
    remote_info: Dict[str, Any] = {}
    if configured:
        ping = await _get("/status")
        remote_ok = ping.get("ok", False)
        remote_info = ping.get("data") or {}

    if db is None:
        return {
            "configured": configured,
            "reachable": remote_ok,
            "strategy": EVOLVER_STRATEGY,
            "review_mode": EVOLVER_REVIEW_MODE,
            "allow_self_modify": EVOLVER_ALLOW_SELF_MODIFY,
            "genes_total": 0, "genes_pending": 0, "genes_approved": 0,
            "last_run": None, "last_event": None, "remote": remote_info,
        }

    genes_total = await db[GENES_COLLECTION].count_documents({})
    genes_pending = await db[GENES_COLLECTION].count_documents({"status": "pending_review"})
    genes_approved = await db[GENES_COLLECTION].count_documents({"status": "approved"})
    last_review = await db[EVENTS_COLLECTION].find_one(
        {"kind": {"$in": ["review_run_success", "review_run_offline"]}},
        sort=[("ts", -1)], projection={"_id": 0},
    )
    last_event = await db[EVENTS_COLLECTION].find_one(
        {}, sort=[("ts", -1)], projection={"_id": 0},
    )
    return {
        "configured": configured,
        "reachable": remote_ok,
        "strategy": EVOLVER_STRATEGY,
        "review_mode": EVOLVER_REVIEW_MODE,
        "allow_self_modify": EVOLVER_ALLOW_SELF_MODIFY,
        "genes_total": genes_total,
        "genes_pending": genes_pending,
        "genes_approved": genes_approved,
        "last_run": last_review,
        "last_event": last_event,
        "remote": remote_info,
    }


async def list_genes(db, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    if db is None:
        return []
    q = {"status": status} if status else {}
    cursor = db[GENES_COLLECTION].find(q, projection={"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def set_gene_status(db, gene_id: str, new_status: str, admin: str) -> bool:
    """Admin approve/reject/retire a gene."""
    if db is None:
        return False
    if new_status not in ("approved", "rejected", "pending_review", "retired"):
        return False
    r = await db[GENES_COLLECTION].update_one(
        {"gene_id": gene_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": admin}},
    )
    await _record_event(db, "gene_status_changed",
                        {"gene_id": gene_id, "new_status": new_status, "admin": admin})
    return r.matched_count > 0
