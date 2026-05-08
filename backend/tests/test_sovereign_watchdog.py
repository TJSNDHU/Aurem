"""Tests for the Sovereign Watchdog (iter 322j)."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from services import sovereign_watchdog as sw


class FakeColl:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def find_one(self, q, proj=None):  # noqa: ARG002
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    if "$gte" in v and d.get(k, "") < v["$gte"]:
                        ok = False; break
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False; break
                elif d.get(k) != v:
                    ok = False; break
            if ok:
                return d
        return None

    async def count_documents(self, q):
        n = 0
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    if "$gte" in v and d.get(k, "") < v["$gte"]:
                        ok = False; break
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False; break
                elif d.get(k) != v:
                    ok = False; break
            if ok:
                n += 1
        return n

    def find(self, q, proj=None):  # noqa: ARG002
        def matches(d, query):
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$gte" in v and d.get(k, "") < v["$gte"]:
                        return False
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        return False
                elif d.get(k) != v:
                    return False
            return True
        async def gen():
            for d in self.docs:
                if matches(d, q):
                    yield d
        class _C:
            def __init__(self, gen): self.gen = gen
            def sort(self, *_a, **_k): return self
            def limit(self, *_a, **_k): return self
            def __aiter__(self): return self.gen
        return _C(gen())


class FakeDB:
    def __init__(self):
        self.sovereign_watchdog_log = FakeColl()
        self.sovereign_council_escalations = FakeColl()
        self.pillar_restart_requests = FakeColl()

    async def command(self, *_a, **_k):
        return {"ok": 1}


def test_pattern_redis_exhausted_matches():
    line = "WARNING:root:Redis rate limit check failed, using memory: max number of clients reached"
    hit = next(((p, r, k) for p, r, _, k in sw._PATTERNS if p.search(line)), None)
    assert hit is not None
    assert hit[1] == "redis_pool_kick"
    assert hit[2] == "redis_exhausted"


def test_pattern_health_boot_race_matches():
    line = ('2026/05/04 23:55:27 [error] 26#26: *7 connect() failed (111: Connection refused) '
            'while connecting to upstream, client: 10.33.139.1, server: , request: '
            '"GET /health HTTP/1.1", upstream: "http://127.0.0.1:8001/health"')
    hit = next(((p, r, k) for p, r, _, k in sw._PATTERNS if p.search(line)), None)
    assert hit is not None, "boot race pattern must match"
    assert hit[1] == "noop_log_only"
    assert hit[2] == "boot_race"


def test_pattern_pillar_failure_matches():
    line = "[STARTUP] ✗ Pillar 4 worker NOT started — schedulers offline"
    hit = next(((p, r, k) for p, r, _, k in sw._PATTERNS if p.search(line)), None)
    assert hit is not None
    assert hit[1] == "pillar_restart"


@pytest.mark.asyncio
async def test_recipe_db_ping_records_success():
    db = FakeDB()
    out = await sw._recipe_db_ping(db)
    assert out["ping"] is True


@pytest.mark.asyncio
async def test_recipe_pillar_restart_writes_request():
    import re
    db = FakeDB()
    m = re.search(r"Pillar\s+(\d+)\s+worker NOT started",
                  "[STARTUP] Pillar 4 worker NOT started")
    out = await sw._recipe_pillar_restart(db, m)
    assert out["pillar"] == "4"
    assert out["request_filed"] is True
    assert len(db.pillar_restart_requests.docs) == 1


@pytest.mark.asyncio
async def test_scan_once_dedupes_within_window(tmp_path, monkeypatch):
    log_file = tmp_path / "backend.err.log"
    log_file.write_text(
        "WARNING:root:Redis rate limit check failed, using memory: max number of clients reached\n"
    )
    monkeypatch.setattr(sw, "LOG_PATHS", [str(log_file)])
    db = FakeDB()
    summary1 = await sw.scan_once(db)
    summary2 = await sw.scan_once(db)
    assert summary1["findings"] == 1
    assert summary2["skipped_duplicates"] >= 1
    assert summary2["findings"] == 0


@pytest.mark.asyncio
async def test_scan_once_health_boot_race_logged_as_noop(tmp_path, monkeypatch):
    log_file = tmp_path / "backend.err.log"
    log_file.write_text(
        '2026/05/04 [error] connect() failed (111: Connection refused) '
        'while connecting to upstream, '
        'request: "GET /health HTTP/1.1", upstream: "http://127.0.0.1:8001/health"\n'
    )
    monkeypatch.setattr(sw, "LOG_PATHS", [str(log_file)])
    db = FakeDB()
    summary = await sw.scan_once(db)
    assert summary["findings"] == 1
    assert summary["fixed"] == 1
    # The recipe is noop, but it succeeded, so no escalation
    log = [d for d in db.sovereign_watchdog_log.docs if d.get("kind") == "boot_race"]
    assert log and log[0]["recipe_result"]["action"] == "boot_artifact_noted"


@pytest.mark.asyncio
async def test_scan_once_no_log_file_returns_empty(monkeypatch):
    monkeypatch.setattr(sw, "LOG_PATHS", ["/nonexistent/path"])
    db = FakeDB()
    summary = await sw.scan_once(db)
    assert summary["findings"] == 0
    assert summary["fixed"] == 0


@pytest.mark.asyncio
async def test_status_green_on_empty_db():
    db = FakeDB()
    s = await sw.get_watchdog_status(db)
    assert s["state"] == "green"


@pytest.mark.asyncio
async def test_status_red_on_unacked_council_escalation():
    db = FakeDB()
    db.sovereign_council_escalations.docs.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "ack_by_ora_agent": False,
    })
    s = await sw.get_watchdog_status(db)
    assert s["state"] == "red"
    assert s["unacked"] == 1


@pytest.mark.asyncio
async def test_status_yellow_on_unfixed_finding():
    db = FakeDB()
    db.sovereign_watchdog_log.docs.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "mongo_timeout",
        "success": False,
    })
    s = await sw.get_watchdog_status(db)
    assert s["state"] == "yellow"


@pytest.mark.asyncio
async def test_council_escalation_path_when_high_severity_recipe_fails(
    tmp_path, monkeypatch,
):
    """High-severity finding + failing recipe must consult Council."""
    log_file = tmp_path / "backend.err.log"
    log_file.write_text("[STARTUP] Pillar 7 worker NOT started\n")
    monkeypatch.setattr(sw, "LOG_PATHS", [str(log_file)])

    async def boom(*_a, **_k):
        return {"err": "intentional_test_failure"}
    monkeypatch.setitem(sw._RECIPES, "pillar_restart", boom)

    async def fake_council(*_a, **_k):
        return {"ok": True, "final_response": "ESCALATE — pillar dead",
                "winner": "dev", "winner_score": 9}

    db = FakeDB()
    with patch("services.ora_council.convene_council", side_effect=fake_council):
        summary = await sw.scan_once(db)
    assert summary["council_consults"] == 1
    assert len(db.sovereign_council_escalations.docs) == 1
    e = db.sovereign_council_escalations.docs[0]
    assert e["council_winner"] == "dev"
    assert e["ack_by_ora_agent"] is False


@pytest.mark.asyncio
async def test_get_recent_findings_excludes_scan_summary():
    db = FakeDB()
    ts = datetime.now(timezone.utc).isoformat()
    db.sovereign_watchdog_log.docs.extend([
        {"ts": ts, "kind": "scan_summary", "success": True},
        {"ts": ts, "kind": "redis_exhausted", "success": True},
    ])
    rows = await sw.get_recent_findings(db)
    kinds = [r["kind"] for r in rows]
    assert "scan_summary" not in kinds
    assert "redis_exhausted" in kinds
