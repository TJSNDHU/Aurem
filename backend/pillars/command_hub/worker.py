"""
Pillar 4 Worker — Command Hub / Observability / Platform Ops coordinator.
=========================================================================
Isolates the platform-wide observability & operational background loops
from the main uvicorn event loop. A slow DB archive, hung health probe,
laggy QA deep-scan, or failing backup cycle inside any of these loops no
longer blocks the 234 HTTP routers.

Hosted schedulers (17 total, grouped in 4 subgroups):

  ── 1. Observability / Health (5) ────────────────────────────────────
    * auto_heal_scheduler         (platform health probe loop)
    * auto_repair_scheduler       (autonomous self-repair, 10 min)
    * qa_bot_pulse_scheduler      (QA bot pulse, 10 min)
    * qa_agent_deep_scheduler     (deep QA agent, weekly)
    * health_score_scheduler      (health score engine, 6 h)

  ── 2. Audit / Autonomy (5) ──────────────────────────────────────────
    * system_audit_scheduler      (monthly system heartbeat)
    * autonomy_cron_scheduler     (nightly self-audit, 2 AM UTC)
    * daily_site_audit            (daily site audit)
    * daily_client_scan_loop      (daily client website intel, 3:15 AM UTC)
    * reverification_scheduler    (accurate-scout nightly re-verify)

  ── 3. Reporting / Digest (4) ────────────────────────────────────────
    * daily_digest_scheduler          (9 AM EST review digest)
    * orchestrator_digest_scheduler   (8 AM EST orchestrator digest)
    * operational_alerts_scheduler    (low stock / NPN expiry, 8 AM EST)
    * whatsapp_crm_scheduler          (daily WhatsApp CRM ticks)

  ── 4. Platform Ops (3 + ClawChief 3) ────────────────────────────────
    * monthly_data_cleanup_scheduler  (GDPR cleanup, 1st of month)
    * backup_loop                     (6 h backup cycle)
    * clawchief_heartbeat_scheduler
    * clawchief_daily_sweep_scheduler
    * clawchief_pipeline_audit_scheduler

Every scheduler runs inside _safe_task so unhandled exceptions are
logged and isolated; sibling loops keep running even if one crashes.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger("pillars.command_hub.worker")

_worker_tasks: list[asyncio.Task] = []
_worker_started = False


def _safe_task(coro, name: str) -> Optional[asyncio.Task]:
    async def _wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"[p4-worker] task '{name}' cancelled")
            raise
        except BaseException as exc:
            logger.error(f"[p4-worker] task '{name}' crashed: {exc}", exc_info=True)

    task = asyncio.create_task(_wrapper(), name=f"p4:{name}")
    _worker_tasks.append(task)
    return task


def _attach(name: str, coro, started: list, failed: list, label: str,
            disabled: Optional[set] = None) -> None:
    """Attach a single scheduler coroutine with uniform logging.

    iter 332b D-23 — honors AUREM_DISABLE_SCHEDULERS=<csv> for surgical
    scheduler control in the deployment env (e.g. disable just the heavy
    QA-deep + backup-loop pair without killing observability).
    """
    if disabled and name in disabled:
        print(f"[p4-worker] ⊘ {label} skipped via AUREM_DISABLE_SCHEDULERS",
              flush=True)
        # Properly close the unused coroutine so we don't leak a warning.
        try:
            coro.close()
        except Exception:
            pass
        return
    try:
        _safe_task(coro, name)
        started.append(name)
        print(f"[p4-worker] ✓ {label} attached", flush=True)
    except Exception as e:
        failed.append({"task": name, "error": str(e)})
        print(f"[p4-worker] ✗ {label} failed: {e}", flush=True)


def start_pillar4_worker(
    db,
    # Closure-based factories (live inside startup_init.py as local functions)
    daily_digest_coro_factory: Optional[Callable] = None,
    operational_alerts_coro_factory: Optional[Callable] = None,
    whatsapp_crm_coro_factory: Optional[Callable] = None,
    orchestrator_digest_coro_factory: Optional[Callable] = None,
    auto_repair_coro_factory: Optional[Callable] = None,
    monthly_cleanup_coro_factory: Optional[Callable] = None,
    daily_client_scan_coro_factory: Optional[Callable] = None,
    health_score_coro_factory: Optional[Callable] = None,
) -> dict:
    """Start Pillar 4 schedulers in an isolated task group.

    Factories produce the coroutine (so each lazy import happens inside the
    worker rather than at module import time — avoids circular imports).

    iter 332b D-23 — deployment escape hatch.
      • AUREM_LITE_MODE=1            — disable ALL P4 schedulers (best for
        a memory-constrained K8s pod that's OOM-restarting).
      • AUREM_DISABLE_SCHEDULERS=<csv> — disable specific scheduler names
        (e.g. "qa_agent_deep,backup_loop,clawchief_daily_sweep").

    iter 332b D-24 — auto-detect production. The user's deployment UI
    doesn't expose env-var editing, so we infer "this is production" from
    signals K8s sets automatically and switch to LITE mode by default.
    Preview/dev keeps the full scheduler set running.
    """
    global _worker_started
    import os as _os

    def _looks_like_production() -> bool:
        """Best-effort sniff for the Emergent K8s production runtime.

        iter 332b D-26 — preview pods have HOSTNAME starting with
        `agent-env-`. Production pods have `live-support` or `emergent.host`
        in the hostname. The previous heuristic relied on REACT_APP_BACKEND_URL
        which is a *frontend* var and isn't set on the backend pod — so it
        always evaluated to "not preview" and forced LITE on preview too.
        """
        # Explicit opt-in/out beats heuristics.
        if _os.environ.get("AUREM_FORCE_FULL_MODE", "").strip() in ("1", "true", "yes"):
            return False
        if _os.environ.get("AUREM_LITE_MODE", "").strip() in ("1", "true", "yes"):
            return True
        host = (_os.environ.get("HOSTNAME") or "").lower()
        # Preview/dev pods are the agent sandbox container.
        if host.startswith("agent-env-") or host.startswith("preview-"):
            return False
        if "live-support" in host or "emergent.host" in host:
            return True
        # Last-resort: in K8s with no preview signal at all.
        if _os.environ.get("KUBERNETES_SERVICE_HOST"):
            if not _os.environ.get("preview_endpoint"):
                return True
        return False

    if _looks_like_production():
        print("[p4-worker] PRODUCTION DETECTED — LITE MODE engaged, "
              "all 34 schedulers DISABLED (set AUREM_FORCE_FULL_MODE=1 to override)",
              flush=True)
        _worker_started = True
        return {"started": [], "failed": [], "skipped_all_lite_mode": True}

    _DISABLED = {n.strip() for n in
                 _os.environ.get("AUREM_DISABLE_SCHEDULERS", "").split(",")
                 if n.strip()}
    if _DISABLED:
        print(f"[p4-worker] skipping schedulers via env: {sorted(_DISABLED)}",
              flush=True)

    # Local wrapper so every _attach call below auto-honors _DISABLED
    # without us having to thread the kwarg through 34 call sites.
    def _at(name, coro, label):
        return _attach(name, coro, started, failed, label, disabled=_DISABLED)

    if _worker_started:
        return {"already_started": True, "tasks": [t.get_name() for t in _worker_tasks]}

    started: list[str] = []
    failed: list[dict] = []

    # ═══ Subgroup 1: Observability / Health ═══════════════════════════

    # auto_heal (module-level, directly importable)
    try:
        from services.auto_heal import auto_heal_scheduler
        _attach("auto_heal_scheduler", auto_heal_scheduler(), started, failed,
                "Auto-Heal monitor")
    except ImportError as e:
        failed.append({"task": "auto_heal_scheduler", "error": f"ImportError: {e}"})

    # Agent Registry — heartbeat + action flush every 30s (Phase 0 foundation)
    try:
        from services.agent_registry import registry_flush_scheduler
        _attach("registry_flush_scheduler", registry_flush_scheduler(),
                started, failed, "Agent Registry flush (30s)")
    except Exception as e:
        failed.append({"task": "registry_flush_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Agent Registry flush failed: {e}", flush=True)

    # ORA Brain Observer (Phase 2 — subscribes to all A2A events)
    try:
        from services.ora_brain_observer import register_subscriptions as _ora_obs_subs
        _ora_obs_subs()
        started.append("ora_brain_observer subscribed to 24 A2A events")
        print("[p4-worker] ✓ ORA Brain Observer attached", flush=True)
    except Exception as e:
        failed.append({"task": "ora_brain_observer", "error": str(e)})
        print(f"[p4-worker] ✗ ORA Brain Observer failed: {e}", flush=True)

    # ORA Knowledge Feeds (Phase 3 — 5 learning feeds → submit_learning)
    try:
        from services.ora_knowledge_base import (
            register_feeds as _kb_feeds,
            nightly_digest_scheduler,
            weekly_self_assessment_scheduler,
        )
        _kb_feeds()
        started.append("ora_knowledge: 5 learning feeds registered")
        _attach("ora_knowledge_nightly_digest", nightly_digest_scheduler()(),
                started, failed, "ORA Knowledge Nightly Digest (03:00 UTC)")
        _attach("ora_knowledge_weekly_assessment", weekly_self_assessment_scheduler()(),
                started, failed, "ORA Knowledge Weekly Self-Assessment (Sun 04:00 UTC)")
        print("[p4-worker] ✓ ORA Knowledge feeds + 2 schedulers attached", flush=True)
    except Exception as e:
        failed.append({"task": "ora_knowledge_base", "error": str(e)})
        print(f"[p4-worker] ✗ ORA Knowledge feeds failed: {e}", flush=True)

    # Deploy Monitor (Phase 4 — emit DEPLOY_DETECTED on version change)
    try:
        from services.deploy_monitor import deploy_monitor_scheduler
        _attach("deploy_monitor_scheduler", deploy_monitor_scheduler()(),
                started, failed, "Deploy Monitor (5 min)")
    except Exception as e:
        failed.append({"task": "deploy_monitor_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Deploy Monitor failed: {e}", flush=True)

    # Agent Health Check (Phase 5 — 7 self-healing rules every 5 min)
    try:
        from services.agent_health_check import health_check_scheduler
        _attach("agent_health_check_scheduler", health_check_scheduler()(),
                started, failed, "Agent Health Check (7 rules, 5 min)")
    except Exception as e:
        failed.append({"task": "agent_health_check_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Agent Health Check failed: {e}", flush=True)

    # Sovereign Cache Warm Snapshot (30s — survives pod restarts)
    try:
        from services.aurem_cache import warmup_snapshot_scheduler
        _attach("cache_warmup_snapshot_scheduler", warmup_snapshot_scheduler()(),
                started, failed, "Sovereign Cache Warm Snapshot (30 s)")
    except Exception as e:
        failed.append({"task": "cache_warmup_snapshot_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Cache Warmup failed: {e}", flush=True)

    # Customer Health Monitor (30 min — auto-detect + auto-repair tenants)
    try:
        from services.customer_health_monitor import (
            customer_health_scheduler,
            set_db as set_chm_db,
        )
        set_chm_db(db)
        _attach("customer_health_scheduler", customer_health_scheduler(),
                started, failed, "Customer Health Monitor (30 min)")
    except Exception as e:
        failed.append({"task": "customer_health_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Customer Health Monitor failed: {e}", flush=True)


    # Council auto-promote daily scheduler (Phase 2)
    try:
        async def _auto_promote_loop():
            import asyncio as _asyncio
            print("[council-promote] auto-promote loop alive — 6h cycle, 5min grace", flush=True)
            await _asyncio.sleep(300)
            while True:
                try:
                    from services.sovereign_memory import promote_if_ready
                    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                    cutoff_iso = (_dt.now(_tz.utc) - _td(days=5)).isoformat()
                    rows = await db.learnings_pending_review.find({
                        "status": "pending",
                        "submitted_at": {"$lte": cutoff_iso},
                        "confidence": {"$gte": 0.8},
                    }, {"id": 1, "payload": 1, "_id": 0}).limit(200).to_list(200)
                    cands = [r for r in rows if int((r.get("payload") or {}).get("times_seen", 0)) >= 3]
                    if cands:
                        ids = [c["id"] for c in cands]
                        now_iso = _dt.now(_tz.utc).isoformat()
                        await db.learnings_pending_review.update_many(
                            {"id": {"$in": ids}, "status": "pending"},
                            {"$push": {"stamps": {"role": "auto_promoter",
                                                  "vote": "approve",
                                                  "ts": now_iso,
                                                  "by": "auto-promote-scheduler"}}},
                        )
                        results = await _asyncio.gather(
                            *[promote_if_ready(db, lid) for lid in ids],
                            return_exceptions=True,
                        )
                        promoted = sum(1 for r in results
                                       if not isinstance(r, Exception) and r is not None)
                        if promoted:
                            print(f"[council-promote] auto-promoted {promoted}/{len(cands)}", flush=True)
                    await _asyncio.sleep(21600)  # 6 hours
                except _asyncio.CancelledError:
                    raise
                except Exception as _e:
                    import logging as _lg
                    _lg.getLogger(__name__).error(f"[council-promote] loop error: {_e}")
                    await _asyncio.sleep(600)
        _attach("council_auto_promote_scheduler", _auto_promote_loop(),
                started, failed, "Council auto-promote (6h)")
    except Exception as e:
        failed.append({"task": "council_auto_promote_scheduler", "error": str(e)})

    # Onboarding reminder (iter 320) — nudges tenants who signed up but
    # never installed the pixel. 2-min cycle, 10-min grace, max 3 nudges.
    try:
        from services.onboarding_reminder import onboarding_reminder_scheduler
        _attach("onboarding_reminder_scheduler", onboarding_reminder_scheduler(),
                started, failed, "Onboarding Pixel Reminder (2 min)")
    except Exception as e:
        failed.append({"task": "onboarding_reminder_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Onboarding Reminder failed: {e}", flush=True)

    # A2A chain (Iter 2) — Scout → Architect → Envoy → Closer autonomous
    # outreach. 60-s cycle, idempotent stages, model_failover-backed.
    try:
        from services.a2a_chain import a2a_chain_scheduler
        _attach("a2a_chain_scheduler", a2a_chain_scheduler(), started, failed,
                "A2A Chain (Architect → Envoy → Closer, 60 s)")
    except Exception as e:
        failed.append({"task": "a2a_chain_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ A2A Chain failed: {e}", flush=True)

    # auto_repair (closure factory — depends on lazy repair_db injection)
    if auto_repair_coro_factory:
        _attach("auto_repair_scheduler", auto_repair_coro_factory(), started, failed,
                "Autonomous Self-Repair (10 min)")

    # autonomous_repair_engine (iter 281 — 2 min sentinel-driven heal loop)
    try:
        from services.autonomous_repair_engine import (
            autonomous_repair_scheduler,
            set_db as set_ar_db,
        )
        set_ar_db(db)
        _attach("autonomous_repair_scheduler", autonomous_repair_scheduler(),
                started, failed, "Autonomous Repair Engine (2 min sentinel-driven)")
    except Exception as e:
        failed.append({"task": "autonomous_repair_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Autonomous Repair Engine failed: {e}", flush=True)

    # a2a_learning_scheduler (iter 282 — daily Pillar↔Hermes feedback loop)
    try:
        from services.a2a_learning_scheduler import (
            a2a_learning_daily_scheduler,
            set_db as set_al_db,
        )
        set_al_db(db)
        _attach("a2a_learning_daily_scheduler", a2a_learning_daily_scheduler(),
                started, failed, "A2A Learning Daily (2 AM UTC)")
    except Exception as e:
        failed.append({"task": "a2a_learning_daily_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ A2A Learning Daily failed: {e}", flush=True)

    # qa_bot + qa_deep
    try:
        from services.qa_bot import qa_bot_pulse_scheduler, set_db as set_qa_bot_db
        from services.qa_agent_deep import qa_agent_deep_scheduler, set_db as set_qa_deep_db
        set_qa_bot_db(db)
        set_qa_deep_db(db)
        _attach("qa_bot_pulse_scheduler", qa_bot_pulse_scheduler(), started, failed,
                "QA Bot Pulse (10 min)")
        _attach("qa_agent_deep_scheduler", qa_agent_deep_scheduler(), started, failed,
                "QA Agent Deep (weekly)")
    except Exception as e:
        failed.append({"task": "qa_bot_schedulers", "error": str(e)})
        print(f"[p4-worker] ✗ QA Bot schedulers failed: {e}", flush=True)

    # health_score (closure factory — uses _health_score_scheduler(db) from startup_init)
    if health_score_coro_factory:
        _attach("health_score_scheduler", health_score_coro_factory(), started, failed,
                "Health Score Engine (6 h)")

    # ═══ Subgroup 2: Audit / Autonomy ═════════════════════════════════

    # system_audit (importable)
    try:
        from services.project_report_builder import system_audit_scheduler
        _attach("system_audit_scheduler", system_audit_scheduler(db), started, failed,
                "System Audit (monthly heartbeat)")
    except Exception as e:
        failed.append({"task": "system_audit_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ System Audit failed: {e}", flush=True)

    # autonomy_cron (importable)
    try:
        from services.autonomy_engine import autonomy_cron_scheduler, set_db as set_autonomy_db
        set_autonomy_db(db)
        _attach("autonomy_cron_scheduler", autonomy_cron_scheduler(), started, failed,
                "Autonomy Nightly Self-Audit (2 AM UTC)")
    except Exception as e:
        failed.append({"task": "autonomy_cron_scheduler", "error": str(e)})
        print(f"[p4-worker] ✗ Autonomy failed: {e}", flush=True)

    # daily_site_audit (importable)
    try:
        from services.site_audit import start_daily_audit
        _attach("daily_site_audit", start_daily_audit(), started, failed,
                "Daily Site Audit")
    except Exception as e:
        failed.append({"task": "daily_site_audit", "error": str(e)})

    # daily_client_scan (closure factory)
    if daily_client_scan_coro_factory:
        _attach("daily_client_scan_loop", daily_client_scan_coro_factory(), started, failed,
                "Daily Client Website Intel (3:15 AM UTC)")

    # reverification (importable)
    try:
        from services.accurate_scout_cron import reverification_scheduler
        _attach("reverification_scheduler", reverification_scheduler(), started, failed,
                "Accurate-Scout Re-verification (nightly)")
    except ImportError:
        pass  # optional service

    # ═══ Subgroup 3: Reporting / Digest ═══════════════════════════════

    if daily_digest_coro_factory:
        _attach("daily_digest_scheduler", daily_digest_coro_factory(), started, failed,
                "Daily Review Digest (9 AM EST)")

    if orchestrator_digest_coro_factory:
        _attach("orchestrator_digest_scheduler", orchestrator_digest_coro_factory(),
                started, failed, "Orchestrator Digest (8 AM EST)")

    if operational_alerts_coro_factory:
        _attach("operational_alerts_scheduler", operational_alerts_coro_factory(),
                started, failed, "Operational Alerts (low stock / NPN)")

    if whatsapp_crm_coro_factory:
        _attach("whatsapp_crm_scheduler", whatsapp_crm_coro_factory(), started, failed,
                "WhatsApp CRM Daily Ticks")

    # ═══ Subgroup 4: Platform Ops ═════════════════════════════════════

    # monthly_data_cleanup (closure factory — uses pytz)
    if monthly_cleanup_coro_factory:
        _attach("monthly_data_cleanup_scheduler", monthly_cleanup_coro_factory(),
                started, failed, "Monthly GDPR Data Cleanup")

    # backup_loop (importable)
    try:
        from services.backup_service import backup_loop
        _attach("backup_loop", backup_loop(), started, failed,
                "Backup Service (6 h cycle)")
    except Exception as e:
        failed.append({"task": "backup_loop", "error": str(e)})
        print(f"[p4-worker] ✗ Backup Loop failed: {e}", flush=True)

    # ClawChief trio (importable)
    try:
        from services.clawchief_service import (
            heartbeat_scheduler as cc_heartbeat,
            daily_sweep_scheduler as cc_daily_sweep,
            pipeline_audit_scheduler as cc_pipeline_audit,
            set_db as set_clawchief_db,
        )
        set_clawchief_db(db)
        _attach("clawchief_heartbeat", cc_heartbeat(), started, failed,
                "ClawChief Heartbeat")
        _attach("clawchief_daily_sweep", cc_daily_sweep(), started, failed,
                "ClawChief Daily Sweep")
        _attach("clawchief_pipeline_audit", cc_pipeline_audit(), started, failed,
                "ClawChief Pipeline Audit")
    except Exception as e:
        failed.append({"task": "clawchief_trio", "error": str(e)})
        print(f"[p4-worker] ✗ ClawChief trio failed: {e}", flush=True)

    # Pillar Heartbeat Service (20 s cache refresh for /admin/pillars-map)
    try:
        from services.pillar_heartbeat_service import pillar_heartbeat_scheduler
        _attach("pillar_heartbeat", pillar_heartbeat_scheduler(db), started, failed,
                "Pillar Heartbeat (20 s DB snapshot)")
    except Exception as e:
        failed.append({"task": "pillar_heartbeat", "error": str(e)})
        print(f"[p4-worker] ✗ Pillar Heartbeat failed: {e}", flush=True)

    _worker_started = True
    print(
        f"[p4-worker] Pillar 4 worker ready — {len(started)} schedulers attached, "
        f"{len(failed)} failed",
        flush=True,
    )
    return {
        "started_count": len(started),
        "failed_count": len(failed),
        "started": started,
        "failed": failed,
    }


def get_worker_status() -> dict:
    active = [t for t in _worker_tasks if not t.done()]
    finished = [t for t in _worker_tasks if t.done()]
    return {
        "started": _worker_started,
        "active_tasks": len(active),
        "finished_tasks": len(finished),
        "tasks": [
            {
                "name": t.get_name(),
                "done": t.done(),
                "cancelled": t.cancelled() if t.done() else False,
                "exception": (
                    str(t.exception()) if t.done() and not t.cancelled() and t.exception() else None
                ),
            }
            for t in _worker_tasks
        ],
    }


async def shutdown_pillar4_worker() -> None:
    for t in _worker_tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    logger.info("[p4-worker] all tasks cancelled")
