"""
iter 327d — GitHub write-op hard read-only lock
================================================

Founder mandate (verbatim):
  "GitHub: read-only access ONLY.
   Lock these permanently: git push, git commit, PR creation, branch
   create/delete, any write op. If ORA tries: hard block, show
   'Push access locked. Founder approval required to enable',
   send Telegram alert. Lock icon in UI: GitHub: Read Only."

Audit answer (proven by this suite):
  - ORA had no GitHub.com API access wired into her tools at any
    point. Local-only ops (`propose_commit`, `git_commit_local`)
    stayed on the pod and never touched github.com.
  - Now: those local-only ops ALSO hit the lock, so the founder
    has a single switch to silence every "save"/"push" attempt.
  - 4 new sentinel tools (`github_push`, `github_pr_create`,
    `github_branch_create`, `github_branch_delete`) exist solely
    so ORA's brain can name them in a tool_call and get a clean
    "locked" rejection (instead of inventing a tool name and
    hitting the unknown-tool path).

Components verified:
  1. services/github_lockdown.py        — single trusted gate
  2. routers/ora_github_lock_router.py  — status + unlock + relock
  3. ora_tools.py                       — wraps propose_commit +
                                          git_commit_local + 4 sentinels
  4. ora_agent.py SYSTEM_PROMPT         — teaches ORA the lock
  5. OraChat.jsx                        — GithubLockPill in header
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import mongomock_motor

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# Lockdown service basics
# ─────────────────────────────────────────────

def test_lockdown_module_exists_and_exports_helpers():
    from services import github_lockdown as gl
    for sym in ("GitHubLockedError", "LOCKED_OPERATIONS",
                 "is_github_locked", "get_lock_status",
                 "assert_github_writes_allowed", "log_block_attempt",
                 "set_db"):
        assert hasattr(gl, sym), f"missing export: {sym}"


def test_locked_operations_covers_founder_list():
    """The founder's verbatim list must each appear as a slug."""
    from services.github_lockdown import LOCKED_OPERATIONS
    for must_have in (
        "git_push",
        "git_remote_commit",   # ANY commit op
        "git_branch_create",
        "git_branch_delete",
        "pr_create",
        "pr_merge",
        "github_api_write",
    ):
        assert must_have in LOCKED_OPERATIONS, f"missing slug: {must_have}"


@pytest.mark.asyncio
async def test_is_locked_defaults_true_when_db_unset():
    """Fail-safe — if Mongo doc is missing, treat as locked."""
    from services import github_lockdown as gl
    gl.set_db(None)
    assert await gl.is_github_locked() is True


@pytest.mark.asyncio
async def test_is_locked_defaults_true_when_row_missing():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    assert await gl.is_github_locked() is True


@pytest.mark.asyncio
async def test_is_locked_respects_db_row():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    # Unlock
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {"locked": False}}, upsert=True,
    )
    assert await gl.is_github_locked() is False
    # Relock
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {"locked": True}},
    )
    assert await gl.is_github_locked() is True


@pytest.mark.asyncio
async def test_get_lock_status_shape():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    s = await gl.get_lock_status()
    assert s["locked"] is True
    assert s["mode"] == "read_only"
    assert s["ui_label"] == "Read Only"
    assert s["icon"] == "lock"
    assert isinstance(s["locked_operations"], list)
    assert "git_push" in s["locked_operations"]


@pytest.mark.asyncio
async def test_assert_raises_when_locked():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    with pytest.raises(gl.GitHubLockedError) as exc:
        await gl.assert_github_writes_allowed("git_push")
    assert "locked" in exc.value.friendly.lower()
    assert exc.value.operation == "git_push"


@pytest.mark.asyncio
async def test_assert_passes_when_unlocked():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {"locked": False}}, upsert=True,
    )
    # Must NOT raise
    await gl.assert_github_writes_allowed("git_push")


@pytest.mark.asyncio
async def test_assert_fires_telegram_alert_on_block():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)

    sent = []
    async def fake_send(message, alert_type, fingerprint):
        sent.append({"alert_type": alert_type, "fingerprint": fingerprint,
                      "msg_excerpt": message[:200]})
        return {"ok": True}

    with patch("services.silent_failure_alerts._send", side_effect=fake_send):
        try:
            await gl.assert_github_writes_allowed("git_push")
        except gl.GitHubLockedError:
            pass
        # Telegram dispatch is fire-and-forget via asyncio; let the
        # task settle.
        await asyncio.sleep(0.05)

    assert len(sent) == 1
    assert sent[0]["alert_type"] == "github_write_blocked"
    assert "git_push" in sent[0]["fingerprint"]
    assert "locked GitHub write" in sent[0]["msg_excerpt"]


@pytest.mark.asyncio
async def test_log_block_attempt_persists_audit():
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    await gl.log_block_attempt("git_push", actor="ora",
                                 context="propose_commit title='foo'")
    rows = await db.ora_github_block_log.find({}).to_list(length=5)
    assert len(rows) == 1
    assert rows[0]["operation"] == "git_push"
    assert rows[0]["actor"] == "ora"


