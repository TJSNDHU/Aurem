"""
Pillar 3 — Site Monitoring / Sentinel / Self-Heal / Shannon

This package logically groups all site-monitoring-related code. The goal is
to gradually extract it into an independently deployable service.

What lives here:
  - pillars/site_monitor/worker.py  — dedicated scheduler coordinator
    that owns site_monitor_scheduler, shannon_runner_scheduler, and
    self_repair_loop. Removes their burden from the main uvicorn event loop.

What will eventually live here (tracked in /app/memory/AUREM_MODULARIZATION_AUDIT_2026-04-22.md):
  - routers/site_monitor_router.py
  - routers/shannon_router.py
  - routers/sentinel_client_router.py
  - routers/seo_audit_router.py
  - routers/self_repair_router.py
  - routers/ai_repair_router.py
  - routers/customer_website_repair_router.py
  - routers/approval_router.py
  - services/site_monitor.py
  - services/shannon_runner.py
  - services/shannon_security.py
  - services/self_repair_loop.py
  - services/auto_repair.py
  - services/self_healing_ai.py
  - services/sentinel_anomaly.py
  - services/patch_deployer.py
  - services/smart_approval.py
"""
