"""
Emergent Code Fixer — iter 322ar
==================================
Tier-2 autonomous fix proposer. Cost cascade:

    L0  ORA pattern matcher (free, instant)
    L1  Sovereign LLM       (free, local)
    L2  OpenRouter free     (free, rate-limited)
    L3  Emergent / Claude   (paid, last resort)

Output of every call is a **structured proposal** stored as a row in
`db.ora_dev_actions` with `kind="emergent_code_fix"` so the Dev Console
UI surfaces it. This module DOES NOT mutate source files — actual code
mutation requires git-worktree sandboxing which is a separate work
package. The proposal payload includes the suggested diff so a human
(or, later, a sandbox-runner) can apply it.

After a fix is applied (status flips to `auto_approved` or `human_applied`
on the ora_dev_actions row) the verification hook in the
collective_scanner re-runs and feeds the outcome to
`fix_learning_pipeline.learn_from_fix()`.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services import ora_pattern_matcher, fix_learning_pipeline

logger = logging.getLogger(__name__)

_db = None

FIX_PROMPT_TEMPLATE = """You are debugging the AUREM platform. ONE issue at a time.
Return ONLY a JSON object — no prose, no markdown fences. Schema:
{{
  "root_cause": "<one sentence>",
  "fix_type": "config|scheduler_restart|code_change|env_var|data_repair",
  "diff": "<unified diff if fix_type=code_change, else null>",
  "files_changed": ["..."],
  "config_changed": {{"key": "...", "old": "...", "new": "..."}} | null,
  "action_taken": "<one-line imperative summary>",
  "risk_level": "LOW|MEDIUM|HIGH",
  "verification": "<a single async curl / mongo command that proves the fix>"
}}

Context:
  Agent affected: {agent}
  Evidence:       {evidence}
  Metric:         {metric_name}={metric_value} (expected ≥ {expected_value}, gap {gap})
  Status:         {status}

Be ultra-specific. If unsure, set risk_level=HIGH and propose verification only."""


def set_db(database) -> None:
    global _db
    _db = database
    fix_learning_pipeline.set_db(database)
    ora_pattern_matcher.set_db(database)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json_safe(blob: str) -> Optional[Dict[str, Any]]:
    if not blob:
        return None
    blob = blob.strip()
    # Strip code-fences if model added them despite our instruction
    if blob.startswith("```"):
        blob = blob.strip("`")
        if blob.lower().startswith("json"):
            blob = blob[4:].strip()
    try:
        return json.loads(blob)
    except Exception:
        # Last-ditch: find first '{' and last '}'
        s, e = blob.find("{"), blob.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(blob[s:e + 1])
            except Exception:
                return None
        return None


async def _ask_llm_for_fix(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Cascade through sovereign → openrouter → emergent. Returns
    {source, fix_json, raw} where source ∈ {sovereign,openrouter,emergent}."""
    try:
        from services.llm_gateway import call_llm_with_meta
    except Exception as e:
        return {"source": "unavailable", "fix_json": None, "raw": str(e)}

    user = FIX_PROMPT_TEMPLATE.format(
        agent=issue.get("agent") or issue.get("subject_agent"),
        evidence=issue.get("evidence_type"),
        metric_name=issue.get("metric_name"),
        metric_value=issue.get("metric_value"),
        expected_value=issue.get("expected_value"),
        gap=issue.get("gap"),
        status=issue.get("status"),
    )
    system = "You are AUREM's autonomous code-fix proposer. Output strict JSON."
    res = await call_llm_with_meta(system, user, max_tokens=900)
    parsed = _parse_json_safe(res.get("content", ""))
    return {
        "source": res.get("provider", "unknown"),  # sovereign|openrouter|emergent|fallback
        "fix_json": parsed,
        "raw": res.get("content"),
    }