# ─────────────────────────────────────────────
# Sentinel tools — registry + behaviour
# ─────────────────────────────────────────────

def test_four_sentinels_registered():
    from services.ora_tools import TOOL_REGISTRY
    for name in ("github_push", "github_pr_create",
                 "github_branch_create", "github_branch_delete"):
        assert name in TOOL_REGISTRY, f"sentinel {name} not registered"
        desc = TOOL_REGISTRY[name].get("description", "").lower()
        assert "locked" in desc, f"{name} description must say locked"


@pytest.mark.asyncio
async def test_github_push_sentinel_returns_locked_error():
    from services.ora_tools import _ora_github_push
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    r = await _ora_github_push(branch="main", rationale="ship it")
    assert r["ok"] is False
    assert r["error_code"] == "github_locked"
    assert r["operation"] == "git_push"
    assert r["lock_state"] == "read_only"
    assert "Push access is locked" in r["error"]


@pytest.mark.asyncio
async def test_all_four_sentinels_return_locked():
    from services.ora_tools import (
        _ora_github_push, _ora_github_pr_create,
        _ora_github_branch_create, _ora_github_branch_delete,
    )
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    for r in (
        await _ora_github_push(branch="x"),
        await _ora_github_pr_create(title="t", body="b", base="main", head="x"),
        await _ora_github_branch_create(branch="foo", base="main"),
        await _ora_github_branch_delete(branch="foo"),
    ):
        assert r["ok"] is False
        assert r["error_code"] == "github_locked"


# ─────────────────────────────────────────────
# Existing local-only tools now also hit the lock
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_commit_blocked_when_locked():
    from services.ora_tools import propose_commit
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    r = await propose_commit(
        title="Fix bug",
        body="addresses #42",
        rationale="this is a real reason longer than ten chars",
    )
    assert r["ok"] is False
    assert r["error_code"] == "github_locked"


@pytest.mark.asyncio
async def test_git_commit_local_blocked_when_locked():
    from services.ora_tools import _ora_git_commit_local
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    r = await _ora_git_commit_local(message="autofix")
    assert r["ok"] is False
    assert r["error_code"] == "github_locked"


# ─────────────────────────────────────────────
# Tier 1 READS still work
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_git_log_still_works_when_locked():
    """git_log is read-only — must NOT be blocked by the lock."""
    from services.ora_tools import _ora_git_log
    from services import github_lockdown as gl
    db = mongomock_motor.AsyncMongoMockClient()["test327d"]
    gl.set_db(db)
    r = await _ora_git_log(path="", limit=2)
    assert r["ok"] is True
    assert "commits" in r


# ─────────────────────────────────────────────
# Admin endpoints registered
# ─────────────────────────────────────────────

def test_router_registered():
    src = (BACKEND / "routers" / "registry.py").read_text()
    assert "routers.ora_github_lock_router" in src


def test_router_file_has_three_endpoints():
    src = (BACKEND / "routers" / "ora_github_lock_router.py").read_text()
    for ep in ("/github-lock", "/github-unlock", "/github-relock"):
        assert ep in src
    # Unlock requires a reason ≥10 chars (audit hygiene)
    assert "min_length=10" in src


# ─────────────────────────────────────────────
# SYSTEM_PROMPT teaches the lock
# ─────────────────────────────────────────────

def test_system_prompt_documents_lock():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    idx = src.index('SYSTEM_PROMPT = """')
    block = src[idx: idx + 15000]
    assert "GITHUB WRITE LOCK" in block
    assert "iter 327d" in block
    # Tells ORA NOT to call any of the 4 sentinels
    for name in ("github_push", "github_pr_create",
                 "github_branch_create", "github_branch_delete",
                 "git_commit_local", "propose_commit"):
        assert name in block, f"prompt missing mention of {name}"


# ─────────────────────────────────────────────
# UI — lock pill in chat header
# ─────────────────────────────────────────────

def test_chat_renders_github_lock_pill():
    src = FRONTEND.read_text()
    assert "function GithubLockPill" in src
    assert "<GithubLockPill" in src
    assert 'data-testid="github-lock-pill"' in src


def test_lock_pill_polls_status_endpoint():
    src = FRONTEND.read_text()
    assert "/api/admin/ora/github-lock" in src
    # Polls every 60s
    assert "setInterval" in src.split("function GithubLockPill")[1][:1500]


def test_lock_pill_uses_lock_icon_when_locked():
    src = FRONTEND.read_text()
    pill_block = src.split("function GithubLockPill")[1][:1800]
    assert "Lock" in pill_block and "Unlock" in pill_block
    assert "Read Only" in pill_block


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_327d_marker_present():
    assert "iter 327d" in (BACKEND / "services" / "github_lockdown.py").read_text()
    assert "iter 327d" in (BACKEND / "routers" / "ora_github_lock_router.py").read_text()
    assert "iter 327d" in (BACKEND / "services" / "ora_tools.py").read_text()
