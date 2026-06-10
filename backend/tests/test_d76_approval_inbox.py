"""
D-76 Approval Inbox — E2E backend tests.

Proves the new endpoints added in
routers/autonomous_repair_admin_router.py work end-to-end against
real Mongo + real JWT auth:

  GET  /api/admin/autonomous-repair/list?status=pending_approval
  POST /api/admin/autonomous-repair/approve/{approval_id}
  POST /api/admin/autonomous-repair/reject/{approval_id}

Each test cleans up after itself (inserts → asserts → deletes).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

API_BASE = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")


def _admin_token() -> str:
    secret = os.environ.get("JWT_SECRET")
    assert secret, "JWT_SECRET unset"
    return jwt.encode(
        {
            "user_id": "test_d76_admin",
            "email": "d76-tests@aurem.live",
            "is_admin": True,
            "is_super_admin": True,
            "role": "super_admin",
        },
        secret,
        algorithm="HS256",
    )


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest_asyncio.fixture
async def fresh_approval(db):
    """Insert one synthetic pending_approval, yield its id, clean up."""
    aid = f"d76_test_{uuid.uuid4().hex[:10]}"
    await db.pending_approvals.insert_one({
        "approval_id": aid,
        "type": "d76_test",
        "status": "pending_approval",
        "cto_status": "awaiting_founder",
        "source": "d76_test",
        "summary": "synthetic pending approval for D-76 endpoint tests",
        "created_at": datetime.now(timezone.utc),
    })
    yield aid
    # Cleanup — either the test approved/rejected (moved to archive)
    # or it left the row in pending. Wipe both.
    await db.pending_approvals.delete_one({"approval_id": aid})
    await db.pending_approvals_archive.delete_one({"approval_id": aid})


@pytest_asyncio.fixture
async def approval_with_proposal(db):
    """Insert pending_approval + linked ora_cto_proposal pair, clean up."""
    aid = f"d76_test_{uuid.uuid4().hex[:10]}"
    pid = f"d76_prop_{uuid.uuid4().hex[:10]}"
    await db.pending_approvals.insert_one({
        "approval_id": aid,
        "cto_proposal_id": pid,
        "type": "d76_test",
        "status": "pending_approval",
        "cto_status": "awaiting_founder",
        "source": "d76_test",
        "summary": "D-76 approve test row (linked to proposal)",
        "created_at": datetime.now(timezone.utc),
    })
    await db.ora_cto_proposals.insert_one({
        "proposal_id": pid,
        "approval_id": aid,
        "status": "awaiting_founder",
        "summary": "synthetic LLM proposal",
        "diagnosis": "synthetic diagnosis for D-76 inbox tests",
        "suggested_fix": "no-op",
        "model": "test-d76",
        "created_at": datetime.now(timezone.utc),
    })
    yield aid, pid
    await db.pending_approvals.delete_one({"approval_id": aid})
    await db.pending_approvals_archive.delete_one({"approval_id": aid})
    await db.ora_cto_proposals.delete_one({"proposal_id": pid})


@pytest.mark.asyncio
async def test_list_requires_admin():
    """GET /list without a Bearer token → 401."""
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(f"{API_BASE}/api/admin/autonomous-repair/list")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_returns_real_rows(fresh_approval):
    """Inserted row shows up in the live feed within one HTTP call."""
    aid = fresh_approval
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/autonomous-repair/list",
            params={"limit": 100, "status": "pending_approval"},
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    ids = {it["approval_id"] for it in body["items"]}
    assert aid in ids, f"inserted {aid} missing from feed (got {len(ids)} ids)"


@pytest.mark.asyncio
async def test_approve_without_proposal_returns_409(fresh_approval):
    """Approve must refuse rows that have no linked LLM proposal —
    otherwise the founder thinks it'll execute and nothing happens."""
    aid = fresh_approval
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.post(
            f"{API_BASE}/api/admin/autonomous-repair/approve/{aid}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 409, r.text
    assert "cto_proposal" in r.text.lower()


@pytest.mark.asyncio
async def test_approve_with_proposal_flips_status(approval_with_proposal, db):
    """End-to-end approve flow: row status → approved, proposal status
    → approved, audit row written."""
    aid, pid = approval_with_proposal
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.post(
            f"{API_BASE}/api/admin/autonomous-repair/approve/{aid}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["proposal_id"] == pid

    # Real DB read confirms the flip
    pa = await db.pending_approvals.find_one({"approval_id": aid})
    assert pa["status"] == "approved"
    assert pa["cto_status"] == "approved"
    assert pa.get("approved_by") == "d76-tests@aurem.live"

    pr = await db.ora_cto_proposals.find_one({"proposal_id": pid})
    assert pr["status"] == "approved"
    assert pr.get("approved_by") == "d76-tests@aurem.live"

    # Audit trail
    audit = await db.autonomous_repair_audit.find_one(
        {"action": "approve", "payload.approval_id": aid},
    )
    assert audit is not None, "audit row missing"


@pytest.mark.asyncio
async def test_reject_archives_row(fresh_approval, db):
    """Reject must move the row to pending_approvals_archive."""
    aid = fresh_approval
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.post(
            f"{API_BASE}/api/admin/autonomous-repair/reject/{aid}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text

    live = await db.pending_approvals.find_one({"approval_id": aid})
    assert live is None, "rejected row still in pending_approvals"
    arch = await db.pending_approvals_archive.find_one({"approval_id": aid})
    assert arch is not None, "rejected row missing from archive"
    assert arch.get("archive_reason") == "manual_reject"


@pytest.mark.asyncio
async def test_list_404_for_unknown_id_action():
    """Approve/reject on a non-existent approval_id returns 404."""
    bogus = f"d76_does_not_exist_{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.post(
            f"{API_BASE}/api/admin/autonomous-repair/reject/{bogus}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 404
