"""
sentinel_ai_diagnose.py — Reusable Claude-based error diagnosis.

Single source of truth for turning a captured client_error doc into a
structured `repair_suggestion` row. Used by:
  • routers/sentinel_client_router.admin_analyze_error  (manual: admin click)
  • services/sentinel_repair_loop                       (autonomous: A2A → Council → ORA)

iter 322 STEP 1 — routes through `services.llm_gateway_v2.route` so EVERY
call is cost-tracked in db.llm_costs (tokens + latency + provider). This
is the ONLY path Claude is hit from Sentinel; manual + autonomous both
flow through the same gateway, so spend visibility is now total.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are AUREM's senior SRE. Given a captured client-side error, "
    "produce a STRICT JSON repair suggestion for human review. "
    "Never modify code — only suggest. Keep confidence honest.\n\n"
    "Output JSON schema (no other text, no markdown fences):\n"
    "{\n"
    '  "severity": "P0"|"P1"|"P2"|"P3",\n'
    '  "root_cause": "1-2 sentence diagnosis",\n'
    '  "suggested_fix": "natural-language description of the fix",\n'
    '  "code_hint": "optional pseudo-diff or file path to inspect",\n'
    '  "affected_files": ["path/to/file1", ...],\n'
    '  "test_hint": "how to verify the fix works",\n'
    '  "confidence": 0.0-1.0,\n'
    '  "requires_deploy": true|false,\n'
    '  "safe_auto_apply": false\n'
    "}\n"
    'Rule: set "safe_auto_apply" to true ONLY for mechanical single-line fixes. '
    "For anything structural, set to false."
)


async def diagnose_error(err: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude with the compact error payload, return parsed JSON.
    Raises on LLM failure / unparseable response so caller can decide.

    iter 322 — STEP 1 wired through `services.llm_gateway_v2.route`
    (task_type='repair_diagnose'). All calls now logged to db.llm_costs
    with token counts + latency, and the gateway will (in subsequent steps)
    enforce per-BIN budget caps + free-LLM-first triage.
    """
    from services.llm_gateway_v2 import route

    compact = {
        "type": err.get("type"),
        "classification": err.get("classification"),
        "message": err.get("message"),
        "status_code": err.get("status_code"),
        "url": err.get("url"),
        "method": err.get("method"),
        "stack_head": (err.get("stack") or "")[:1200],
        "page_url": err.get("page_url"),
        "hostname": err.get("hostname"),
    }
    user_prompt = f"Error:\n{json.dumps(compact, indent=2)}"
    result = await route(
        task_type="repair_diagnose",
        prompt=user_prompt,
        system=_SYSTEM_PROMPT,
        max_tokens=1500,
    )
    if not result.get("ok") or not result.get("text"):
        raise RuntimeError(
            f"LLM gateway failed: {result.get('error') or 'no_text'} "
            f"(provider={result.get('provider')} model={result.get('model')})"
        )
    raw = str(result["text"]).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM did not return JSON: {raw[:200]}")
    return json.loads(raw[start : end + 1])


def build_suggestion_doc(
    err: Dict[str, Any], parsed: Dict[str, Any], *, source: str = "manual"
) -> Dict[str, Any]:
    """Shape the parsed Claude output into the canonical repair_suggestions row.
    `source` distinguishes manual admin clicks vs. autonomous loop discoveries.
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "suggestion_id": f"rs_{uuid.uuid4().hex[:12]}",
        "error_id": err.get("error_id"),
        "source": source,  # "manual" | "autonomous_a2a"
        "source_signature": err.get("signature"),
        "created_at": now,
        "status": "pending",
        "severity": parsed.get("severity") or "P2",
        "root_cause": (parsed.get("root_cause") or "")[:500],
        "suggested_fix": (parsed.get("suggested_fix") or "")[:1500],
        "code_hint": (parsed.get("code_hint") or "")[:2000],
        "affected_files": (parsed.get("affected_files") or [])[:10],
        "test_hint": (parsed.get("test_hint") or "")[:400],
        "confidence": float(parsed.get("confidence") or 0),
        "requires_deploy": bool(parsed.get("requires_deploy")),
        "safe_auto_apply": bool(parsed.get("safe_auto_apply")),
        "error_snapshot": {
            "classification": err.get("classification"),
            "message": err.get("message"),
            "url": err.get("url"),
            "status_code": err.get("status_code"),
        },
    }


async def diagnose_and_store(
    db, err: Dict[str, Any], *, source: str = "manual"
) -> Optional[Dict[str, Any]]:
    """Full pipeline: dedup → Claude diagnose → persist suggestion → mark
    client_error as analyzed. Returns the stored suggestion (without _id),
    or the existing one if already pending. Returns None on failure.
    """
    if db is None:
        raise RuntimeError("db_unavailable")

    sig = err.get("signature")
    if sig:
        existing = await db.repair_suggestions.find_one(
            {"source_signature": sig, "status": "pending"}, {"_id": 0}
        )
        if existing:
            return existing

    parsed = await diagnose_error(err)
    suggestion = build_suggestion_doc(err, parsed, source=source)
    await db.repair_suggestions.insert_one(dict(suggestion))

    # Mark this error AND any sibling errors with same signature as analyzed
    # so the autonomous loop doesn't re-burn LLM tokens on duplicates.
    try:
        match = {"signature": sig} if sig else {"error_id": err.get("error_id")}
        await db.client_errors.update_many(
            {**match, "status": {"$in": ["new", "council_rejected"]}},
            {"$set": {
                "status": "ai_diagnosed",
                "suggestion_id": suggestion["suggestion_id"],
            }},
        )
    except Exception as e:
        logger.debug(f"[sentinel-diagnose] sibling mark skipped: {e}")

    suggestion.pop("_id", None)
    return suggestion
