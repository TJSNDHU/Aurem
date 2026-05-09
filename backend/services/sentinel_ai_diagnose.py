"""
sentinel_ai_diagnose.py — Reusable Claude-based error diagnosis.

Single source of truth for turning a captured client_error doc into a
structured `repair_suggestion` row. Used by:
  • routers/sentinel_client_router.admin_analyze_error  (manual: admin click)
  • services/sentinel_repair_loop                       (autonomous: A2A → Council → ORA)

iter 322 STEP 1 — routes through `services.llm_gateway_v2.route` so EVERY
call is cost-tracked in db.llm_costs (tokens + latency + provider).

iter 322q — Token Optimization (3-step):
  STEP A · Triage layer (cheap Qwen) classifies BEFORE Claude. Trivial /
           known-pattern / CDN-noise short-circuits without burning Claude.
  STEP B · Context compression — top-5 stack frames only, message capped.
  STEP C · Response cache (db.llm_response_cache) keyed on signature so
           identical errors within 24h reuse the cached suggestion.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.llm_response_cache import cache_get, cache_put
from services.sentinel_triage import compress_stack, triage

logger = logging.getLogger(__name__)

# Bumped when the system prompt or schema changes — invalidates cache.
_PROMPT_SEED = "v2-triage-2026-02-10"
_CACHE_SCOPE = "sentinel_diagnose"

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


def _compact_payload(err: Dict[str, Any]) -> Dict[str, Any]:
    """STEP B — context compression. Trim message + stack aggressively."""
    return {
        "type": err.get("type"),
        "classification": err.get("classification"),
        "message": (err.get("message") or "")[:600],
        "status_code": err.get("status_code"),
        "url": err.get("url"),
        "method": err.get("method"),
        "stack_top": compress_stack(err.get("stack") or "", max_frames=5, head_chars=900),
        "page_url": err.get("page_url"),
        "hostname": err.get("hostname"),
    }


async def diagnose_error(err: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude with the compact error payload, return parsed JSON.
    Raises on LLM failure / unparseable response so caller can decide.

    NOTE: This is the LOW-LEVEL Claude call. Callers that want triage +
    cache short-circuiting should use `diagnose_and_store` instead.
    """
    from services.llm_gateway_v2 import route

    compact = _compact_payload(err)
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


def _suggestion_from_triage(triage_out: Dict[str, Any], err: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Claude-skipping suggestion when triage marks the error
    TRIVIAL with high confidence. We still flag `safe_auto_apply=False`
    so a human reviews before any code change."""
    cat = triage_out.get("category") or "unknown_runtime"
    severity_map = {
        "auth_expired": "P3",
        "network_transient": "P3",
        "cdn_5xx": "P3",
        "validation_error": "P2",
        "npe_or_undefined": "P2",
        "unknown_runtime": "P2",
        "novel": "P1",
    }
    return {
        "severity": severity_map.get(cat, "P2"),
        "root_cause": triage_out.get("reason") or f"Pattern-classified: {cat}",
        "suggested_fix": triage_out.get("quick_fix_hint")
            or "Triage classifier matched a known pattern. Review before applying.",
        "code_hint": "",
        "affected_files": [],
        "test_hint": "Reproduce via the captured URL and verify the error no longer recurs.",
        "confidence": float(triage_out.get("confidence") or 0.6),
        "requires_deploy": False,
        "safe_auto_apply": False,
        "_diagnose_path": "triage_short_circuit",
        "_triage_category": cat,
    }


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
        "diagnose_path": parsed.get("_diagnose_path") or "claude_full",
        "triage_category": parsed.get("_triage_category"),
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
    """Full pipeline with triage + cache:
       1. existing-pending-suggestion dedup (cheapest)
       2. response-cache hit (cheap — bypasses both LLMs)
       3. triage classify (cheap LLM)
          • SKIP     → drop, no row
          • TRIVIAL  → store low-conf suggestion from triage
          • ESCALATE → fall through to Claude
       4. Claude diagnose → store
       5. mark sibling client_errors as ai_diagnosed (dedup downstream)
    Returns the stored suggestion (without _id) or None on failure / SKIP.
    """
    if db is None:
        raise RuntimeError("db_unavailable")

    sig = err.get("signature")

    # --- Layer 1: existing suggestion dedup ---
    if sig:
        existing = await db.repair_suggestions.find_one(
            {"source_signature": sig, "status": "pending"}, {"_id": 0}
        )
        if existing:
            return existing

    # --- Layer 2: response-cache hit ---
    cached = await cache_get(db, scope=_CACHE_SCOPE, signature=sig or "", prompt_seed=_PROMPT_SEED) if sig else None
    parsed: Optional[Dict[str, Any]] = None
    if cached:
        parsed = dict(cached)
        # Force-mark this run as a cache hit (override the original
        # path label that was cached from the 1st execution).
        parsed["_diagnose_path"] = "cache_hit"
    else:
        # --- Layer 3: triage ---
        triage_out: Dict[str, Any] = {}
        try:
            triage_out = await triage(err)
        except Exception as e:
            logger.debug(f"[sentinel-diagnose] triage soft-fail → escalating: {e}")
            triage_out = {"verdict": "ESCALATE", "confidence": 0.0}

        verdict = triage_out.get("verdict") or "ESCALATE"
        confidence = float(triage_out.get("confidence") or 0)

        if verdict == "SKIP" and confidence >= 0.75:
            # Drop noise. Mark error so we don't re-triage it forever.
            try:
                match = {"signature": sig} if sig else {"error_id": err.get("error_id")}
                await db.client_errors.update_many(
                    {**match, "status": {"$in": ["new", "council_rejected"]}},
                    {"$set": {"status": "triage_skipped",
                              "triage_reason": triage_out.get("reason", "")[:200]}},
                )
            except Exception:
                pass
            return None

        if verdict == "TRIVIAL" and confidence >= 0.80:
            parsed = _suggestion_from_triage(triage_out, err)
        else:
            # ESCALATE → full Claude
            parsed = await diagnose_error(err)
            parsed["_diagnose_path"] = "claude_full"

        # Persist to cache (only successful, non-empty parses).
        if sig and parsed and parsed.get("root_cause"):
            await cache_put(
                db,
                scope=_CACHE_SCOPE,
                signature=sig,
                payload=parsed,
                prompt_seed=_PROMPT_SEED,
            )

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
