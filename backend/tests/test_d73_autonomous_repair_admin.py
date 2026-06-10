"""
test_d73_autonomous_repair_admin.py — iter D-73 regression guard.

The D-71p audit + D-72 deep-dive surfaced that `pending_approvals` had
been silently piling up for 2 months because:

  * 428 rows used a pre-iter-325f schema (no `type`, no `tier`) so
    `services.ora_cto_repair_agent.run_repair_tick` quietly skipped
    them.
  * 14 newer rows targeted test-only domains, so the founder never
    approved fixes for them and they sat in `awaiting_founder` state
    forever.

iter D-73 fixed it via a real admin router (`routers/autonomous_
repair_admin_router.py`) + observability in `run_repair_tick`. These
tests hit the REAL backend over HTTP, with REAL Mongo writes/reads.
No mocks.

Coverage:
  * GET /stats — honest counts, no shortcut
  * POST /archive-legacy — moves no-type rows; idempotent
  * POST /archive-test-targets — only test-target rows; respects custom
    AUREM_AUTO_REPAIR_TEST_HOSTS
  * POST /reject/{approval_id} — moves a specific row + cancels its
    proposal
  * POST /expire-stale?days=N — moves stale awaiting_founder rows
  * POST /ensure-ttl — creates the TTL index with the requested retention
  * Non-admin token returns 403
  * `run_repair_tick` exposes `legacy_count` + `stale_awaiting` in stats

Run: PYTHONPATH=/app/backend python3 -m pytest tests/test_d73_autonomous_repair_admin.py -v
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, "/app/backend")


# ─── helpers ──────────────────────────────────────────────────────────

def _backend_url() -> str:
    env_file = Path("/app/frontend/.env")
    for line in env_file.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


def _founder_token() -> str:
    """Log in and return the founder's JWT."""
    api = _backend_url()
    r = httpx.post(
        f"{api}/api/platform/auth/login",
        json={"email": "teji.ss1986@gmail.com",
              "password": "Aurem@Founder2026!"},
        timeout=15.0,
    )
    if r.status_code != 200:
        pytest.skip(f"founder login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


def _non_admin_token() -> str:
    """Forge a JWT with the right secret but no admin claims, so we can
    prove the admin gate rejects it."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # Try to read it from the live backend's env
        env_file = Path("/app/backend/.env")
        for line in env_file.read_text().splitlines():
            if line.startswith("JWT_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not secret:
        pytest.skip("JWT_SECRET unavailable")
    import jwt as pyjwt
    return pyjwt.encode(
        {"email": "notadmin@example.com", "role": "user",
         "is_admin": False, "is_super_admin": False,
         "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()},
        secret, algorithm="HS256",
    )


async def _get_db():
    """Direct Mongo handle for setup/teardown that doesn't go through
    the public API."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


# ─── fixtures ─────────────────────────────────────────────────────────

TEST_PREFIX = f"d73test_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def api_url():
    return _backend_url()


@pytest.fixture(scope="module")
def admin_token():
    return _founder_token()


@pytest.fixture
def db_event_loop():
    """One event loop per test for direct-DB ops."""
    return asyncio.new_event_loop()


@pytest.fixture
def seed_fixtures(db_event_loop):
    """Seed 3 docs of each kind (legacy / test-target / stale-founder)
    so each test starts from a known state. Cleans up the seeded rows
    on teardown so we never pollute prod data."""
    async def _seed():
        db = await _get_db()
        # 3 legacy rows (no `type` field)
        legacy_ids = []
        for i in range(3):
            aid = f"{TEST_PREFIX}_legacy_{i}"
            await db.pending_approvals.insert_one({
                "approval_id": aid,
                "status": "pending",
                "fix": {"description": "legacy auto_repair row from old schema"},
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            })
            legacy_ids.append(aid)

        # 3 test-target Shannon rows
        test_target_ids = []
        for i, host in enumerate(("score-calc-test.com", "test-target.com", "example.com")):
            aid = f"{TEST_PREFIX}_tt_{i}"
            pid = f"{TEST_PREFIX}_prop_{i}"
            await db.pending_approvals.insert_one({
                "approval_id": aid,
                "type": "security_fix",
                "status": "pending_approval",
                "tier": 2,
                "severity": "critical",
                "title": f"[CRIT] test on {host}",
                "source": "shannon",
                "metadata": {"target": f"https://{host}/foo"},
                "cto_proposal_id": pid,
                "cto_status": "awaiting_founder",
                "created_at": datetime.now(timezone.utc) - timedelta(days=3),
            })
            await db.ora_cto_proposals.insert_one({
                "proposal_id": pid,
                "approval_id": aid,
                "status": "awaiting_founder",
            })
            test_target_ids.append((aid, pid))

        # 3 stale-founder rows (>20 days, real-looking customer domain)
        stale_ids = []
        for i in range(3):
            aid = f"{TEST_PREFIX}_stale_{i}"
            pid = f"{TEST_PREFIX}_staleprop_{i}"
            await db.pending_approvals.insert_one({
                "approval_id": aid,
                "type": "security_fix",
                "status": "pending_approval",
                "tier": 2,
                "severity": "high",
                "title": f"[HIGH] HSTS missing #{i}",
                "source": "shannon",
                "metadata": {"target": "https://realcustomer.example/foo"},
                "cto_proposal_id": pid,
                "cto_status": "awaiting_founder",
                "created_at": datetime.now(timezone.utc) - timedelta(days=20),
            })
            await db.ora_cto_proposals.insert_one({
                "proposal_id": pid,
                "approval_id": aid,
                "status": "awaiting_founder",
            })
            stale_ids.append((aid, pid))

        return {"legacy": legacy_ids, "tt": test_target_ids, "stale": stale_ids}

    seeded = db_event_loop.run_until_complete(_seed())
    yield seeded

    async def _cleanup():
        db = await _get_db()
        all_aids = (list(seeded["legacy"]) +
                    [aid for aid, _ in seeded["tt"]] +
                    [aid for aid, _ in seeded["stale"]])
        all_pids = ([pid for _, pid in seeded["tt"]] +
                    [pid for _, pid in seeded["stale"]])
        # Remove from BOTH primary and archive (so re-running tests is clean)
        await db.pending_approvals.delete_many({"approval_id": {"$in": all_aids}})
        await db.pending_approvals_archive.delete_many({"approval_id": {"$in": all_aids}})
        await db.ora_cto_proposals.delete_many({"proposal_id": {"$in": all_pids}})
        await db.autonomous_repair_audit.delete_many(
            {"payload.sample": {"$in": all_aids}}
        )

    db_event_loop.run_until_complete(_cleanup())
    db_event_loop.close()


# ─── tests ────────────────────────────────────────────────────────────

def test_stats_requires_admin(api_url):
    """Non-admin token → 403."""
    r = httpx.get(
        f"{api_url}/api/admin/autonomous-repair/stats",
        headers={"Authorization": f"Bearer {_non_admin_token()}"},
        timeout=10.0,
    )
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


def test_stats_returns_honest_counts(api_url, admin_token, seed_fixtures):
    r = httpx.get(
        f"{api_url}/api/admin/autonomous-repair/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    pa = body["pending_approvals"]
    # We seeded 3 legacy + 3 test-target + 3 stale = 9 rows
    assert pa["legacy_no_type"] >= 3, f"expected ≥3 legacy, got {pa['legacy_no_type']}"
    assert pa["test_target_findings"] >= 3, (
        f"expected ≥3 test-target rows, got {pa['test_target_findings']}"
    )
    assert pa["stale_awaiting_founder_gt_7d"] >= 3, (
        f"expected ≥3 stale, got {pa['stale_awaiting_founder_gt_7d']}"
    )
    # ora_cto_proposals breakdown must include the seeded proposals
    assert body["ora_cto_proposals"]["total"] >= 6


def test_archive_legacy_moves_no_type_rows(api_url, admin_token, seed_fixtures, db_event_loop):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/archive-legacy",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["ok"] is True
    assert body["moved"] >= 3, f"expected ≥3 moved, got {body['moved']}"

    # Verify the 3 legacy seeds are GONE from pending_approvals
    async def _check():
        db = await _get_db()
        remaining = await db.pending_approvals.count_documents(
            {"approval_id": {"$in": seed_fixtures["legacy"]}}
        )
        archived = await db.pending_approvals_archive.count_documents(
            {"approval_id": {"$in": seed_fixtures["legacy"]}}
        )
        return remaining, archived

    remaining, archived = db_event_loop.run_until_complete(_check())
    assert remaining == 0, f"legacy rows still in primary: {remaining}"
    assert archived == 3, f"legacy rows NOT in archive: {archived}"


def test_archive_legacy_is_idempotent(api_url, admin_token, seed_fixtures):
    """Running it a SECOND time after the first must return moved=0
    (or fewer than 3) — it shouldn't re-archive."""
    httpx.post(
        f"{api_url}/api/admin/autonomous-repair/archive-legacy",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/archive-legacy",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    assert r.status_code == 200
    # Second call must not double-archive the rows we just moved
    assert r.json()["moved"] < 3, (
        f"second call re-archived the same rows: {r.json()['moved']}"
    )


def test_archive_test_targets_only_touches_test_domains(api_url, admin_token, seed_fixtures, db_event_loop):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/archive-test-targets",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["ok"] is True
    assert body["moved"] >= 3, f"expected ≥3 test-target rows, got {body['moved']}"

    async def _verify():
        db = await _get_db()
        # Test-target seeds GONE from primary
        tt_aids = [aid for aid, _ in seed_fixtures["tt"]]
        in_primary = await db.pending_approvals.count_documents(
            {"approval_id": {"$in": tt_aids}}
        )
        # Stale-founder seeds (realcustomer.example) STILL in primary
        stale_aids = [aid for aid, _ in seed_fixtures["stale"]]
        stale_in_primary = await db.pending_approvals.count_documents(
            {"approval_id": {"$in": stale_aids}}
        )
        # Linked proposals cancelled
        tt_pids = [pid for _, pid in seed_fixtures["tt"]]
        cancelled = await db.ora_cto_proposals.count_documents(
            {"proposal_id": {"$in": tt_pids}, "status": "cancelled"}
        )
        return in_primary, stale_in_primary, cancelled

    in_primary, stale_in_primary, cancelled = db_event_loop.run_until_complete(_verify())
    assert in_primary == 0, f"test-target rows still in primary: {in_primary}"
    assert stale_in_primary == 3, (
        f"REAL stale rows wrongly archived alongside test-targets: only {stale_in_primary} left"
    )
    assert cancelled == 3, (
        f"linked proposals not cancelled: {cancelled} of 3"
    )


def test_reject_specific_approval(api_url, admin_token, seed_fixtures, db_event_loop):
    aid, pid = seed_fixtures["stale"][0]
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/reject/{aid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["ok"] is True
    assert body["approval_id"] == aid
    assert body["cancelled_proposal_id"] == pid

    async def _verify():
        db = await _get_db()
        in_primary = await db.pending_approvals.count_documents({"approval_id": aid})
        archived = await db.pending_approvals_archive.find_one(
            {"approval_id": aid, "archive_reason": "manual_reject"}
        )
        prop = await db.ora_cto_proposals.find_one({"proposal_id": pid})
        return in_primary, archived, prop

    in_primary, archived, prop = db_event_loop.run_until_complete(_verify())
    assert in_primary == 0
    assert archived is not None
    assert prop and prop.get("status") == "cancelled"
    assert prop.get("cancelled_reason") == "manual_reject"


def test_reject_404_for_unknown_id(api_url, admin_token):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/reject/never_existed",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 404


def test_restore_round_trip(api_url, admin_token, seed_fixtures, db_event_loop):
    """Archive → restore must end with the row back in primary, the
    proposal re-opened, and the archive row gone."""
    aid, pid = seed_fixtures["stale"][1]
    # First reject it so it lands in archive
    r1 = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/reject/{aid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r1.status_code == 200

    # Now restore
    r2 = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/restore/{aid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r2.status_code == 200, r2.text[:300]
    assert r2.json()["approval_id"] == aid

    async def _verify():
        db = await _get_db()
        primary = await db.pending_approvals.find_one({"approval_id": aid})
        in_archive = await db.pending_approvals_archive.count_documents(
            {"approval_id": aid}
        )
        prop = await db.ora_cto_proposals.find_one({"proposal_id": pid})
        return primary, in_archive, prop

    primary, in_archive, prop = db_event_loop.run_until_complete(_verify())
    assert primary is not None, "row not restored to primary"
    assert in_archive == 0, "row still lingering in archive after restore"
    assert primary.get("restored_at"), "restored_at field missing"
    assert primary.get("status") == "pending_approval"
    # cto_proposal_id must be cleared so agent re-evaluates with fresh LLM
    assert "cto_proposal_id" not in primary, (
        "cto_proposal_id NOT cleared on restore — agent will skip this row"
    )
    # Proposal marked restored (not cancelled forever)
    assert prop and prop.get("status") == "restored"


def test_restore_404_for_unknown_id(api_url, admin_token):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/restore/never_existed",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 404


def test_expire_stale_archives_awaiting_founder_gt_n_days(api_url, admin_token, seed_fixtures, db_event_loop):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/expire-stale?days=14",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["ok"] is True
    assert body["older_than_days"] == 14
    assert body["moved"] >= 3, f"expected ≥3 stale moved, got {body['moved']}"

    async def _verify():
        db = await _get_db()
        stale_aids = [aid for aid, _ in seed_fixtures["stale"]]
        remaining = await db.pending_approvals.count_documents(
            {"approval_id": {"$in": stale_aids}}
        )
        archived = await db.pending_approvals_archive.count_documents(
            {"approval_id": {"$in": stale_aids},
             "archive_reason": "founder_no_response_gt_14d"}
        )
        return remaining, archived

    remaining, archived = db_event_loop.run_until_complete(_verify())
    assert remaining == 0
    assert archived == 3


def test_ensure_ttl_creates_index(api_url, admin_token, db_event_loop):
    r = httpx.post(
        f"{api_url}/api/admin/autonomous-repair/ensure-ttl?retention_days=60",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["ok"] is True
    assert body["retention_days"] == 60
    # 4 target collections; pending_approvals MUST succeed (others best-effort)
    assert body["results"]["pending_approvals"]["ok"] is True

    async def _verify_index():
        db = await _get_db()
        for idx in await db.pending_approvals.list_indexes().to_list(50):
            if idx.get("expireAfterSeconds") == 60 * 86400:
                return True
        return False

    assert db_event_loop.run_until_complete(_verify_index()), (
        "TTL index with 60-day expireAfterSeconds NOT found"
    )


def test_run_repair_tick_exposes_observability_fields(db_event_loop):
    """`run_repair_tick` must include `legacy_count` and `stale_awaiting`
    in its stats dict — without these fields, the cron logs say nothing
    about the backlog and the operator has no signal."""
    async def _run():
        from services.ora_cto_repair_agent import run_repair_tick
        db = await _get_db()
        return await run_repair_tick(db)

    stats = db_event_loop.run_until_complete(_run())
    assert stats.get("ok") is True
    assert "legacy_count" in stats, (
        f"run_repair_tick missing `legacy_count`: {stats}"
    )
    assert "stale_awaiting" in stats, (
        f"run_repair_tick missing `stale_awaiting`: {stats}"
    )
    assert isinstance(stats["legacy_count"], int)
    assert isinstance(stats["stale_awaiting"], int)
