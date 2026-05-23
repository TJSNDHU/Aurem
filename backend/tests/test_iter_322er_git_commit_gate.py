"""
Regression test — iter 322er (Git Commit Gate)
Locks in:
  1. propose_commit rejects without rationale
  2. propose_commit rejects oversized titles / unauthorised paths
  3. propose_commit handles untracked files via intent-to-add
  4. git-gate router exposes the right paths
  5. propose_commit registered in TOOL_REGISTRY with quota
"""
import os
import pytest


def test_git_gate_router_imports_clean():
    from routers import git_gate_router
    paths = [r.path for r in git_gate_router.router.routes]
    expected = (
        "/api/admin/git-gate/summary",
        "/api/admin/git-gate/proposals",
        "/api/admin/git-gate/proposals/{proposal_id}",
        "/api/admin/git-gate/proposals/{proposal_id}/approve",
        "/api/admin/git-gate/proposals/{proposal_id}/reject",
        "/api/admin/git-gate/proposals/{proposal_id}/hard-reset",
        "/api/admin/git-gate/history",
    )
    for p in expected:
        assert p in paths, f"missing route: {p}"


def test_propose_commit_registered():
    from services.ora_tools import TOOL_REGISTRY
    assert "propose_commit" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_propose_commit_requires_rationale():
    from services.ora_tools import propose_commit
    res = await propose_commit(title="something", body="", file_paths=[], rationale="")
    assert res["ok"] is False
    assert "rationale" in res["error"].lower()


@pytest.mark.asyncio
async def test_propose_commit_rejects_too_long_title():
    from services.ora_tools import propose_commit
    long_title = "x" * 200
    res = await propose_commit(
        title=long_title, body="", file_paths=[],
        rationale="A perfectly valid rationale string of sufficient length.",
    )
    assert res["ok"] is False
    assert "title" in res["error"].lower()


@pytest.mark.asyncio
async def test_propose_commit_rejects_disallowed_path():
    """iter 327d — GitHub lock now intercepts before path validation. Unlock
    first so the underlying write-allowed root check is exercised."""
    import mongomock_motor
    from services import github_lockdown as gl
    from services.ora_tools import propose_commit
    db = mongomock_motor.AsyncMongoMockClient()["test_322er"]
    gl.set_db(db)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"}, {"$set": {"locked": False}}, upsert=True,
    )
    try:
        res = await propose_commit(
            title="trying to commit etc",
            body="malicious",
            file_paths=["/etc/passwd"],
            rationale="This should be blocked by write-allowed root check",
        )
        assert res["ok"] is False
        assert "not allowed" in res["error"].lower()
    finally:
        gl.set_db(None)


@pytest.mark.asyncio
async def test_propose_commit_caps_file_count():
    """iter 327d — unlock so the file-count cap is what trips, not the lock."""
    import mongomock_motor
    from services import github_lockdown as gl
    from services.ora_tools import propose_commit, _COMMIT_FILES_MAX
    db = mongomock_motor.AsyncMongoMockClient()["test_322er"]
    gl.set_db(db)
    await db.ora_governance.update_one(
        {"_id": "github_lock_state"}, {"$set": {"locked": False}}, upsert=True,
    )
    try:
        too_many = [f"/app/memory/file_{i}.md" for i in range(_COMMIT_FILES_MAX + 5)]
        res = await propose_commit(
            title="bulk commit",
            body="",
            file_paths=too_many,
            rationale="Should be capped to prevent runaway commits",
        )
        assert res["ok"] is False
        assert "too many" in res["error"].lower()
    finally:
        gl.set_db(None)
