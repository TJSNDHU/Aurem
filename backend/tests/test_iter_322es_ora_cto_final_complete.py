"""
Regression test — iter 322es (ORA CTO Final Complete)
Locks in:
  1. New routers (ora_files, ora_settings, ora_rollback) load cleanly
  2. ora_files MIME whitelist + size cap configured
  3. ora_settings exposes all 5 sections + helpers
  4. ora_rollback path-decoder reverses safe_edit's encoding correctly
  5. Skill `aurem-322es-ora-cto-final-complete` lives in library + broadcast
"""
import os
import pytest
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_new_routers_import_cleanly():
    from routers import ora_files_router, ora_settings_router, ora_rollback_router
    for mod, expected_prefix in (
        (ora_files_router,    "/api/admin/ora-files"),
        (ora_settings_router, "/api/admin/ora-settings"),
        (ora_rollback_router, "/api/admin/ora-rollback"),
    ):
        paths = [r.path for r in mod.router.routes]
        assert any(p.startswith(expected_prefix) for p in paths), \
            f"{mod.__name__} has no {expected_prefix} routes"


def test_ora_files_constraints():
    from routers.ora_files_router import MAX_BYTES, ALLOWED_MIME, ALLOWED_EXT
    assert MAX_BYTES == 30 * 1024 * 1024
    # core formats present
    for m in ("application/pdf",
               "image/jpeg", "image/png",
               "audio/mpeg",
               "video/mp4"):
        assert m in ALLOWED_MIME, f"missing mime: {m}"
    for e in (".pdf", ".docx", ".jpg", ".png", ".mp3", ".mp4"):
        assert e in ALLOWED_EXT, f"missing ext: {e}"


def test_ora_settings_section_defaults():
    from routers.ora_settings_router import _SECTION_DEFAULTS
    for sec in ("github", "permissions", "council", "notifications", "audit"):
        assert sec in _SECTION_DEFAULTS, f"missing section: {sec}"
    # Critical guarantees
    assert _SECTION_DEFAULTS["council"]["hard_gate"] is True
    assert "security" in _SECTION_DEFAULTS["council"]["peer_roles"]
    assert _SECTION_DEFAULTS["audit"]["retention_days"] >= 30


def test_ora_rollback_path_decoder():
    """The encoder used by safe_edit is `path.replace('/', '__')`; verify
    the decoder is the inverse so restore() never picks the wrong file."""
    from routers.ora_rollback_router import _backup_to_origpath
    p = _backup_to_origpath("20260512T060000__app__backend__server.py.bak")
    assert str(p) == "/app/backend/server.py"
    p2 = _backup_to_origpath("ts__app__memory__PRD.md.bak")
    assert str(p2) == "/app/memory/PRD.md"


@pytest.mark.asyncio
async def test_iter_322es_skill_persisted():
    db = _db()
    s = await db.ora_skills_library.find_one(
        {"id": "aurem-322es-ora-cto-final-complete"},
        {"_id": 0, "name": 1, "body": 1},
    )
    assert s is not None, "iter 322es skill missing from library"
    assert len(s["body"]) > 2000
    assert "Preview" in s["body"] and "Rollback" in s["body"]
    bc = await db.ora_skills_broadcast.find_one({"_id": "active"})
    assert "aurem-322es-ora-cto-final-complete" in (bc.get("skill_ids") or [])


def test_iter_322es_quota_machinery_removed():
    """Quotas were stripped at the founder's request."""
    import services.ora_tools as ot
    for sym in ("_QUOTA_PER_HOUR", "_check_quota", "_maybe_alert_quota",
                 "_record_llm_cost"):
        assert not hasattr(ot, sym), f"quota symbol still present: {sym}"
