"""
AUREM Sentinel — Stage 2: DIAGNOSE
====================================
Classifies issues by severity (P0-P3).
Uses LLM (Claude Haiku via OpenRouter) for root cause analysis on P0/P1.
Returns diagnosed issues with proposed fixes.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


async def diagnose_issues(db, issues: list) -> list:
    """
    STAGE 2: Classify and diagnose each issue.
    P0/P1: Use LLM for root cause analysis
    P2/P3: Pattern match from known_fixes database
    Returns list of diagnosed issues with proposed fixes.
    """
    if not issues:
        return []

    # Sort by severity (P0 first)
    sorted_issues = sorted(issues, key=lambda x: SEVERITY_ORDER.get(x.get("severity", "P3"), 3))

    diagnosed = []
    for issue in sorted_issues:
        severity = issue.get("severity", "P3")
        service = issue.get("service", "unknown")
        error = issue.get("error", "")

        # Check known_fixes database first
        known_fix = await _check_known_fixes(db, service, error)
        if known_fix:
            diagnosed.append({
                **issue,
                "diagnosis": known_fix.get("diagnosis", "Known issue"),
                "proposed_fix": known_fix.get("fix_type", ""),
                "fix_params": known_fix.get("fix_params", {}),
                "confidence": known_fix.get("success_rate", 0.5),
                "source": "known_fixes_db",
            })
            continue

        # P0/P1: Use LLM for root cause analysis
        if severity in ("P0", "P1"):
            llm_diagnosis = await _llm_diagnose(service, error)
            if llm_diagnosis:
                diagnosed.append({
                    **issue,
                    "diagnosis": llm_diagnosis.get("cause", "Unknown"),
                    "proposed_fix": llm_diagnosis.get("fix_type", "manual"),
                    "fix_params": llm_diagnosis.get("fix_params", {}),
                    "prevention": llm_diagnosis.get("prevention", ""),
                    "confidence": 0.7,
                    "source": "llm_claude",
                })
                continue

        # P2/P3 or LLM failed: use pattern matching
        pattern_fix = _pattern_match_fix(service, error)
        diagnosed.append({
            **issue,
            "diagnosis": pattern_fix["diagnosis"],
            "proposed_fix": pattern_fix["fix_type"],
            "fix_params": pattern_fix.get("fix_params", {}),
            "confidence": pattern_fix.get("confidence", 0.3),
            "source": "pattern_match",
        })

    # Log diagnoses
    try:
        if db is not None:
            for d in diagnosed:
                await db.sentinel_diagnoses.insert_one({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": d["service"],
                    "severity": d["severity"],
                    "diagnosis": d["diagnosis"],
                    "proposed_fix": d["proposed_fix"],
                    "source": d["source"],
                })
    except Exception as e:
        logger.warning(f"[Sentinel] Failed to log diagnosis: {e}")

    return diagnosed


async def _check_known_fixes(db, service: str, error: str) -> dict:
    """Check known_fixes collection for a matching pattern."""
    try:
        if db is None:
            return {}
        # Match by service + error substring
        fix = await db.known_fixes.find_one(
            {"issue_pattern": {"$regex": service, "$options": "i"}},
            {"_id": 0},
        )
        if fix and fix.get("success_rate", 0) > 0.5:
            return fix
    except Exception:
        pass
    return {}


async def _llm_diagnose(service: str, error: str) -> dict:
    """Use Claude Haiku via OpenRouter for root cause analysis."""
    try:
        from services.openrouter_client import call_ora_brain

        prompt = f"""AUREM issue:
Service: {service} | Error: {error} | Time: {datetime.now(timezone.utc).isoformat()}

Diagnose → JSON:
{{"cause":"<1 sentence>","fix_type":"<circuit_breaker_reset|cache_flush|fallback_activate|knowledge_resync|index_repair|service_restart|manual>","fix_params":{{}},"prevention":"<1 sentence>"}}"""

        result = await call_ora_brain(
            system_prompt="DevOps diagnostic AI. JSON only. No prose.",
            user_message=prompt,
            model_override="nvidia/nemotron-3-super-120b-a12b:free",
            max_tokens=300,
            temperature=0.2,
        )

        if result.get("content"):
            import json
            text = result["content"].strip()
            # Extract JSON from response
            if "{" in text and "}" in text:
                start = text.index("{")
                end = text.rindex("}")
                if end > start:
                    json_str = text[start:end + 1]
                    return json.loads(json_str)
    except Exception as e:
        logger.warning(f"[Sentinel] LLM diagnosis failed: {e}")
    return {}


def _pattern_match_fix(service: str, error: str) -> dict:
    """Fallback pattern matching for common issues."""
    error_lower = error.lower()

    if "circuit breaker" in error_lower or "tripped" in error_lower:
        return {"diagnosis": "Circuit breaker tripped due to repeated failures", "fix_type": "circuit_breaker_reset", "confidence": 0.9}

    if "401" in error_lower or "expired" in error_lower or "unauthorized" in error_lower:
        return {"diagnosis": f"{service} API key expired or invalid", "fix_type": "fallback_activate", "fix_params": {"service": service}, "confidence": 0.95}

    if "memory" in error_lower and ("high" in error_lower or "critical" in error_lower):
        return {"diagnosis": "System memory pressure", "fix_type": "cache_flush", "confidence": 0.7}

    if "overdue" in error_lower and "sync" in error_lower:
        return {"diagnosis": "Knowledge base not synced recently", "fix_type": "knowledge_resync", "confidence": 0.9}

    if "latency" in error_lower or "slow" in error_lower:
        return {"diagnosis": f"{service} response time degraded", "fix_type": "index_repair", "confidence": 0.5}

    if "connection" in error_lower or "refused" in error_lower:
        return {"diagnosis": f"{service} connection lost", "fix_type": "service_restart", "confidence": 0.6}

    return {"diagnosis": f"Unknown issue in {service}: {error[:100]}", "fix_type": "manual", "confidence": 0.1}
