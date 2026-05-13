"""
triage_brain.py — Hybrid triage for AUREM incidents (iter 322ff).

Decision flow:
  1. Look up the incident's fingerprint in `incident_fingerprints`.
     If we've resolved this exact pattern before (`known_playbook` set),
     skip the LLM call and reuse the proven playbook → FREE + FAST.
  2. Otherwise, run a deterministic rule classifier on category/signature.
  3. If still uncertain, ask Groq (llama-3.3-70b) for a one-shot
     classification + suggested playbook. Token cost capped (≤500 out).

Outputs a JSON triage_summary written back to the incident row. The
result is descriptive only — actual EXECUTION of the playbook stays in
`incident_playbooks.py` (Phase 2, gated by founder approval for
destructive ops).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Known playbooks — keyed by category. Each "auto" entry means it CAN be
# executed without Telegram approval (read-only or safe retries). "manual"
# means it requires founder approval before execution.
PLAYBOOKS: dict[str, dict[str, Any]] = {
    "transient_502":     {"mode": "auto",   "chain": ["retry_after_5s"],                "max_retries": 3},
    "timeout":           {"mode": "auto",   "chain": ["retry_with_extended_timeout"],   "max_retries": 2},
    "backend_5xx":       {"mode": "auto",   "chain": ["check_backend_health", "log_to_legacy"], "max_retries": 1},
    "frontend_crash":    {"mode": "manual", "chain": ["alert_founder", "capture_stack"]},
    "frontend_unhandled_rejection": {"mode": "manual", "chain": ["alert_founder", "capture_stack"]},
    "tool_exception":    {"mode": "auto",   "chain": ["switch_llm_provider"],           "max_retries": 2},
    "route_missing":     {"mode": "manual", "chain": ["grep_for_route", "council_review"]},
    "db_conn":           {"mode": "manual", "chain": ["restart_backend", "verify_mongo_health"]},
    "dependency_missing":{"mode": "manual", "chain": ["legion_pip_install_gated"]},
    "permission_denied": {"mode": "manual", "chain": ["alert_founder"]},
    "legion_disconnect": {"mode": "manual", "chain": ["alert_founder_telegram"]},
    "ghost_blocked":     {"mode": "auto",   "chain": ["rotate_proxy", "retry_once"]},
    "council_stuck":     {"mode": "auto",   "chain": ["timeout_vote", "tally_partial"]},
    "rate_limit_hit":    {"mode": "auto",   "chain": ["backoff_and_retry"],             "max_retries": 1},
    "build_error":       {"mode": "manual", "chain": ["rollback_last_backup", "lint_and_restart"]},
    "unknown":           {"mode": "manual", "chain": ["alert_founder", "capture_full_context"]},
}

# Severity → user impact rough mapping
SEVERITY_IMPACT: dict[str, int] = {"P0": 10, "P1": 7, "P2": 4, "P3": 2}


async def fingerprint_known_playbook(db, fingerprint: str) -> str | None:
    """Has this fingerprint been resolved successfully before?"""
    if db is None or not fingerprint:
        return None
    doc = await db.incident_fingerprints.find_one(
        {"_id": fingerprint}, {"known_playbook": 1, "_id": 0}
    )
    return (doc or {}).get("known_playbook")


def deterministic_classify(category: str, signature: str) -> dict[str, Any]:
    """Rule-based first pass. No LLM cost."""
    pb = PLAYBOOKS.get(category) or PLAYBOOKS["unknown"]
    sig = (signature or "").lower()
    notes: list[str] = []
    # Tighten unknowns where signature is informative
    if category == "unknown":
        if "syntaxerror" in sig or "unexpected token" in sig:
            category = "frontend_crash"
            pb = PLAYBOOKS[category]
            notes.append("signature looked like JS parse error → frontend_crash")
        elif "502" in sig or "bad gateway" in sig:
            category = "transient_502"
            pb = PLAYBOOKS[category]
            notes.append("signature mentions 502 → transient_502")
        elif "timeout" in sig:
            category = "timeout"
            pb = PLAYBOOKS[category]
            notes.append("signature mentions timeout → timeout")
    return {
        "category":     category,
        "playbook":     pb,
        "auto_fixable": pb["mode"] == "auto",
        "rule_notes":   notes,
        "source":       "deterministic",
    }


async def llm_classify(title: str, detail: str, signature: str) -> dict[str, Any] | None:
    """Last-resort LLM triage. Capped to ~300 output tokens. Returns None on failure."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx
    except Exception:
        return None
    cats = sorted(PLAYBOOKS.keys())
    prompt = (
        f"Classify this AUREM incident into ONE category from {cats}. "
        f"Also give: severity (P0|P1|P2|P3), one-line root_cause_hypothesis, "
        f"and a boolean auto_fixable. Reply STRICT JSON only.\n\n"
        f"title: {title[:200]}\nsignature: {signature[:200]}\ndetail: {detail[:1200]}"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                          "Content-Type":  "application/json"},
                json={
                    "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    "messages": [
                        {"role": "system",
                         "content": "You are an SRE triage classifier. Output STRICT JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens":  300,
                    "response_format": {"type": "json_object"},
                },
            )
            if r.status_code != 200:
                logger.debug(f"[triage_brain] groq {r.status_code}: {r.text[:200]}")
                return None
            data = r.json()
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            parsed = json.loads(text)
            cat = parsed.get("category") or "unknown"
            if cat not in PLAYBOOKS:
                cat = "unknown"
            pb = PLAYBOOKS[cat]
            return {
                "category":              cat,
                "playbook":              pb,
                "severity_suggestion":   parsed.get("severity"),
                "root_cause_hypothesis": parsed.get("root_cause_hypothesis"),
                "auto_fixable":          bool(parsed.get("auto_fixable", pb["mode"] == "auto")),
                "source":                "llm",
            }
    except Exception as e:
        logger.debug(f"[triage_brain] llm_classify failed: {e}")
        return None


