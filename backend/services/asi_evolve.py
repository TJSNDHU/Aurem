"""
ASI-Evolve Sentinel Self-Improvement Loop
==========================================
Transforms AUREM from self-healing to self-learning.

Architecture:
  1. OBSERVE  — Pull failed/suboptimal OODA runs from episodic_memory
  2. ANALYZE  — Detect recurring failure patterns using Qwen 3.6 Plus ($0)
  3. SYNTHESIZE — Generate evolved instruction patches via Architect model
  4. SHADOW TEST — A/B simulate old vs new instruction (15% threshold)
  5. EVOLVE — Write approved patches to knowledge_base

Safety Gates:
  - Security, Auth, Stripe, Biometric routers require MANUAL_APPROVAL
  - All evolutions logged to sentinel_diagnoses
  - Shadow test must show >=15% confidence improvement
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

# Routers that NEVER auto-evolve — require manual approval
PROTECTED_DOMAINS = frozenset([
    "security", "auth", "biometric", "stripe", "payment",
    "jwt", "cors", "encryption", "vault",
])

CONFIDENCE_THRESHOLD = 0.15  # 15% improvement required


def set_db(database):
    global _db
    _db = database


def _get_db():
    if _db is None:
        raise RuntimeError("ASI-Evolve: DB not initialized")
    return _db


async def run_evolution_cycle(tenant_id: str = "aurem_platform") -> dict:
    """
    Main evolution cycle — runs periodically or on-demand.
    Returns a report of patterns detected and evolutions generated.
    """
    db = _get_db()
    cycle_id = f"evo_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"[ASI-Evolve] Starting evolution cycle {cycle_id}")

    async def _log_cycle(status: str, patterns_n: int, evolutions_n: int, failures_n: int = 0):
        """Record every cycle run so the dashboard reflects real activity."""
        try:
            await db.asi_evolve_cycles.insert_one({
                "cycle_id": cycle_id,
                "tenant_id": tenant_id,
                "status": status,
                "failures_analyzed": failures_n,
                "patterns_detected": patterns_n,
                "evolutions_generated": evolutions_n,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug(f"[ASI-Evolve] cycle log failed: {e}")

    # ─── Step 1: OBSERVE — Pull failure data ──────────────────────
    failures = await _observe_failures(db, tenant_id)
    if not failures:
        logger.info("[ASI-Evolve] No failures to analyze")
        await _log_cycle("clean", 0, 0, 0)
        return {"cycle_id": cycle_id, "status": "clean", "patterns": 0, "evolutions": 0}

    # ─── Step 2: ANALYZE — Detect patterns ────────────────────────
    patterns = await _analyze_patterns(db, failures)
    if not patterns:
        await _log_cycle("no_patterns", 0, 0, len(failures))
        return {"cycle_id": cycle_id, "status": "no_patterns", "patterns": 0, "evolutions": 0}

    # ─── Step 3-5: SYNTHESIZE → SHADOW TEST → EVOLVE ─────────────
    evolutions = []
    for pattern in patterns:
        evolution = await _synthesize_and_test(db, tenant_id, cycle_id, pattern)
        if evolution:
            evolutions.append(evolution)

    # Log cycle to sentinel + cycles collection
    cycle_report = {
        "cycle_id": cycle_id,
        "tenant_id": tenant_id,
        "type": "evolution_cycle",
        "source": "asi_evolve",
        "failures_analyzed": len(failures),
        "patterns_detected": len(patterns),
        "evolutions_generated": len(evolutions),
        "evolutions_approved": sum(1 for e in evolutions if e.get("status") == "approved"),
        "evolutions_pending": sum(1 for e in evolutions if e.get("status") == "pending_approval"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sentinel_diagnoses.insert_one(cycle_report)
    await _log_cycle("completed", len(patterns), len(evolutions), len(failures))

    return {
        "cycle_id": cycle_id,
        "status": "completed",
        "patterns": len(patterns),
        "evolutions": len(evolutions),
        "details": evolutions,
    }


async def _observe_failures(db, tenant_id: str) -> list:
    """Pull unsuccessful outcomes from episodic memory and pipeline runs."""
    failures = []

    # From episodic memory — failed actions
    episodes = await db.episodic_memory.find(
        {"tenant_id": tenant_id, "outcome": {"$in": ["failure", "error", "timeout", "partial"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(100).to_list(100)
    failures.extend(episodes)

    # From pipeline runs — non-clean completions
    pipeline_fails = await db.pipeline_runs.find(
        {"tenant_id": tenant_id, "final_status": {"$nin": ["completed", "completed_no_issues", "completed_no_actions"]}},
        {"_id": 0, "run_id": 1, "final_status": 1, "stage_timings": 1, "started_at": 1}
    ).sort("started_at", -1).limit(50).to_list(50)
    for pf in pipeline_fails:
        pf["source"] = "pipeline"
        pf["outcome"] = pf.get("final_status", "unknown")
    failures.extend(pipeline_fails)

    # From sentinel — performance anomalies
    anomalies = await db.sentinel_diagnoses.find(
        {"tenant_id": tenant_id, "type": "performance_anomaly"},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    for a in anomalies:
        a["source"] = "sentinel"
        a["outcome"] = "slow"
    failures.extend(anomalies)

    return failures


async def _analyze_patterns(db, failures: list) -> list:
    """Use LLM to detect recurring failure patterns."""
    if not failures:
        return []

    # Group failures by type/stage
    failure_summary = {}
    for f in failures:
        key = f.get("action_type") or f.get("stage") or f.get("source", "unknown")
        if key not in failure_summary:
            failure_summary[key] = {"count": 0, "outcomes": [], "samples": []}
        failure_summary[key]["count"] += 1
        failure_summary[key]["outcomes"].append(f.get("outcome", "unknown"))
        if len(failure_summary[key]["samples"]) < 3:
            failure_summary[key]["samples"].append(
                json.dumps({k: v for k, v in f.items() if k not in ("_id",)}, default=str)[:500]
            )

    # Filter: only patterns with 3+ occurrences (evolution trigger threshold)
    recurring = {k: v for k, v in failure_summary.items() if v["count"] >= 3}
    if not recurring:
        return []

    # Use LLM to analyze patterns
    try:
        from services.openrouter_client import call_agent_model

        analysis_prompt = (
            "You are an AI systems analyst for AUREM, an autonomous business platform.\n"
            "Analyze these recurring failure patterns and identify the ROOT CAUSE for each.\n"
            "For each pattern, suggest a specific INSTRUCTION IMPROVEMENT that would prevent this class of error.\n\n"
            "Output JSON array: [{\"pattern_id\": \"...\", \"domain\": \"...\", \"root_cause\": \"...\", "
            "\"current_behavior\": \"...\", \"improved_instruction\": \"...\", \"confidence\": 0.0-1.0}]"
        )

        user_msg = json.dumps(recurring, indent=2, default=str)

        result = await call_agent_model(
            "architect", analysis_prompt, user_msg,
            temperature=0.3, max_tokens=2000
        )

        text = result.get("text", "")

        # Parse JSON from response
        import re
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            patterns = json.loads(json_match.group())
            return patterns

    except Exception as e:
        logger.warning(f"[ASI-Evolve] Pattern analysis failed: {e}")

    # Fallback: generate patterns without LLM
    patterns = []
    for key, data in recurring.items():
        patterns.append({
            "pattern_id": f"pat_{key}",
            "domain": key,
            "root_cause": f"Recurring {key} failures ({data['count']}x)",
            "current_behavior": f"Outcomes: {', '.join(set(data['outcomes'])[:3])}",
            "improved_instruction": f"Add retry logic and better error handling for {key} operations",
            "confidence": 0.5,
        })
    return patterns


async def _synthesize_and_test(db, tenant_id: str, cycle_id: str, pattern: dict) -> Optional[dict]:
    """Generate evolution patch, shadow test it, and deploy if approved."""

    domain = (pattern.get("domain") or "").lower()
    requires_approval = any(p in domain for p in PROTECTED_DOMAINS)

    # ─── SYNTHESIZE: Generate evolved instruction ─────────────────
    evolved_instruction = pattern.get("improved_instruction", "")

    try:
        from services.openrouter_client import call_agent_model

        synth_prompt = (
            "You are the AUREM Architect agent. Generate a precise SYSTEM INSTRUCTION PATCH "
            "that will prevent this class of failure in future pipeline runs.\n\n"
            "The patch should be:\n"
            "1. Specific and actionable (not vague)\n"
            "2. Compatible with the existing OODA pipeline\n"
            "3. A single paragraph that can be prepended to agent prompts\n\n"
            "Output JSON: {\"evolved_instruction\": \"...\", \"target_stages\": [...], \"confidence_score\": 0.0-1.0}"
        )

        result = await call_agent_model(
            "architect", synth_prompt,
            json.dumps(pattern, default=str),
            temperature=0.3, max_tokens=1000
        )

        text = result.get("text", "")
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            evolved_instruction = parsed.get("evolved_instruction", evolved_instruction)
            target_stages = parsed.get("target_stages", [domain])
            new_confidence = parsed.get("confidence_score", 0.6)
        else:
            target_stages = [domain]
            new_confidence = 0.6

    except Exception as e:
        logger.warning(f"[ASI-Evolve] Synthesis failed for {domain}: {e}")
        target_stages = [domain]
        new_confidence = 0.5

    # ─── SHADOW TEST: A/B simulation ─────────────────────────────
    shadow_result = await _shadow_test(
        db, pattern, evolved_instruction, new_confidence
    )

    improvement = shadow_result.get("improvement_pct", 0)
    shadow_passed = improvement >= CONFIDENCE_THRESHOLD * 100

    # ─── EVOLVE: Deploy or queue for approval ────────────────────
    if requires_approval:
        status = "pending_approval"
    elif shadow_passed:
        status = "approved"
    else:
        status = "rejected"
        logger.info(f"[ASI-Evolve] NEURAL NOISE — {domain} evolution rejected "
                     f"(improvement {improvement:.1f}% < threshold {CONFIDENCE_THRESHOLD * 100}%)")

    evolution_doc = {
        "cycle_id": cycle_id,
        "tenant_id": tenant_id,
        "pattern_id": pattern.get("pattern_id", f"pat_{domain}"),
        "domain": domain,
        "root_cause": pattern.get("root_cause", ""),
        "original_instruction": pattern.get("current_behavior", ""),
        "evolved_instruction": evolved_instruction,
        "target_stages": target_stages,
        "confidence_score": new_confidence,
        "shadow_test": shadow_result,
        "improvement_pct": improvement,
        "status": status,
        "rejection_reason": "neural_noise" if status == "rejected" else None,
        "requires_approval": requires_approval,
        "applied_at": None if status != "approved" else datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.self_improvement.insert_one(evolution_doc)

    # If approved, deploy to knowledge_base
    if status == "approved":
        await _deploy_evolution(db, tenant_id, evolution_doc)

    return {
        "pattern_id": pattern.get("pattern_id"),
        "domain": domain,
        "status": status,
        "improvement_pct": improvement,
        "shadow_passed": shadow_passed,
        "requires_approval": requires_approval,
    }


async def _shadow_test(db, pattern: dict, evolved_instruction: str, new_confidence: float) -> dict:
    """
    A/B simulation: Compare old vs evolved instruction.
    Run A: Score based on historical failure rate
    Run B: Score based on evolved instruction confidence
    Must achieve >=15% improvement.
    """
    domain = pattern.get("domain", "unknown")

    # Run A: Score from historical data (failures / total)
    old_failure_rate = 0.5  # Default
    try:
        total = await db.episodic_memory.count_documents(
            {"action_type": domain}
        )
        failures = await db.episodic_memory.count_documents(
            {"action_type": domain, "outcome": {"$in": ["failure", "error", "timeout"]}}
        )
        if total > 0:
            old_failure_rate = failures / total
    except Exception:
        pass

    old_score = (1 - old_failure_rate) * 100  # Convert to 0-100

    # Run B: Score based on LLM confidence + pattern analysis
    new_score = new_confidence * 100

    improvement = new_score - old_score

    return {
        "run_a_score": round(old_score, 1),
        "run_b_score": round(new_score, 1),
        "improvement_pct": round(improvement, 1),
        "threshold_pct": CONFIDENCE_THRESHOLD * 100,
        "passed": improvement >= CONFIDENCE_THRESHOLD * 100,
        "verdict": "EVOLVED" if improvement >= CONFIDENCE_THRESHOLD * 100 else "NEURAL_NOISE",
    }


async def _deploy_evolution(db, tenant_id: str, evolution: dict):
    """Write approved evolution to knowledge_base and invalidate scout cache."""
    pattern_id = evolution.get("pattern_id", "unknown")

    # Write to knowledge_base
    await db.knowledge_base.update_one(
        {"pattern_id": pattern_id, "tenant_id": tenant_id},
        {"$set": {
            "type": "evolved_instruction",
            "pattern_id": pattern_id,
            "domain": evolution.get("domain"),
            "instruction": evolution.get("evolved_instruction"),
            "target_stages": evolution.get("target_stages", []),
            "confidence": evolution.get("confidence_score", 0),
            "source": "asi_evolve",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
        }},
        upsert=True,
    )

    # Invalidate scout cache for evolved domains (in-memory + Redis)
    try:
        from utils.ttl_cache import cache_invalidate_by_domain
        domain = evolution.get("domain", "")
        if domain:
            cleared = cache_invalidate_by_domain(domain)
            logger.info(f"[ASI-Evolve] Scout cache purged: {cleared} entries for domain '{domain}'")
    except Exception as e:
        logger.warning(f"[ASI-Evolve] Cache invalidation failed: {e}")

    logger.info(f"[ASI-Evolve] Deployed evolution {pattern_id} to knowledge_base")


async def get_evolved_instructions(db, tenant_id: str, stage: str) -> list:
    """
    Retrieve evolved instructions for a specific pipeline stage.
    Called by flow_coordinator before each stage runs.
    """
    instructions = await db.knowledge_base.find(
        {
            "tenant_id": tenant_id,
            "type": "evolved_instruction",
            "target_stages": stage,
        },
        {"_id": 0, "instruction": 1, "confidence": 1, "pattern_id": 1}
    ).sort("confidence", -1).limit(5).to_list(5)

    return instructions


async def approve_evolution(evolution_id: str) -> dict:
    """Manually approve a pending evolution (for protected domains)."""
    db = _get_db()

    evo = await db.self_improvement.find_one(
        {"pattern_id": evolution_id, "status": "pending_approval"},
        {"_id": 0}
    )
    if not evo:
        return {"success": False, "error": "Evolution not found or already processed"}

    await db.self_improvement.update_one(
        {"pattern_id": evolution_id, "status": "pending_approval"},
        {"$set": {
            "status": "approved",
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": "admin_manual",
        }}
    )

    await _deploy_evolution(db, evo.get("tenant_id", "aurem_platform"), evo)

    return {"success": True, "pattern_id": evolution_id, "status": "approved"}


async def reject_evolution(evolution_id: str) -> dict:
    """Reject a pending evolution."""
    db = _get_db()

    result = await db.self_improvement.update_one(
        {"pattern_id": evolution_id, "status": "pending_approval"},
        {"$set": {
            "status": "rejected",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejected_by": "admin_manual",
        }}
    )

    return {"success": result.modified_count > 0, "pattern_id": evolution_id, "status": "rejected"}


async def get_evolution_stats(tenant_id: str = None) -> dict:
    """Get ASI-Evolve statistics for dashboard. tenant_id=None → all tenants."""
    db = _get_db()

    q = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.self_improvement.count_documents(q)
    approved = await db.self_improvement.count_documents({**q, "status": "approved"})
    pending = await db.self_improvement.count_documents({**q, "status": "pending_approval"})
    rejected = await db.self_improvement.count_documents({**q, "status": "rejected"})

    # Latest evolutions
    recent = await db.self_improvement.find(
        q,
        {"_id": 0, "cycle_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)

    # Active knowledge_base instructions (cross-tenant admin view)
    kb_q = {"type": "evolved_instruction"}
    if tenant_id:
        kb_q["tenant_id"] = tenant_id
    active_instructions = await db.knowledge_base.count_documents(kb_q)

    # Cycles run (activity indicator — even "clean" cycles count)
    cycles_q = {"tenant_id": tenant_id} if tenant_id else {}
    cycles_run = await db.asi_evolve_cycles.count_documents(cycles_q)
    last_cycle = await db.asi_evolve_cycles.find_one(
        cycles_q, {"_id": 0}, sort=[("created_at", -1)]
    )

    return {
        "total_evolutions": total,
        "approved": approved,
        "pending_approval": pending,
        "rejected": rejected,
        "active_instructions": active_instructions,
        "success_rate": round((approved / total * 100) if total > 0 else 0, 1),
        "recent": recent,
        "cycles_run": cycles_run,
        "last_cycle": last_cycle,
    }
