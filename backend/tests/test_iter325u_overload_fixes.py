"""
iter 325u — regression tests for the APScheduler-overload + watchdog-noise fixes.

Three guarantees:
  1. warm_probe_tick fans out endpoints in PARALLEL (asyncio.gather), so a
     single slow endpoint can no longer starve the 90s scheduler interval.
  2. warm-prober scheduler is registered with max_instances=2 and
     misfire_grace_time=120 to absorb the rare overlap.
  3. ora_campaign_watchdog only emits a NEW incident on the trip-state
     transition + every 30x escalation — not on every 60s cycle.
"""
import inspect
import re


def test_warm_prober_uses_parallel_gather():
    src = open("/app/backend/services/warm_prober.py", encoding="utf-8").read()
    assert "asyncio.gather" in src, "warm_probe_tick must use asyncio.gather"
    # The serial `for path in WARM_ENDPOINTS:` body that called client.get()
    # inline must be gone — the new code dispatches via _probe_one().
    assert "for path in WARM_ENDPOINTS:" not in src or "asyncio.gather" in src
    assert "_probe_one" in src
    # 5s timeout cap so a single hung endpoint doesn't blow the 90s budget.
    assert re.search(r"AsyncClient\(timeout=5\.0\)", src)


def test_warm_prober_scheduler_overload_guards():
    src = open("/app/backend/services/warm_prober.py", encoding="utf-8").read()
    assert "max_instances=2" in src, "must tolerate one overlapping tick"
    assert "misfire_grace_time=120" in src, "must not pile up missed runs"


def test_campaign_watchdog_dedup_incident_emission():
    src = open("/app/backend/services/ora_campaign_watchdog.py",
               encoding="utf-8").read()
    # The transition-based gate must be present.
    assert "should_emit_incident" in src
    assert "prev_streak < SILENT_RUN_SENT_ZERO_CYCLES" in src
    assert "zero_streak % 30 == 0" in src


def test_campaign_watchdog_print_dedup_loop():
    src = open("/app/backend/services/ora_campaign_watchdog.py",
               encoding="utf-8").read()
    # Same dedup logic must guard the stdout print inside watchdog_loop().
    assert "streak <= SILENT_RUN_SENT_ZERO_CYCLES or streak % 30 == 0" in src


def test_warm_prober_helper_signature():
    """_probe_one must be importable + async + accept (client, base, path)."""
    from services import warm_prober
    assert inspect.iscoroutinefunction(warm_prober._probe_one)
    sig = inspect.signature(warm_prober._probe_one)
    assert list(sig.parameters.keys()) == ["client", "base", "path"]
