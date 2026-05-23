"""
iter 327f — 15-minute GitHub-unlock TTL + auto-relock

Founder mandate (verbatim, 2026-02-23):
  "Yes — add 15-minute unlock timer.
   One click unlock → auto-relocks after 15 min.
   Audit row on relock."

What this iter delivers:
  1. `UnlockBody.ttl_minutes` (default 15, cap 60).
  2. `/github-unlock` writes `unlock_expires_at` and surfaces
      `seconds_until_relock` in the response.
  3. `is_github_locked()` lazily re-locks when the TTL is past
      AND writes an audit row `action='github_auto_relock_ttl'`.
  4. `get_lock_status()` returns `seconds_until_relock` + the
      ISO `unlock_expires_at` for the UI countdown.
  5. Frontend `GithubLockPill` is now clickable: one-click unlock
      prompts for a reason, then shows mm:ss countdown.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import mongomock_motor

BACKEND  = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# Backend: TTL plumbing
# ─────────────────────────────────────────────

def test_unlockbody_has_ttl_minutes_field():
    from routers.ora_github_lock_router import UnlockBody
    fields = UnlockBody.model_fields
    assert "ttl_minutes" in fields
    f = fields["ttl_minutes"]
    # Default 15, hard cap 60
    assert f.default == 15
    md_str = " ".join(repr(m) for m in (f.metadata or []))
    assert "ge=1" in md_str or "Ge(ge=1)" in md_str
    assert "le=60" in md_str or "Le(le=60)" in md_str


@pytest.mark.asyncio
async def test_get_lock_status_exposes_seconds_until_relock():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327f"]
    gl.set_db(db)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {
            "locked": False,
            "unlock_expires_at": expires_at.isoformat(),
            "unlocked_by": "teji.ss1986@gmail.com",
        }},
        upsert=True,
    )
    s = await gl.get_lock_status()
    assert s["locked"] is False
    assert s["unlock_expires_at"] == expires_at.isoformat()
    assert isinstance(s["seconds_until_relock"], int)
    assert 14 * 60 < s["seconds_until_relock"] <= 15 * 60


@pytest.mark.asyncio
async def test_is_github_locked_auto_relocks_after_ttl_expiry():
    """The core fail-safe: when TTL is past, the next status read
    must lazily flip the row back to locked AND write an audit row."""
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327f"]
    gl.set_db(db)
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {
            "locked": False,
            "unlock_expires_at": expired_at.isoformat(),
            "unlocked_by": "teji.ss1986@gmail.com",
        }},
        upsert=True,
    )
    # First read should detect TTL expiry and relock.
    assert await gl.is_github_locked() is True
    # Row should now be back to locked + auto_relocked_at stamped.
    row = await db.ora_governance.find_one({"_id": "github_lock_state"}, {"_id": 0})
    assert row["locked"] is True
    assert "auto_relocked_at" in row
    assert row.get("auto_relock_reason") == "ttl_expired"
    assert "unlock_expires_at" not in row
    # Audit trail must record the auto-relock.
    audits = await db.ora_governance_audit.find(
        {"action": "github_auto_relock_ttl"}, {"_id": 0}
    ).to_list(length=5)
    assert len(audits) == 1
    assert audits[0]["previous_unlocker"] == "teji.ss1986@gmail.com"


@pytest.mark.asyncio
async def test_is_github_locked_still_unlocked_inside_ttl():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327f"]
    gl.set_db(db)
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {"locked": False, "unlock_expires_at": future.isoformat()}},
        upsert=True,
    )
    assert await gl.is_github_locked() is False


@pytest.mark.asyncio
async def test_assert_writes_allowed_after_ttl_expiry_blocks_again():
    """End-to-end: ORA tries a write after the TTL passed — must hit lock."""
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327f"]
    gl.set_db(db)
    past = datetime.now(timezone.utc) - timedelta(seconds=30)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {"locked": False, "unlock_expires_at": past.isoformat()}},
        upsert=True,
    )
    with pytest.raises(gl.GitHubLockedError):
        await gl.assert_github_writes_allowed("git_push")


# ─────────────────────────────────────────────
# Router behaviour
# ─────────────────────────────────────────────

def test_unlock_endpoint_default_ttl_in_source():
    src = (BACKEND / "routers" / "ora_github_lock_router.py").read_text()
    assert "ttl_minutes" in src
    assert "default=15" in src
    assert "le=60" in src
    assert "unlock_expires_at" in src
    assert "auto-relock at" in src  # log message


def test_relock_endpoint_clears_expiry():
    src = (BACKEND / "routers" / "ora_github_lock_router.py").read_text()
    # Manual relock must unset the expiry too so we don't get a
    # ghost countdown after the founder relocks early.
    assert '"$unset": {"unlock_expires_at": ""}' in src


# ─────────────────────────────────────────────
# UI: clickable pill + countdown
# ─────────────────────────────────────────────

def test_pill_is_clickable_button_with_unlock_handler():
    src = FRONTEND.read_text()
    block = src.split("function GithubLockPill")[1][:6000]
    # Pill is now a <button>, not a <span>
    assert "<button data-testid=\"github-lock-pill\"" in block
    # Calls the unlock endpoint with ttl_minutes=15
    assert "/api/admin/ora/github-unlock" in block
    assert "ttl_minutes: 15" in block
    # Live countdown rendering
    assert "countdown" in block
    assert "seconds_until_relock" in block


def test_pill_prompts_for_reason_before_unlock():
    src = FRONTEND.read_text()
    block = src.split("function GithubLockPill")[1][:6000]
    assert "window.prompt" in block
    # ≥10 char reason enforced client-side too
    assert "length < 10" in block


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_327f_marker_present():
    assert "iter 327f" in (BACKEND / "services" / "github_lockdown.py").read_text()
    assert "iter 327f" in (BACKEND / "routers" / "ora_github_lock_router.py").read_text()
    assert "iter 327f" in FRONTEND.read_text()
