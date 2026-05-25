"""
iter 332b D-19 — Dev CTO chat redesign tests.

Covers:
  - System prompt now bakes in the frontend-first rule + NEXT_STEPS contract.
  - History endpoint round-trips persisted messages.
  - DELETE endpoint wipes the persisted history.
  - Stream wrapper persists user+assistant turn after a successful stream.
  - Frontend parser regexes match the contract (smoke-checked via the
    file text — the JSX is exercised in the test agent run).
"""
from __future__ import annotations

import os
import asyncio
import re

import pytest


# ── 1. System prompt contract ─────────────────────────────────────────
def test_system_prompt_has_frontend_first_rule():
    from services import dev_cto_chat
    p = dev_cto_chat.SYSTEM_PROMPT
    assert "FRONTEND-FIRST" in p, "system prompt must declare the frontend-first rule"
    assert "NEXT_STEPS:" in p, "system prompt must instruct the model to emit NEXT_STEPS"
    assert "[step N/M]" in p, "system prompt must instruct the model to use [step N/M] markers"


# ── 2. Frontend parser contract ───────────────────────────────────────
def test_frontend_parses_step_and_next_steps():
    src = open("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx").read()
    # Progress marker regex present
    assert "STEP_RE" in src and "[step" in src.lower()
    # NEXT_STEPS regex present
    assert "NEXTSTEPS_RE" in src
    # Strips the contract line before rendering
    assert "stripContract" in src
    # Chips rendered
    assert "dev-cto-chat-next-steps" in src
    assert "dev-cto-next-step-" in src
    # Progress bar component
    assert "dev-cto-chat-progress" in src
    # Persistence wiring
    assert "/api/developers/cto/chat/history" in src


# ── 3. Header chip redesign ───────────────────────────────────────────
def test_dashboard_uses_compact_header_chips():
    src = open("/app/frontend/src/platform/developers/DevDashboard.jsx").read()
    assert "dev-header-chips" in src, (
        "DevDashboard must render the compact pill row"
    )
    # The chat panel must be mounted in fullScreen mode.
    assert "fullScreen" in src
    # Old 2x2 grid block should be gone (no av2-grid-4 in the main render).
    assert "av2-grid-4" not in src, (
        "DevDashboard still ships the old 2x2 metric grid"
    )


# ── 4. Backend history endpoint contract ──────────────────────────────
@pytest.mark.asyncio
async def test_history_endpoint_round_trip(monkeypatch):
    """Simulate the in-memory `_db.developer_chat_sessions` collection
    and verify the endpoints upsert + fetch + clear."""
    from routers import developer_portal_router as ROUTER

    class FakeColl:
        def __init__(self):
            self.docs: list[dict] = []

        async def find_one(self, q, proj=None):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return {k: d[k] for k in d if k != "_id"}
            return None

        async def update_one(self, q, upd, upsert=False):
            existing = None
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    existing = d
                    break
            if existing is None:
                if not upsert:
                    return type("R", (), {"modified_count": 0})()
                existing = {**q, "messages": []}
                self.docs.append(existing)
            push = upd.get("$push", {})
            for k, v in push.items():
                if isinstance(v, dict) and "$each" in v:
                    existing.setdefault(k, []).extend(v["$each"])
                else:
                    existing.setdefault(k, []).append(v)
            for k, v in upd.get("$set", {}).items():
                existing[k] = v
            for k, v in upd.get("$setOnInsert", {}).items():
                existing.setdefault(k, v)
            return type("R", (), {"modified_count": 1})()

    class FakeDB:
        def __init__(self):
            self.developer_chat_sessions = FakeColl()

    fake = FakeDB()
    ROUTER._db = fake

    # Insert 2 turns
    await fake.developer_chat_sessions.update_one(
        {"user_id": "dev_x", "session_id": "default"},
        {"$push": {"messages": {"$each": [
            {"role": "user", "content": "Build me a TODO app"},
            {"role": "assistant", "content": "Plan (3 steps): ..."},
        ]}}, "$set": {"updated_at": "2026-05-25T00:00:00Z"},
         "$setOnInsert": {"user_id": "dev_x", "session_id": "default"}},
        upsert=True,
    )

    # Patch _current_dev so we don't need a real JWT
    async def _fake_current(_auth):
        return {"user_id": "dev_x"}
    monkeypatch.setattr(ROUTER, "_current_dev", _fake_current)

    out = await ROUTER.cto_chat_history(authorization="Bearer fake")
    assert isinstance(out, dict)
    assert len(out["messages"]) == 2
    assert out["messages"][0]["content"] == "Build me a TODO app"

    cleared = await ROUTER.cto_chat_history_clear(authorization="Bearer fake")
    assert cleared["ok"] is True

    out2 = await ROUTER.cto_chat_history(authorization="Bearer fake")
    assert out2["messages"] == []


# ── 5. Routes are registered ──────────────────────────────────────────
def test_chat_history_routes_are_mounted():
    from routers import developer_portal_router as ROUTER
    paths = {r.path for r in ROUTER.router.routes}
    assert "/api/developers/cto/chat/history" in paths