async def request_code_fix(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point. Returns the proposal dict (also persisted)."""
    if _db is None:
        return {"ok": False, "reason": "db_unavailable"}

    # ── L0: ORA Pattern Matcher ────────────────────────────────────
    ora_check = await ora_pattern_matcher.check_ora_knows(issue)
    if ora_check.get("ora_knows") and not ora_check.get("use_emergent", True):
        proposal = {
            "action_id": str(uuid.uuid4()),
            "kind": "emergent_code_fix",
            "agent": issue.get("agent") or issue.get("subject_agent"),
            "source": "ora_learned",
            "match_type": ora_check.get("match_type"),
            "fix": ora_check.get("suggested_fix"),
            "confidence": ora_check.get("confidence"),
            "times_worked": ora_check.get("times_worked"),
            "risk_level": "LOW" if ora_check.get("confidence", 0) >= 0.9 else "MEDIUM",
            "tier": "tier_1" if ora_check.get("confidence", 0) >= 0.9 else "tier_2",
            "status": "pending",
            "issue": issue,
            "ts": _utc_now(),
            "cost_usd": 0.0,
            "message_plain": (
                f"ORA ne yeh fix pehle {ora_check.get('times_worked')} baar "
                f"successfully apply kiya hai (confidence {int(ora_check.get('confidence',0)*100)}%). "
                f"Fix type: {(ora_check.get('suggested_fix') or {}).get('fix_type','?')}."
            ),
        }
        try:
            await _db.ora_dev_actions.insert_one(proposal)
        except Exception as e:
            logger.warning(f"[code-fixer] L0 insert failed: {e}")
        # Log ledger
        await fix_learning_pipeline.learn_from_fix({
            "issue": issue,
            "fix": ora_check.get("suggested_fix") or {},
            "outcome": {"verification_passed": False, "applied": False},  # proposed only
            "source": "ora_learned",
            "cost_usd": 0.0,
        })
        return {"ok": True, "proposal": _sanitize(proposal), "tier_used": "L0_ora"}

    # ── L1–L3: cascade through LLM gateway ─────────────────────────
    ai = await _ask_llm_for_fix(issue)
    fix_json = ai.get("fix_json") or {}
    source = ai.get("source", "unknown")
    risk = (fix_json.get("risk_level") or "HIGH").upper()
    tier_label = {
        "sovereign":  "L1_sovereign",
        "openrouter": "L2_openrouter",
        "emergent":   "L3_emergent",
        "fallback":   "L3_failed",
    }.get(source, "L3_unknown")

    proposal = {
        "action_id": str(uuid.uuid4()),
        "kind": "emergent_code_fix",
        "agent": issue.get("agent") or issue.get("subject_agent"),
        "source": source,
        "fix": {
            "fix_type": fix_json.get("fix_type"),
            "files_changed": fix_json.get("files_changed", []),
            "config_changed": fix_json.get("config_changed"),
            "action_taken": fix_json.get("action_taken"),
            "diff": fix_json.get("diff"),
        },
        "root_cause": fix_json.get("root_cause"),
        "verification": fix_json.get("verification"),
        "risk_level": risk,
        "tier": "tier_1" if risk == "LOW" else "tier_2",
        "status": "pending",
        "issue": issue,
        "ts": _utc_now(),
        "cost_usd": 0.003 if source == "emergent" else 0.0,
        "message_plain": (
            f"{source.upper()} ne diagnose kiya: {fix_json.get('root_cause','(no root cause)')}. "
            f"Suggested action: {fix_json.get('action_taken','(none)')}. "
            f"Risk: {risk}."
        ),
    }
    try:
        await _db.ora_dev_actions.insert_one(proposal)
    except Exception as e:
        logger.warning(f"[code-fixer] L1-3 insert failed: {e}")

    # Ledger row — teaches future runs (outcome.applied=False yet, since
    # the fix has only been *proposed*; verification will flip this when
    # Dev Console applies + collective_scanner re-scans)
    await fix_learning_pipeline.learn_from_fix({
        "issue": issue,
        "fix": proposal["fix"],
        "outcome": {"verification_passed": False, "applied": False, "proposed": True},
        "source": source,
        "cost_usd": proposal["cost_usd"],
    })
    return {"ok": True, "proposal": _sanitize(proposal), "tier_used": tier_label}


def _sanitize(doc):
    if isinstance(doc, dict):
        return {k: _sanitize(v) for k, v in doc.items() if k != "_id"}
    if isinstance(doc, list):
        return [_sanitize(x) for x in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
