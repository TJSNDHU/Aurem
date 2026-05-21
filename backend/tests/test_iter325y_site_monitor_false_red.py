"""
iter 325y — Site-monitor false-RED cascade fix.

User reported (2026-05-21 screenshot): /admin/pillars-map drill-down for
`site_monitor_logs` showed:
  • DB Side red "no writes within 20 min (silent failure)"  (image OCR)
  • Backend Side red "0/1 writers live"  (actual root)

Root-cause analysis (verified live):
  1. The p3 orchestrator has a deliberate 25-second cold-boot delay
     (`SCHED_BOOT_DELAY_S`) before launching pillar workers. During this
     window NO `p[1-4]:*` scheduler task exists in `asyncio.all_tasks()`,
     so the watchdog flagged every collection-with-writer as RED.
  2. Additionally, when there are zero active customer endpoints, the
     site-monitor scheduler runs every 5 min but writes nothing → false
     "silent failure" red after the 20-min freshness threshold.

Route-level fixes (no UI patches):
  • `_backend_pulse` reports YELLOW with a "booting · orchestrator grace"
    reason during the ~85s startup window. RED only fires once grace has
    elapsed AND the writer task is still absent (i.e. genuinely dead).
  • `site_monitor.run_scan_tick` writes a `kind:scheduler_heartbeat` row
    when there are no endpoints to probe so freshness checks see writes
    even on idle systems. `case_study_builder` + pass-rate aggregations
    filter that kind out so reports remain accurate.
"""
import os
import sys
import importlib

sys.path.insert(0, "/app/backend")


def test_boot_grace_returns_yellow_not_red_when_writers_absent(monkeypatch):
    """During the orchestrator boot grace, missing writers → YELLOW (not RED).

    Reset the cached process-start time + grace window then call
    `_backend_pulse` with an empty live-names set.
    """
    from routers import pillars_map_router as pmap
    from datetime import datetime, timezone
    pmap._PROCESS_STARTED_AT = datetime.now(timezone.utc)
    pmap._ORCH_GRACE_SECONDS = 85.0
    status, reason = pmap._backend_pulse(
        "site_monitor_logs", pillar_live_count=0, live_names=set()
    )
    assert status == "yellow"
    assert "boot" in reason.lower() or "grace" in reason.lower()


def test_red_returns_after_grace_elapsed(monkeypatch):
    """Once grace has elapsed, missing writers → RED (genuine outage)."""
    from routers import pillars_map_router as pmap
    from datetime import datetime, timezone, timedelta
    # Fake a process that started 1 hour ago — grace long elapsed.
    pmap._PROCESS_STARTED_AT = datetime.now(timezone.utc) - timedelta(hours=1)
    pmap._ORCH_GRACE_SECONDS = 85.0
    status, reason = pmap._backend_pulse(
        "site_monitor_logs", pillar_live_count=0, live_names=set()
    )
    assert status == "red"
    assert "0/" in reason


def test_green_when_writer_alive(monkeypatch):
    """If the writer is in live_names, status is GREEN regardless of grace."""
    from routers import pillars_map_router as pmap
    status, reason = pmap._backend_pulse(
        "site_monitor_logs",
        pillar_live_count=3,
        live_names={"p3:site_monitor_scheduler"},
    )
    assert status == "green"
    assert "1/1" in reason


def test_site_monitor_writes_heartbeat_when_no_endpoints():
    """site_monitor.run_scan_tick must insert a scheduler_heartbeat row
    when there are zero active endpoints, so the freshness watchdog has
    a recent write to look at."""
    src = open("/app/backend/services/site_monitor.py", encoding="utf-8").read()
    assert "scheduler_heartbeat" in src
    assert "tick ran, no active endpoints" in src
    # Must also filter heartbeats out of recent-pass-rate aggregation
    assert '"kind": {"$ne": "scheduler_heartbeat"}' in src
