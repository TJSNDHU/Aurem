"""
iter 332b D-20 — Save-project + uploads + sidebar projects tests.
"""
from __future__ import annotations

import io

import pytest


# ── 1. Frontend wiring ────────────────────────────────────────────────
def test_chat_panel_has_upload_button():
    src = open("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx").read()
    assert "dev-cto-chat-upload" in src, "Upload button not rendered"
    assert "dev-cto-chat-file-input" in src, "Hidden file input missing"
    assert "/api/developers/cto/uploads" in src, "Upload POST URL missing"
    # Attachment rendering inside bubbles
    assert "dev-cto-attachment-link" in src
    assert "Attachment" in src


def test_chat_panel_has_save_project_modal():
    src = open("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx").read()
    assert "dev-cto-chat-save" in src, "Save-project header button missing"
    assert "dev-cto-save-modal" in src, "Save-project modal missing"
    assert "dev-cto-save-title" in src
    assert "dev-cto-save-domain" in src
    assert "dev-cto-save-confirm" in src
    # POST endpoint reference
    assert '/api/developers/projects' in src


def test_chat_panel_loads_from_project_id_query():
    """When the URL is /developers/dashboard?project=proj_xxx we must
    load THAT project's history instead of the default chat session."""
    src = open("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx").read()
    assert "useLocation" in src
    assert "project" in src and "params.get" in src
    assert "/api/developers/projects/${encodeURIComponent(projectId)}" in src


def test_sidebar_lists_saved_projects():
    src = open("/app/frontend/src/platform/developers/DeveloperShell.jsx").read()
    assert "dev-sidebar-projects" in src
    assert "dev-sidebar-projects-empty" in src
    assert "/api/developers/projects" in src
    # Click navigates to /developers/dashboard?project=<id>
    assert "?project=" in src
    # Refresh hook on save event
    assert "dev-cto-project-saved" in src


# ── 2. Backend routes exist ───────────────────────────────────────────
def test_project_routes_mounted():
    from routers import developer_portal_router as ROUTER
    paths = {r.path for r in ROUTER.router.routes}
    expected = {
        "/api/developers/projects",
        "/api/developers/projects/{project_id}",
        "/api/developers/cto/uploads",
        "/api/developers/cto/uploads/{file_id}",
    }
    missing = expected - paths
    assert not missing, f"Missing routes: {missing}"


# ── 3. Project save → list → delete round-trip ─────────────────────────
@pytest.mark.asyncio
async def test_project_save_list_delete(monkeypatch, tmp_path):
    from routers import developer_portal_router as ROUTER

    class FakeColl:
        def __init__(self):
            self.docs: list[dict] = []

        async def find_one(self, q, proj=None):
            for d in self.docs:
                if all(d.get(k) == v for k, v in q.items()):
                    return {k: d[k] for k in d if k != "_id"}
            return None

        def find(self, q, proj=None):
            self._cursor_filter = q
            self._cursor_limit = None
            self._cursor_sort = None
            return self

        def sort(self, *_a, **_k): return self
        def limit(self, n): self._cursor_limit = n; return self

        async def to_list(self, length=None):
            out = [d for d in self.docs
                   if all(d.get(k) == v for k, v in self._cursor_filter.items())]
            return out[: (length or len(out))]

        async def insert_one(self, doc): self.docs.append(doc)

        async def delete_one(self, q):
            for i, d in enumerate(self.docs):
                if all(d.get(k) == v for k, v in q.items()):
                    self.docs.pop(i)
                    return type("R", (), {"deleted_count": 1})()
            return type("R", (), {"deleted_count": 0})()

        async def update_one(self, *_a, **_k):
            return type("R", (), {"modified_count": 0})()

    class FakeDB:
        def __init__(self):
            self.developer_projects = FakeColl()
            self.developer_chat_sessions = FakeColl()
            self.developer_uploads = FakeColl()

    ROUTER._db = FakeDB()

    async def _fake_current(_a):
        return {"user_id": "dev_42"}
    monkeypatch.setattr(ROUTER, "_current_dev", _fake_current)

    # Pre-seed a chat session so the save snapshots something.
    await ROUTER._db.developer_chat_sessions.insert_one({
        "user_id": "dev_42", "session_id": "default",
        "messages": [{"role": "user", "content": "Hi"}],
    })

    saved = await ROUTER.save_project(
        ROUTER.ProjectSaveBody(title="My TODO app", domain="todo.acme.com"),
        authorization="Bearer fake",
    )
    assert saved["ok"] is True
    assert saved["project"]["title"] == "My TODO app"
    assert saved["project"]["domain"] == "todo.acme.com"
    assert saved["project"]["messages"][0]["content"] == "Hi"

    listed = await ROUTER.list_projects(authorization="Bearer fake")
    assert len(listed["projects"]) == 1

    pid = saved["project"]["project_id"]
    loaded = await ROUTER.load_project(pid, authorization="Bearer fake")
    assert loaded["title"] == "My TODO app"

    deleted = await ROUTER.delete_project(pid, authorization="Bearer fake")
    assert deleted["ok"] is True

    listed2 = await ROUTER.list_projects(authorization="Bearer fake")
    assert listed2["projects"] == []


# ── 4. Upload size cap ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_upload_rejects_oversize(monkeypatch, tmp_path):
    """A 26 MB file should be rejected with HTTP 413."""
    from fastapi import HTTPException
    from routers import developer_portal_router as ROUTER

    async def _fake_current(_a):
        return {"user_id": "dev_42"}
    monkeypatch.setattr(ROUTER, "_current_dev", _fake_current)
    # Point uploads at a temp dir so we don't pollute /app/data.
    monkeypatch.setattr(ROUTER, "_UPLOAD_ROOT", tmp_path)

    class BigFile:
        filename = "big.bin"
        content_type = "application/octet-stream"
        _payload = b"x" * (26 * 1024 * 1024)
        async def read(self): return self._payload

    with pytest.raises(HTTPException) as ei:
        await ROUTER.upload_attachment(file=BigFile(),
                                         authorization="Bearer fake")
    assert ei.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_persists_metadata(monkeypatch, tmp_path):
    from routers import developer_portal_router as ROUTER

    async def _fake_current(_a):
        return {"user_id": "dev_99"}
    monkeypatch.setattr(ROUTER, "_current_dev", _fake_current)
    monkeypatch.setattr(ROUTER, "_UPLOAD_ROOT", tmp_path)

    captured: list[dict] = []
    class Coll:
        async def insert_one(self, doc): captured.append(doc)
    class DB:
        developer_uploads = Coll()
    ROUTER._db = DB()

    class SmallFile:
        filename = "hello.txt"
        content_type = "text/plain"
        _payload = b"hi"
        async def read(self): return self._payload

    out = await ROUTER.upload_attachment(file=SmallFile(),
                                          authorization="Bearer fake")
    assert out["ok"] is True
    assert out["filename"] == "hello.txt"
    assert out["size"] == 2
    assert out["url"].endswith(out["file_id"])
    assert captured and captured[0]["filename"] == "hello.txt"
    assert (tmp_path / "dev_99").exists()
