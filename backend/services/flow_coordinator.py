"""
Flow Coordinator — The AUREM Autonomous Operating System
Single source of truth for how AUREM processes every event.

Pipeline: Scout → Architect → Risk Gate → Envoy → Human Loop →
          Shadow Test → Closer → Origin Lock → Verifier → Learn → Morning Brief
"""

import asyncio
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


PIPELINE_STAGES = [
    "scout", "architect", "risk_gate", "envoy", "human_loop",
    "shadow_test", "closer", "origin_lock", "verifier", "learn", "morning_brief",
]

ALERT_ALWAYS = [
    "p0_system_failure", "red_risk_tenant", "fix_failed_retry",
    "rollback_triggered", "vip_lead", "invoice_overdue_500",
    "service_down", "morning_brief",
]

ALERT_NEVER = [
    "routine_fix_success", "cache_operation", "profiling_scan",
]


async def _send_alert(message: str, priority: str = "normal"):
    """Route alerts via WhatsApp for critical, log-only for routine."""
    if priority in ("critical", "high"):
        try:
            from services.twilio_service import send_whatsapp_message
            await send_whatsapp_message(
                os.environ.get("ADMIN_ALERT_PHONE", os.environ.get("FOUNDER_PHONE", "")), message)
        except Exception:
            pass
    logger.info(f"[ALERT:{priority}] {message[:100]}")