async def triage(db, incident: dict[str, Any]) -> dict[str, Any]:
    """Run hybrid triage on an incident dict (from incident_bus.report).

    Returns a triage_summary dict suitable for `incident_bus.update_status`.
    """
    category    = incident.get("category", "unknown")
    severity    = incident.get("severity", "P2")
    signature   = incident.get("signature", "")
    title       = incident.get("title", "")
    detail      = incident.get("detail", "")
    fingerprint = incident.get("fingerprint", "")

    # 1. Fingerprint match (free)
    known = await fingerprint_known_playbook(db, fingerprint)
    if known and known in PLAYBOOKS:
        return {
            "ok":            True,
            "category":      category,
            "severity":      severity,
            "user_impact":   SEVERITY_IMPACT.get(severity, 4),
            "playbook":      known,
            "playbook_def":  PLAYBOOKS[known],
            "auto_fixable":  PLAYBOOKS[known]["mode"] == "auto",
            "source":        "fingerprint_library",
            "decided_by":    "cache_hit",
        }

    # 2. Deterministic
    det = deterministic_classify(category, signature)
    if det["category"] != "unknown":
        return {
            "ok":           True,
            "category":     det["category"],
            "severity":     severity,
            "user_impact":  SEVERITY_IMPACT.get(severity, 4),
            "playbook":     det["category"],
            "playbook_def": det["playbook"],
            "auto_fixable": det["auto_fixable"],
            "source":       "deterministic",
            "rule_notes":   det["rule_notes"],
            "decided_by":   "rule_classifier",
        }

    # 3. LLM fallback
    llm = await llm_classify(title, detail, signature)
    if llm:
        return {
            "ok":              True,
            "category":        llm["category"],
            "severity":        llm.get("severity_suggestion") or severity,
            "user_impact":     SEVERITY_IMPACT.get(
                llm.get("severity_suggestion") or severity, 4
            ),
            "playbook":        llm["category"],
            "playbook_def":    llm["playbook"],
            "auto_fixable":    llm["auto_fixable"],
            "root_cause":      llm.get("root_cause_hypothesis"),
            "source":          "llm",
            "decided_by":      "groq_llama3.3",
        }

    # 4. Couldn't triage — escalate
    return {
        "ok":           True,
        "category":     "unknown",
        "severity":     severity,
        "user_impact":  SEVERITY_IMPACT.get(severity, 4),
        "playbook":     "unknown",
        "playbook_def": PLAYBOOKS["unknown"],
        "auto_fixable": False,
        "source":       "fallback",
        "decided_by":   "escalation_default",
    }
