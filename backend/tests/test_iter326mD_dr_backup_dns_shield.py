"""
test_iter326mD_dr_backup_dns_shield.py — Production deploy bug fix.
══════════════════════════════════════════════════════════════════════════════
User reported PRODUCTION deploy logs spamming:
  pymongo.errors.AutoReconnect: customer-apps-shard-00-XX.djq3ym.mongodb.net
    :27017: [Errno -3] Temporary failure in name resolution
  APScheduler: maximum number of running instances reached
  APScheduler: Run time of job ... was missed by 2-4 minutes

ROOT CAUSE
──────────
`SECONDARY_MONGO_URL` (read in `services/db_backup_service.py` and
`routers/admin_dr_backup_router.py`) pointed to a stale Atlas cluster.
Both modules constructed a sync `MongoClient(stale_url, ...)` which spawns
a topology MONITOR THREAD inside pymongo. That thread retries DNS forever,
even after the surrounding code calls `client.close()` — close() only
sets a flag; the thread has to finish its in-flight DNS attempt (5–30s
each) before observing it. Daily DR cron + every T3 escalation in
`pillar_escalation.py` re-spawned new zombies → APScheduler's worker
pool saturated → scheduler missed jobs by minutes.

FIX
───
Module-level **DNS pre-flight** (`socket.getaddrinfo` with 3s budget) +
**30-minute circuit breaker** in `services/db_backup_service.py`:

  • `_preflight_dns(url)`     — resolve every host BEFORE MongoClient.
  • `_secondary_circuit_open` — true while cooldown active.
  • `_trip_secondary_circuit` — opens breaker on any DNS failure.

Both `db_backup_service.run_backup` and the dashboard probe in
`admin_dr_backup_router` now gate every `MongoClient(secondary_url)` on
this guard. When the URL is dead, NO MongoClient is constructed at all —
zero zombie threads.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326mD_dr_backup_dns_shield.py -v
"""
from __future__ import annotations

import time

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# DNS pre-flight helper
# ─────────────────────────────────────────────────────────────────────────────
def test_preflight_dns_resolves_real_host():
    """A reachable mongo MUST pass both stages of the pre-flight (DNS
    resolves AND TCP port 27017 accepts). Local mongod (which the test
    suite already uses) is the simplest reachable target."""
    from services.db_backup_service import _preflight_dns

    ok, reason = _preflight_dns("mongodb://localhost:27017/aurem_db")
    assert ok is True, f"expected ok, got reason={reason!r}"


def test_preflight_dns_rejects_dead_atlas_hostname():
    """The exact hostname from the production failure logs MUST be
    rejected fast — no MongoClient construction allowed. Atlas keeps
    DNS records alive even after the cluster is decommissioned, so
    the rejection must come from the TCP-connect stage, not just DNS."""
    from services.db_backup_service import _preflight_dns

    dead_url = (
        "mongodb://user:pass@customer-apps-shard-00-00.djq3ym.mongodb.net:27017,"
        "customer-apps-shard-00-01.djq3ym.mongodb.net:27017,"
        "customer-apps-shard-00-02.djq3ym.mongodb.net:27017/aurem_db"
        "?ssl=true&replicaSet=atlas-djq3ym-shard-0&authSource=admin"
    )
    ok, reason = _preflight_dns(dead_url)
    assert ok is False
    # Either DNS missed, OR TCP connect failed (likelier — Atlas
    # decommissioned cluster keeps DNS but rejects connections).
    assert ("djq3ym" in reason
            or "TCP connect" in reason
            or "DNS fail" in reason
            or "TCP probe" in reason), f"unexpected reason: {reason}"


def test_preflight_dns_extracts_replica_set_hosts_correctly():
    """The extractor must split comma-separated hosts and strip
    ports/credentials. Otherwise a single dead host in a 3-host RS would
    silently slip past the pre-flight."""
    from services.db_backup_service import _hosts_from_mongo_url

    url = (
        "mongodb://user:pass@h1.example.com:27017,"
        "h2.example.com:27017,h3.example.com:27018/db?ssl=true"
    )
    hosts = _hosts_from_mongo_url(url)
    assert hosts == ["h1.example.com", "h2.example.com", "h3.example.com"]


def test_preflight_dns_handles_srv_url_form():
    """SRV form (`mongodb+srv://`) must also be parsed — this is the
    most common Atlas URL shape today."""
    from services.db_backup_service import _hosts_from_mongo_url

    url = "mongodb+srv://user:pass@cluster.atlas.mongodb.net/db?retryWrites=true"
    hosts = _hosts_from_mongo_url(url)
    assert hosts == ["cluster.atlas.mongodb.net"]