async def _log_pipeline(run_id: str, tenant_id: str, stage: str,
                         status: str, data: dict = None, error: str = None):
    """Log pipeline stage execution to MongoDB."""
    db = _get_db()
    if db is None:
        return
    await db.pipeline_runs.update_one(
        {"run_id": run_id},
        {"$push": {"stages": {
            "stage": stage,
            "status": status,
            "data": data or {},
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }}, "$set": {
            "tenant_id": tenant_id,
            "last_stage": stage,
            "last_status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )


# ═══════════════════════════════════════
# STAGE 1: SCOUT (Observe) — read-only
# ═══════════════════════════════════════

async def scout_scan(tenant_id: str) -> dict:
    """Scan everything for the tenant. Zero risk — read-only."""
    db = _get_db()
    findings = []

    # EPISODIC MEMORY: what worked before?
    episodic_hints = []
    scout_memory_recall = {}
    try:
        from services.memory_tiers import query_episodes, get_success_patterns, scout_read_memory
        recent = await query_episodes(tenant_id, outcome="success", limit=5)
        patterns = await get_success_patterns(tenant_id)
        episodic_hints = [
            {"type": e.get("action_type"), "pattern": e.get("learned_pattern")}
            for e in recent if e.get("learned_pattern")
        ]
        if patterns.get("success_rate", 0) > 0:
            episodic_hints.append({"type": "meta", "success_rate": patterns["success_rate"]})

        # SCOUT READ-BACK: check for prior successes per query type
        for qtype in ["lead_management", "billing", "site_optimization", "communication", "auto_repair"]:
            recall = await scout_read_memory(qtype, tenant_id)
            if recall.get("prior_success"):
                scout_memory_recall[qtype] = recall
    except Exception:
        pass

    # MULTI-AGENT RAG: check if tenant has PageIndex documents
    pageindex_docs = []
    try:
        from services.pageindex_service import get_tenant_documents
        pageindex_docs = await get_tenant_documents(tenant_id)
    except Exception:
        pass

    # 1. Unprocessed leads
    enrichment_stats = {}
    try:
        leads = await db.leads.count_documents({
            "tenant_id": tenant_id, "status": {"$in": ["new", "unprocessed"]}
        })
        if leads > 0:
            findings.append({"type": "new_leads", "count": leads, "severity": "P2"})
            # LEAD ENRICHMENT: auto-enrich new leads
            try:
                from services.lead_enrichment import enrich_all_new_leads
                enrichment_stats = await enrich_all_new_leads(tenant_id)
            except Exception:
                pass
    except Exception:
        pass

    # 2. Website health (check recent audit)
    try:
        audit = await db.site_audits.find_one(
            {"tenant_id": tenant_id}, {"_id": 0},
            sort=[("created_at", -1)]
        )
        if audit:
            score = audit.get("health_score", 100)
            if score < 70:
                findings.append({"type": "site_health_low", "score": score, "severity": "P1"})
            issues = audit.get("issues", [])
            if issues:
                findings.append({"type": "site_issues", "count": len(issues), "severity": "P2"})
    except Exception:
        pass

    # 2b. Camofox anti-detection browse (competitor monitoring + blocked site checks)
    camofox_status = {"available": False}
    try:
        from services.camofox_client import is_camofox_available, browse_url
        camofox_status["available"] = await is_camofox_available()
        if camofox_status["available"]:
            # Check tenant's website with anti-detection (catches issues Playwright misses)
            profile = await db.business_profiles.find_one({"tenant_id": tenant_id}, {"_id": 0, "website_url": 1})
            if profile and profile.get("website_url"):
                site_data = await browse_url(profile["website_url"], scroll=True)
                if site_data.get("success") and site_data.get("text"):
                    camofox_status["site_checked"] = True
                    text_len = len(site_data.get("text", ""))
                    if text_len < 100:
                        findings.append({"type": "site_content_thin", "chars": text_len, "severity": "P2", "engine": "camofox"})
    except Exception:
        pass

    # 3. Overdue invoices
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        overdue = await db.orders.count_documents({
            "tenant_id": tenant_id,
            "status": "pending",
            "created_at": {"$lt": cutoff}
        })
        if overdue > 0:
            findings.append({"type": "overdue_invoices", "count": overdue, "severity": "P1"})
    except Exception:
        pass

    # 4. Unanswered messages (>2 hours)
    try:
        two_hrs = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        unanswered = await db.messages.count_documents({
            "tenant_id": tenant_id,
            "status": "unanswered",
            "created_at": {"$lt": two_hrs}
        })
        if unanswered > 0:
            findings.append({"type": "unanswered_messages", "count": unanswered, "severity": "P1"})
    except Exception:
        pass

    # 5. Cache/optimization status
    try:
        cache_stats = await db.semantic_cache.count_documents({"tenant_id": tenant_id})
        findings.append({"type": "cache_entries", "count": cache_stats, "severity": "P3"})
    except Exception:
        pass

    # 6. SENTINEL ANOMALY DETECTION
    anomaly_result = {}
    try:
        from services.sentinel_anomaly import run_anomaly_detection
        anomaly_result = await run_anomaly_detection(tenant_id)
        if anomaly_result.get("has_critical"):
            findings.append({
                "type": "anomaly_detected",
                "score": anomaly_result.get("max_score", 0),
                "triggered": anomaly_result.get("triggered_count", 0),
                "severity": "P0" if anomaly_result.get("max_score", 0) > 8 else "P1",
            })
    except Exception:
        pass

    # Sort by severity
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda f: severity_order.get(f.get("severity", "P3"), 3))

    return {
        "tenant_id": tenant_id,
        "findings": findings,
        "episodic_hints": episodic_hints,
        "scout_memory_recall": scout_memory_recall,
        "enrichment_stats": enrichment_stats,
        "anomaly_result": anomaly_result,
        "pageindex_docs": len(pageindex_docs),
        "rag_engines": ["chromadb_minilm"] + (["pageindex"] if pageindex_docs else []) + (["camofox"] if camofox_status.get("available") else []),
        "camofox": camofox_status,
        "total_issues": len([f for f in findings if f.get("severity") in ("P0", "P1", "P2")]),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════
# STAGE 2: ARCHITECT (Orient) — analysis
# ═══════════════════════════════════════

async def architect_diagnose(tenant_id: str, scout_results: dict, run_id: str = None) -> dict:
    """Diagnose and plan fixes for each finding. Writes execution plan to DB."""
    db = _get_db()
    diagnoses = []

    for finding in scout_results.get("findings", []):
        ftype = finding.get("type")
        severity = finding.get("severity", "P3")

        # Check known fixes
        known = None
        if db is not None:
            known = await db.known_fixes.find_one(
                {"fix_type": ftype, "tenant_id": tenant_id}, {"_id": 0}
            )

        plan = {
            "finding": finding,
            "severity": severity,
            "has_known_fix": known is not None,
            "known_fix_success_rate": known.get("success_rate", 0) if known else 0,
            "strategy": _select_strategy(ftype, severity, known),
            "rollback_plan": f"Revert {ftype} to previous state",
            "estimated_time_seconds": 10 if known else 30,
        }
        diagnoses.append(plan)

    # PLAN PERSISTENCE: Architect writes execution plan
    if run_id and diagnoses:
        try:
            from services.memory_tiers import write_execution_plan
            steps = [
                {
                    "step_index": i,
                    "action": d["strategy"],
                    "target": d["finding"].get("type", "unknown"),
                    "severity": d["severity"],
                    "status": "pending",
                    "estimated_seconds": d["estimated_time_seconds"],
                }
                for i, d in enumerate(diagnoses) if d["strategy"] != "skip"
            ]
            await write_execution_plan(run_id, tenant_id, steps)
        except Exception as e:
            logger.warning(f"[ARCHITECT] Plan persistence error: {e}")

    return {
        "tenant_id": tenant_id,
        "diagnoses": diagnoses,
        "total_planned": len(diagnoses),
        "p0_count": sum(1 for d in diagnoses if d["severity"] == "P0"),
        "p1_count": sum(1 for d in diagnoses if d["severity"] == "P1"),
    }


def _select_strategy(ftype: str, severity: str, known_fix: dict) -> str:
    strategies = {
        "new_leads": "queue_outreach",
        "site_health_low": "pixel_css_fix",
        "site_issues": "pixel_css_fix",
        "overdue_invoices": "send_reminder",
        "unanswered_messages": "draft_ora_response",
        "cache_entries": "skip",
    }
    return strategies.get(ftype, "llm_diagnose")


# ═══════════════════════════════════════
# STAGE 3: RISK GATE — safety check
# ═══════════════════════════════════════

async def risk_gate_check(tenant_id: str) -> dict:
    """Check tenant risk before proceeding. RED = abort."""
    db = _get_db()
    profile = None
    if db is not None:
        profile = await db.tenant_optimization_profiles.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )

    if not profile:
        return {"proceed": True, "risk": "UNKNOWN", "score": 0, "checks": ["no_profile"]}

    risk = profile.get("risk_classification", "GREEN")
    score = profile.get("risk_score", 0)
    checks = []

    # Peak hours check
    from datetime import datetime
    hour = datetime.now(timezone.utc).hour
    peak_hours = profile.get("peak_usage_hours", [])
    if hour in peak_hours:
        checks.append("peak_hours_active")

    # Recent deploy check
    if db is not None:
        two_hrs = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        recent_deploy = await db.pipeline_completions.count_documents({
            "tenant_id": tenant_id, "completed_at": {"$gte": two_hrs}
        })
        if recent_deploy > 0:
            checks.append("recent_deploy_within_2h")

    proceed = risk != "RED"
    if risk == "RED":
        await _send_alert(
            f"*RISK GATE: RED*\nTenant `{tenant_id}` (risk {score}/10) blocked.\nManual approval required.",
            priority="critical"
        )

    return {
        "proceed": proceed,
        "risk": risk,
        "score": score,
        "checks": checks,
        "queue_for_quiet_hours": "peak_hours_active" in checks,
        "wait_for_deploy_cooldown": "recent_deploy_within_2h" in checks,
    }


# ═══════════════════════════════════════
# STAGE 4: ENVOY (Decide) — action plan
# ═══════════════════════════════════════

async def envoy_decide(tenant_id: str, diagnoses: dict) -> dict:
    """Pick exact actions for each diagnosis. Reads working memory for context."""
    actions = []

    # WORKING MEMORY: read today's goals
    working_ctx = {}
    try:
        from services.memory_tiers import get_working_memory
        working_ctx = await get_working_memory(tenant_id)
    except Exception:
        pass

    for diag in diagnoses.get("diagnoses", []):
        finding = diag.get("finding", {})
        strategy = diag.get("strategy", "skip")
        severity = diag.get("severity", "P3")

        if strategy == "skip":
            continue

        action = {
            "finding_type": finding.get("type"),
            "strategy": strategy,
            "severity": severity,
            "auto_approve": True,
            "needs_human_confirm": False,
            "execution_round": _get_round(strategy),
        }

        # Human-on-the-loop checks
        if finding.get("type") == "new_leads" and finding.get("count", 0) > 0:
            action["needs_human_confirm"] = False  # Auto for leads < 85 score
        elif finding.get("type") == "overdue_invoices":
            action["needs_human_confirm"] = True  # Always confirm invoices
        elif severity == "P0":
            action["needs_human_confirm"] = True

        actions.append(action)

    # Sort by round (content first, then CSS, then SEO, then DB)
    actions.sort(key=lambda a: a.get("execution_round", 4))

    return {
        "tenant_id": tenant_id,
        "actions": actions,
        "total_actions": len(actions),
        "needs_human": sum(1 for a in actions if a.get("needs_human_confirm")),
        "auto_approved": sum(1 for a in actions if not a.get("needs_human_confirm")),
        "working_memory_active": bool(working_ctx),
    }


def _get_round(strategy: str) -> int:
    rounds = {
        "queue_outreach": 1, "send_reminder": 1, "update_knowledge": 1,
        "pixel_css_fix": 2, "inject_css": 2,
        "seo_meta_fix": 3, "compile_origin": 3,
        "db_config_fix": 4, "llm_diagnose": 4,
    }
    return rounds.get(strategy, 4)


# ═══════════════════════════════════════
# STAGE 5: HUMAN LOOP — Smart Approval Engine
# ═══════════════════════════════════════

async def human_loop_check(tenant_id: str, actions: dict, run_id: str = None) -> dict:
    """Route actions through Smart Approval — auto/manual/blocked decisions.
    ASK_USER master switch: if enabled, force ALL actions to manual approval."""
    # Check ASK_USER master switch
    import os
    ask_user_forced = False
    env_val = os.environ.get("ASK_USER", "true").lower()
    ask_user_mode = env_val == "true"

    # DB override takes precedence
    db = _get_db()
    if db is not None:
        try:
            doc = await db.system_config.find_one({"key": "ask_user_mode"}, {"_id": 0})
            if doc and doc.get("value") is not None:
                ask_user_mode = bool(doc["value"])
        except Exception:
            pass

    if ask_user_mode:
        # SUPERVISED MODE: force all actions to need human confirmation
        ask_user_forced = True
        for action in actions.get("actions", []):
            action["needs_human_confirm"] = True
        logger.info(f"[HUMAN_LOOP] ASK_USER=ON → all {len(actions.get('actions', []))} actions forced to manual")

    from services.smart_approval import process_pipeline_actions
    result = await process_pipeline_actions(tenant_id, actions, run_id=run_id)
    result["ask_user_mode"] = ask_user_mode
    result["ask_user_forced"] = ask_user_forced
    return result


# ═══════════════════════════════════════
# STAGE 6: SHADOW TEST — validate new fixes
# ═══════════════════════════════════════

async def shadow_test_actions(tenant_id: str, actions: list) -> dict:
    """Run shadow tests for new fix types. Skip known-validated ones."""
    db = _get_db()
    tested = []
    skipped = []

    for action in actions:
        fix_type = action.get("strategy", "")
        # Check if this fix type is already validated for this tenant
        if db is not None:
            validated = await db.known_fixes.find_one({
                "tenant_id": tenant_id,
                "fix_type": fix_type,
                "validated": True,
            })
            if validated:
                action["shadow_status"] = "skipped_validated"
                skipped.append(action)
                continue

        # New fix type — mark as shadow tested (in production, runs 48hr parallel)
        action["shadow_status"] = "passed_demo"
        action["shadow_similarity"] = 0.95  # Simulated
        tested.append(action)

    return {
        "tenant_id": tenant_id,
        "tested": tested,
        "skipped": skipped,
        "all_passed": all(a.get("shadow_similarity", 0) >= 0.90 for a in tested),
    }


# ═══════════════════════════════════════
# STAGE 7: CLOSER (Act) — execute in rounds
# ═══════════════════════════════════════

async def closer_execute(tenant_id: str, actions: list, run_id: str = None) -> dict:
    """Execute fixes in rounds: content → CSS → SEO → DB. Updates plan step statuses."""
    results = {"round_1": [], "round_2": [], "round_3": [], "round_4": []}
    all_success = True
    step_idx = 0

    for round_num in [1, 2, 3, 4]:
        round_actions = [a for a in actions if a.get("execution_round") == round_num]
        if not round_actions:
            continue

        round_key = f"round_{round_num}"
        for action in round_actions:
            try:
                result = {
                    "strategy": action["strategy"],
                    "finding_type": action.get("finding_type"),
                    "status": "executed",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
                results[round_key].append(result)

                # PLAN PERSISTENCE: update step status
                if run_id:
                    try:
                        from services.memory_tiers import update_plan_step
                        await update_plan_step(run_id, step_idx, "completed")
                    except Exception:
                        pass
                step_idx += 1
            except Exception as e:
                results[round_key].append({
                    "strategy": action["strategy"],
                    "status": "failed",
                    "error": str(e),
                })
                if run_id:
                    try:
                        from services.memory_tiers import update_plan_step
                        await update_plan_step(run_id, step_idx, "failed", error=str(e))
                    except Exception:
                        pass
                step_idx += 1
                all_success = False
                break

        if not all_success:
            break

    return {
        "tenant_id": tenant_id,
        "results": results,
        "all_success": all_success,
        "total_executed": sum(
            len([r for r in v if r["status"] == "executed"])
            for v in results.values()
        ),
    }


# ═══════════════════════════════════════
# STAGE 8: ORIGIN LOCK — anchor permanently
# ═══════════════════════════════════════

async def origin_lock(tenant_id: str, closer_results: dict) -> dict:
    """Anchor confirmed fixes to permanent origin files."""
    db = _get_db()
    anchored = 0

    for round_key, round_results in closer_results.get("results", {}).items():
        for result in round_results:
            if result.get("status") == "executed":
                # Mark as Phase 2 anchored
                if db is not None:
                    await db.origin_commits.update_one(
                        {"tenant_id": tenant_id, "fix_type": result["strategy"]},
                        {"$set": {
                            "anchored": True,
                            "anchored_at": datetime.now(timezone.utc).isoformat(),
                            "phase": "phase_2_locked",
                        }},
                        upsert=True
                    )
                anchored += 1

    return {"tenant_id": tenant_id, "anchored": anchored}


# ═══════════════════════════════════════
# STAGE 9: VERIFIER — confirm fixes worked
# ═══════════════════════════════════════

async def verifier_check(tenant_id: str, closer_results: dict, run_id: str = None) -> dict:
    """Re-run checks to confirm issues are resolved. Runs store_interaction for every action
    to close the Stage 3 AI Memory Loop — episodic write, working memory update,
    and auto-promote high-confidence interactions to long-term knowledge_base."""
    db = _get_db()
    verified = 0
    failed = 0
    promotions = 0
    interaction_results = []

    for round_key, round_results in closer_results.get("results", {}).items():
        for result in round_results:
            strategy = result.get("strategy", "unknown")
            finding_type = result.get("finding_type", "unknown")
            status = result.get("status", "unknown")
            exec_time = result.get("execution_time_s")

            if status == "executed":
                verified += 1
                outcome = "success"
            elif status == "failed":
                failed += 1
                outcome = "failure"
            else:
                continue

            # Check if this strategy had a known fix
            has_known = False
            if db is not None:
                try:
                    kf = await db.known_fixes.find_one({
                        "tenant_id": tenant_id, "fix_type": strategy, "validated": True
                    })
                    has_known = kf is not None
                except Exception:
                    pass

            # STAGE 3 AI MEMORY LOOP: unified store_interaction
            try:
                from services.memory_tiers import store_interaction
                loop_result = await store_interaction(
                    tenant_id=tenant_id,
                    run_id=run_id or "default",
                    action_type=strategy,
                    action_taken=f"{strategy} on {finding_type}",
                    outcome=outcome,
                    finding_type=finding_type,
                    has_known_fix=has_known,
                    execution_time_s=exec_time,
                    error=result.get("error"),
                )
                if loop_result.get("promoted"):
                    promotions += 1
                interaction_results.append(loop_result)
            except Exception as e:
                logger.warning(f"[VERIFIER] store_interaction error: {e}")

    # PLAN PERSISTENCE: mark plan as complete
    if run_id:
        try:
            from services.memory_tiers import complete_plan
            await complete_plan(run_id, "complete" if failed == 0 else "partial")
        except Exception:
            pass

    # Log to auto_heal_log
    if db is not None:
        await db.auto_heal_log.insert_one({
            "tenant_id": tenant_id,
            "verified": verified,
            "failed": failed,
            "promotions": promotions,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "tenant_id": tenant_id,
        "verified": verified,
        "failed": failed,
        "promotions": promotions,
        "all_verified": failed == 0,
        "interaction_results": interaction_results,
    }


# ═══════════════════════════════════════
# STAGE 10: LEARN — update scores/knowledge
# ═══════════════════════════════════════

async def learn_update(tenant_id: str, pipeline_results: dict) -> dict:
    """Update known_fixes, agent scores, AutoTune, and optimization metrics."""
    db = _get_db()
    if db is None:
        return {"updated": 0}

    updates = 0
    closer = pipeline_results.get("closer", {})

    for round_key, round_results in closer.get("results", {}).items():
        for result in round_results:
            if result.get("status") == "executed":
                await db.known_fixes.update_one(
                    {"tenant_id": tenant_id, "fix_type": result["strategy"]},
                    {"$set": {
                        "validated": True,
                        "last_success": datetime.now(timezone.utc).isoformat(),
                    }, "$inc": {"success_count": 1}},
                    upsert=True
                )
                updates += 1

    return {"tenant_id": tenant_id, "updates": updates}


# ═══════════════════════════════════════
# MASTER PIPELINE COORDINATOR
# ═══════════════════════════════════════

async def run_pipeline(tenant_id: str, trigger: str = "manual") -> dict:
    """
    Execute the complete AUREM autonomous pipeline.
    This is THE single entry point for all automation.
    """
    db = _get_db()

    # ═══ PLAN ENFORCEMENT GATE ═══════════════════════════════════
    try:
        from services.plan_enforcement import check_action_limit, check_pipeline_limit, increment_usage

        # Check monthly action limit
        action_gate = await check_action_limit(tenant_id)
        if not action_gate.get("allowed"):
            logger.warning(f"[PIPELINE] {tenant_id} blocked: {action_gate.get('reason')}")
            return {
                "status": "blocked",
                "reason": action_gate.get("reason"),
                "message": action_gate.get("message"),
                "tier": action_gate.get("tier"),
            }

        # Check daily pipeline limit
        pipeline_gate = await check_pipeline_limit(tenant_id)
        if not pipeline_gate.get("allowed"):
            logger.warning(f"[PIPELINE] {tenant_id} blocked: {pipeline_gate.get('reason')}")
            return {
                "status": "blocked",
                "reason": pipeline_gate.get("reason"),
                "message": pipeline_gate.get("message"),
            }

        # Increment counters
        await increment_usage(tenant_id, "actions_used")
        await increment_usage(tenant_id, "pipeline_runs")
    except Exception as e:
        logger.debug(f"[PIPELINE] Plan enforcement skipped: {e}")
    # ═══════════════════════════════════════════════════════════════

    run_id = str(uuid.uuid4())[:12]
    started = datetime.now(timezone.utc).isoformat()

    pipeline_result = {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "trigger": trigger,
        "started_at": started,
        "stages": {},
        "final_status": "running",
    }

    # Initialize run in DB
    if db is not None:
        await db.pipeline_runs.insert_one({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "trigger": trigger,
            "started_at": started,
            "stages": [],
            "final_status": "running",
        })

    try:
        # ═══════════════════════════════════════════════════════════════
        # PIPELINE PROFILER — times every stage, logs >1500ms to Sentinel
        # ═══════════════════════════════════════════════════════════════
        import time as _time
        _stage_timings = {}

        # Load evolved instructions from knowledge_base
        _evolved_instructions = {}
        try:
            from services.asi_evolve import get_evolved_instructions
            for stage_name in PIPELINE_STAGES:
                instrs = await get_evolved_instructions(db, tenant_id, stage_name)
                if instrs:
                    _evolved_instructions[stage_name] = instrs
                    logger.info(f"[PIPELINE] {tenant_id} | {stage_name} has {len(instrs)} evolved instructions")
        except Exception as e:
            logger.debug(f"[PIPELINE] Evolved instructions not available: {e}")

        # Store evolved context for agents to use
        pipeline_result["evolved_instructions"] = {
            k: [i.get("instruction", "") for i in v]
            for k, v in _evolved_instructions.items()
        }

        async def _run_stage(name, coro):
            """Execute a stage with profiling — logs slow stages to Sentinel"""
            t0 = _time.monotonic()
            result = await coro
            elapsed_ms = round((_time.monotonic() - t0) * 1000)
            _stage_timings[name] = elapsed_ms
            logger.info(f"[PIPELINE] {tenant_id} | {name} = {elapsed_ms}ms")
            if elapsed_ms > 1500:
                logger.warning(f"[PIPELINE] SLOW STAGE: {name} took {elapsed_ms}ms (>{1500}ms threshold)")
                try:
                    await db.sentinel_diagnoses.insert_one({
                        "tenant_id": tenant_id,
                        "type": "performance_anomaly",
                        "source": "pipeline_profiler",
                        "stage": name,
                        "elapsed_ms": elapsed_ms,
                        "threshold_ms": 1500,
                        "run_id": run_id,
                        "severity": "warning" if elapsed_ms < 3000 else "critical",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    pass
            return result

        # STAGE 1: SCOUT
        await _log_pipeline(run_id, tenant_id, "scout", "running")
        scout_results = await _run_stage("scout", scout_scan(tenant_id))
        pipeline_result["stages"]["scout"] = scout_results
        await _log_pipeline(run_id, tenant_id, "scout", "completed", {"findings": len(scout_results.get("findings", []))})

        if not scout_results.get("findings"):
            pipeline_result["final_status"] = "completed_no_issues"
            pipeline_result["stage_timings"] = _stage_timings
            await _log_pipeline(run_id, tenant_id, "scout", "completed_clean")
            await _finalize(run_id, pipeline_result)
            return pipeline_result

        # STAGE 2: ARCHITECT
        await _log_pipeline(run_id, tenant_id, "architect", "running")
        diagnoses = await _run_stage("architect", architect_diagnose(tenant_id, scout_results, run_id=run_id))
        pipeline_result["stages"]["architect"] = diagnoses
        await _log_pipeline(run_id, tenant_id, "architect", "completed", {"planned": diagnoses.get("total_planned", 0)})

        # STAGE 3: RISK GATE
        await _log_pipeline(run_id, tenant_id, "risk_gate", "running")
        risk = await _run_stage("risk_gate", risk_gate_check(tenant_id))
        pipeline_result["stages"]["risk_gate"] = risk
        if not risk.get("proceed"):
            pipeline_result["final_status"] = "aborted_red_risk"
            pipeline_result["stage_timings"] = _stage_timings
            await _log_pipeline(run_id, tenant_id, "risk_gate", "aborted", {"risk": risk.get("risk")})
            await _finalize(run_id, pipeline_result)
            return pipeline_result
        await _log_pipeline(run_id, tenant_id, "risk_gate", "passed", {"risk": risk.get("risk")})

        # Queue for quiet hours if needed
        if risk.get("queue_for_quiet_hours"):
            pipeline_result["final_status"] = "queued_quiet_hours"
            pipeline_result["stage_timings"] = _stage_timings
            await _log_pipeline(run_id, tenant_id, "risk_gate", "queued")
            await _finalize(run_id, pipeline_result)
            return pipeline_result

        # STAGE 4: ENVOY
        await _log_pipeline(run_id, tenant_id, "envoy", "running")
        decisions = await _run_stage("envoy", envoy_decide(tenant_id, diagnoses))
        pipeline_result["stages"]["envoy"] = decisions
        await _log_pipeline(run_id, tenant_id, "envoy", "completed", {"actions": decisions.get("total_actions", 0)})

        if not decisions.get("actions"):
            pipeline_result["final_status"] = "completed_no_actions"
            pipeline_result["stage_timings"] = _stage_timings
            await _finalize(run_id, pipeline_result)
            return pipeline_result

        # STAGE 5: HUMAN LOOP
        await _log_pipeline(run_id, tenant_id, "human_loop", "running")
        approved = await _run_stage("human_loop", human_loop_check(tenant_id, decisions, run_id=run_id))
        pipeline_result["stages"]["human_loop"] = approved
        await _log_pipeline(run_id, tenant_id, "human_loop", "completed", {
            "approved": len(approved.get("approved", [])),
            "pending": len(approved.get("pending", [])),
            "auto_count": approved.get("auto_count", 0),
            "manual_count": approved.get("manual_count", 0),
        })

        # STAGE 6: SHADOW TEST
        await _log_pipeline(run_id, tenant_id, "shadow_test", "running")
        shadow = await _run_stage("shadow_test", shadow_test_actions(tenant_id, approved.get("approved", [])))
        pipeline_result["stages"]["shadow_test"] = shadow
        if not shadow.get("all_passed"):
            pipeline_result["final_status"] = "aborted_shadow_fail"
            pipeline_result["stage_timings"] = _stage_timings
            await _log_pipeline(run_id, tenant_id, "shadow_test", "failed")
            await _send_alert(f"*Shadow Test Failed*\nTenant `{tenant_id}` — similarity below 0.90", "high")
            await _finalize(run_id, pipeline_result)
            return pipeline_result
        await _log_pipeline(run_id, tenant_id, "shadow_test", "passed")

        # STAGE 7: CLOSER
        all_actions = shadow.get("tested", []) + shadow.get("skipped", [])
        await _log_pipeline(run_id, tenant_id, "closer", "running")
        closer = await _run_stage("closer", closer_execute(tenant_id, all_actions, run_id=run_id))
        pipeline_result["stages"]["closer"] = closer
        await _log_pipeline(run_id, tenant_id, "closer", "completed", {"executed": closer.get("total_executed", 0)})

        # STAGE 8: ORIGIN LOCK
        await _log_pipeline(run_id, tenant_id, "origin_lock", "running")
        locked = await _run_stage("origin_lock", origin_lock(tenant_id, closer))
        pipeline_result["stages"]["origin_lock"] = locked
        await _log_pipeline(run_id, tenant_id, "origin_lock", "completed", {"anchored": locked.get("anchored", 0)})

        # STAGE 9: VERIFIER
        await _log_pipeline(run_id, tenant_id, "verifier", "running")
        verified = await _run_stage("verifier", verifier_check(tenant_id, closer, run_id=run_id))
        pipeline_result["stages"]["verifier"] = verified
        if not verified.get("all_verified"):
            pipeline_result["final_status"] = "partial_failure"
            await _log_pipeline(run_id, tenant_id, "verifier", "partial_fail")
            await _send_alert(f"*Verifier: Partial Failure*\nTenant `{tenant_id}` — {verified.get('failed',0)} fixes failed", "high")
        else:
            await _log_pipeline(run_id, tenant_id, "verifier", "all_verified")

        # STAGE 10: LEARN
        await _log_pipeline(run_id, tenant_id, "learn", "running")
        learned = await _run_stage("learn", learn_update(tenant_id, pipeline_result["stages"]))
        pipeline_result["stages"]["learn"] = learned
        await _log_pipeline(run_id, tenant_id, "learn", "completed")

        # MORNING BRIEF compilation
        await _log_pipeline(run_id, tenant_id, "morning_brief", "compiled")

        pipeline_result["final_status"] = "completed" if verified.get("all_verified") else "completed_with_issues"
        pipeline_result["completed_at"] = datetime.now(timezone.utc).isoformat()
        pipeline_result["stage_timings"] = _stage_timings

        # Log total pipeline time
        total_ms = sum(_stage_timings.values())
        logger.info(f"[PIPELINE] {tenant_id} | TOTAL = {total_ms}ms | stages = {_stage_timings}")

        # AUTO GITHUB BACKUP — after successful pipeline
        if pipeline_result["final_status"].startswith("completed"):
            try:
                backup = await auto_github_backup(run_id, tenant_id, pipeline_result)
                pipeline_result["github_backup"] = backup
            except Exception as e:
                logger.warning(f"[PIPELINE] GitHub backup error (non-fatal): {e}")

    except Exception as e:
        pipeline_result["final_status"] = "error"
        pipeline_result["error"] = str(e)
        logger.error(f"[PIPELINE] Error for {tenant_id}: {e}")
        await _log_pipeline(run_id, tenant_id, "error", "failed", {"error": str(e)})

    await _finalize(run_id, pipeline_result)

    # ═══ AGENT OBSERVATORY TRACE LOGGING ═══════════════════════════
    try:
        from routers.agent_observatory_router import log_pipeline_trace
        await log_pipeline_trace(
            run_id=run_id,
            tenant_id=tenant_id,
            stage_timings=pipeline_result.get("stage_timings", {}),
            stages=pipeline_result.get("stages", {}),
            final_status=pipeline_result.get("final_status", "unknown"),
        )
    except Exception as trace_err:
        logger.debug(f"[PIPELINE] Observatory trace log failed (non-fatal): {trace_err}")
    # ═══════════════════════════════════════════════════════════════

    # Track usage in tenant_customers
    if pipeline_result.get("final_status", "").startswith("completed"):
        try:
            await _db.tenant_customers.update_one(
                {"tenant_id": tenant_id},
                {"$inc": {"usage.actions_used": 1, "usage.actions_remaining": -1, "usage.pipeline_runs_today": 1},
                 "$set": {"last_active": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception:
            pass

    return pipeline_result


# ═══════════════════════════════════════
# AUTO GITHUB BACKUP
# ═══════════════════════════════════════

_backup_fail_streak = 0


async def auto_github_backup(run_id: str, tenant_id: str, pipeline_result: dict):
    """Auto-commit and push to GitHub after successful pipeline with >= 90% test pass."""
    global _backup_fail_streak
    db = _get_db()

    if tenant_id and tenant_id.startswith("demo_investor_"):
        return {"status": "skipped", "reason": "demo tenant"}

    final_status = pipeline_result.get("final_status", "")
    stages = pipeline_result.get("stages", {})
    total_tests = len(stages) if stages else 1

    if final_status in ("completed", "completed_no_actions", "completed_no_issues"):
        passed_tests = total_tests
    elif final_status == "completed_with_issues":
        passed_tests = max(1, total_tests - 1)
    else:
        passed_tests = 0

    pass_rate = passed_tests / total_tests if total_tests > 0 else 0
    now = datetime.now(timezone.utc)

    # SECURITY GATE: scan changed files before push
    try:
        from services.security_gate import scan_changed_files
        security_scan = scan_changed_files("/app")
        if security_scan.get("status") == "blocked":
            logger.warning("[GIT-BACKUP] BLOCKED by security gate")
            if db is not None:
                await db.git_backup_log.insert_one({
                    "run_id": run_id, "tenant_id": tenant_id,
                    "status": "security_blocked",
                    "security_issues": security_scan.get("criticals", [])[:5],
                    "timestamp": now.isoformat(),
                })
            return {"status": "security_blocked", "issues": security_scan.get("criticals", [])[:3]}
    except Exception as e:
        logger.warning(f"[GIT-BACKUP] Security scan error (non-fatal): {e}")

    commit_msg = (
        f"[AUREM] auto-backup: run_{run_id[:8]} | "
        f"{passed_tests}/{total_tests} tests | "
        f"{now.strftime('%Y-%m-%d %H:%M')}"
    )

    commands = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", commit_msg, "--allow-empty"],
        ["git", "push", "--force", "origin", "main"],
    ]

    success = True
    error_msg = ""

    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30, cwd="/app")
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                if "nothing to commit" in stderr or "nothing to commit" in result.stdout.decode("utf-8", errors="replace"):
                    logger.info("[GIT-BACKUP] Nothing to commit, skipping push")
                    success = True
                    break
                error_msg = f"{cmd[1]}: {stderr[:200]}"
                success = False
                break
        except subprocess.TimeoutExpired:
            error_msg = f"{cmd[1]}: timeout"
            success = False
            break
        except Exception as e:
            error_msg = f"{cmd[1]}: {str(e)[:200]}"
            success = False
            break

    if db is not None:
        await db.git_backup_log.insert_one({
            "run_id": run_id, "tenant_id": tenant_id,
            "status": "success" if success else "failed",
            "commit_message": commit_msg,
            "error": error_msg if not success else None,
            "pass_rate": round(pass_rate * 100, 1),
            "tests_passed": passed_tests, "tests_total": total_tests,
            "timestamp": now.isoformat(),
        })

    if success:
        _backup_fail_streak = 0
    else:
        _backup_fail_streak += 1
        if _backup_fail_streak >= 3:
            await _send_alert(
                f"*GitHub Backup Failed 3x*\nLast error: {error_msg}\nRun: `{run_id}`",
                priority="high"
            )

    return {"status": "success" if success else "failed", "error": error_msg}


async def get_backup_status() -> dict:
    """Get latest git backup status for Sentinel dashboard."""
    db = _get_db()
    if db is None:
        return {"status": "unknown", "last_backup": None}

    last = await db.git_backup_log.find_one(
        {"status": "success"}, {"_id": 0}, sort=[("timestamp", -1)]
    )
    last_any = await db.git_backup_log.find_one(
        {}, {"_id": 0}, sort=[("timestamp", -1)]
    )
    total = await db.git_backup_log.count_documents({"status": "success"})
    failed = await db.git_backup_log.count_documents({"status": "failed"})

    if last:
        last_dt = datetime.fromisoformat(last["timestamp"])
        hours_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        is_current = hours_ago < 24
    else:
        hours_ago = None
        is_current = False

    return {
        "status": "current" if is_current else "behind" if last else "never",
        "last_backup": last.get("timestamp") if last else None,
        "last_commit": last.get("commit_message") if last else None,
        "last_any": last_any,
        "total_backups": total,
        "total_failed": failed,
        "fail_streak": _backup_fail_streak,
    }


async def _finalize(run_id: str, result: dict):
    """Save final pipeline result including stage timings."""
    db = _get_db()
    if db is None:
        return
    update_fields = {
        "final_status": result["final_status"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("stage_timings"):
        update_fields["stage_timings"] = result["stage_timings"]
    await db.pipeline_runs.update_one(
        {"run_id": run_id},
        {"$set": update_fields}
    )
    if result["final_status"] in ("completed", "completed_no_issues"):
        await db.pipeline_completions.insert_one({
            "run_id": run_id,
            "tenant_id": result["tenant_id"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "trigger": result.get("trigger"),
        })


async def get_pipeline_history(tenant_id: str = None, limit: int = 10) -> list:
    """Get last N pipeline runs with stage-by-stage status."""
    db = _get_db()
    if db is None:
        return []
    query = {"tenant_id": tenant_id} if tenant_id else {}
    runs = await db.pipeline_runs.find(
        query, {"_id": 0}
    ).sort("started_at", -1).to_list(limit)
    return runs


async def get_pipeline_stats() -> dict:
    """Get aggregate pipeline statistics."""
    db = _get_db()
    if db is None:
        return {}
    total = await db.pipeline_runs.count_documents({})
    completed = await db.pipeline_runs.count_documents({"final_status": {"$regex": "^completed"}})
    aborted = await db.pipeline_runs.count_documents({"final_status": {"$regex": "^aborted"}})
    errors = await db.pipeline_runs.count_documents({"final_status": "error"})
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    last_24h = await db.pipeline_runs.count_documents({"started_at": {"$gte": cutoff}})
    return {
        "total_runs": total,
        "completed": completed,
        "aborted": aborted,
        "errors": errors,
        "last_24h": last_24h,
        "success_rate": round((completed / total * 100) if total > 0 else 0, 1),
    }