# ─────────────────────────────────────────────────────────────────────────────
# Circuit breaker
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def fresh_circuit():
    """Reset breaker state before AND after each test so test ordering
    can't leak state."""
    import services.db_backup_service as svc

    svc._SECONDARY_DNS_FAIL_UNTIL = 0.0
    svc._SECONDARY_DNS_FAIL_REASON = ""
    yield svc
    svc._SECONDARY_DNS_FAIL_UNTIL = 0.0
    svc._SECONDARY_DNS_FAIL_REASON = ""


def test_circuit_starts_closed(fresh_circuit):
    open_, reason = fresh_circuit._secondary_circuit_open()
    assert open_ is False
    assert reason == ""


def test_circuit_trips_for_full_cooldown(fresh_circuit):
    fresh_circuit._trip_secondary_circuit("simulated DNS fail")
    open_, reason = fresh_circuit._secondary_circuit_open()
    assert open_ is True
    assert "simulated DNS fail" in reason
    # cooldown is 30 min — verify the deadline is set roughly correctly
    assert (
        fresh_circuit._SECONDARY_DNS_FAIL_UNTIL - time.time()
        > fresh_circuit.SECONDARY_DNS_COOLDOWN_S - 5
    )


def test_circuit_re_closes_after_cooldown(fresh_circuit):
    """Past the deadline, the breaker self-closes. Otherwise an early-
    boot transient DNS hiccup would permanently disable DR."""
    fresh_circuit._trip_secondary_circuit("simulated")
    fresh_circuit._SECONDARY_DNS_FAIL_UNTIL = time.time() - 1
    open_, _ = fresh_circuit._secondary_circuit_open()
    assert open_ is False


# ─────────────────────────────────────────────────────────────────────────────
# run_backup integration — must short-circuit BEFORE constructing MongoClient
# ─────────────────────────────────────────────────────────────────────────────
def test_run_backup_skips_when_circuit_open(monkeypatch, fresh_circuit):
    """When the breaker is already tripped, `run_backup` must return a
    `status=skipped` report WITHOUT calling MongoClient at all (otherwise
    we re-spawn the zombie topology thread we were avoiding)."""
    from pymongo import MongoClient as _RealMongoClient
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("SECONDARY_MONGO_URL",
                       "mongodb://customer-apps-shard-00-00.djq3ym.mongodb.net:27017")

    fresh_circuit._trip_secondary_circuit("preset for test")

    # Sentinel: if run_backup constructs a MongoClient anyway, the test fails.
    constructed: list = []

    def _spy(*a, **kw):
        constructed.append((a, kw))
        return _RealMongoClient(*a, **kw)

    monkeypatch.setattr("services.db_backup_service.MongoClient", _spy)

    report = fresh_circuit.run_backup(triggered_by="pytest")
    assert report["status"] == "skipped"
    assert "preset for test" in report["error"]
    assert constructed == [], (
        f"MongoClient must NOT be constructed when circuit is open "
        f"(got {len(constructed)} construction(s))"
    )


def test_run_backup_does_dns_preflight_and_trips_breaker(monkeypatch,
                                                        fresh_circuit):
    """End-to-end: with a dead SECONDARY_MONGO_URL, `run_backup` must
    1) detect the DNS failure, 2) trip the breaker, 3) skip cleanly,
    4) NEVER construct a MongoClient(secondary_url)."""
    from pymongo import MongoClient as _RealMongoClient
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv(
        "SECONDARY_MONGO_URL",
        "mongodb://customer-apps-shard-00-00.djq3ym.mongodb.net:27017,"
        "customer-apps-shard-00-01.djq3ym.mongodb.net:27017/db",
    )

    constructed: list = []

    def _spy(url, *a, **kw):
        constructed.append(url)
        return _RealMongoClient(url, *a, **kw)

    monkeypatch.setattr("services.db_backup_service.MongoClient", _spy)

    report = fresh_circuit.run_backup(triggered_by="pytest")

    assert report["status"] == "skipped"
    assert ("djq3ym" in report["error"]
            or "DNS" in report["error"]
            or "TCP" in report["error"]), f"unexpected error: {report['error']}"
    # critical: NO MongoClient was constructed for the dead secondary
    dead_attempts = [u for u in constructed if "djq3ym" in str(u)]
    assert dead_attempts == [], (
        f"MongoClient was constructed for the dead URL — zombie thread risk: "
        f"{dead_attempts}"
    )
    # circuit was tripped for next 30 min
    open_, _ = fresh_circuit._secondary_circuit_open()
    assert open_ is True
