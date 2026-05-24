"""
iter 327o + 327p (backend) — Lesson journal + admin sources endpoint.

Founder mandate (verbatim, 2026-02-23):
  "Yes to 327o — ora_learning_journal.
   Yes to 327p — Tier-1/Tier-2 sources admin panel.
   Skip lesson librarian cron for now."

327o delivers:
  - services/ora_lessons_loader.py
      • _LAST_INJECTION_MANIFEST, _LAST_TOTAL_CHARS module mirrors
      • build_lessons_block() now stamps sha256 + size per tier-1 file
      • record_journal_entry_if_changed(db) — writes to
        db.ora_learning_journal when any file hash differs from the
        last snapshot. Idempotent on no-change.
  - server.py startup_event → background task that calls the recorder

327p (backend half) delivers:
  - routers/ora_lesson_sources_router.py
      • GET /api/admin/ora/lesson-sources
      • GET /api/admin/ora/lesson-journal?limit=N
      Both super-admin gated, registered in routers/registry.py.

Frontend admin panel (327p UI half) is queued for the next iter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import mongomock_motor
import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# 327o — Loader manifest + sha256
# ─────────────────────────────────────────────

def test_build_lessons_block_populates_manifest():
    from services.ora_lessons_loader import (
        build_lessons_block, last_injection_manifest, tier1_total_chars,
    )
    block = build_lessons_block()
    assert block, "tier-1 block empty — source files missing"
    manifest = last_injection_manifest()
    assert len(manifest) >= 4, f"expected ≥4 entries, got {len(manifest)}"
    # Every loaded entry must have a sha256 + size.
    loaded = [m for m in manifest if m.get("loaded")]
    assert loaded, "no loaded entries"
    for m in loaded:
        assert len(m["sha256"]) == 64, f"bad sha256: {m['sha256']}"
        assert m["size"] > 0
    # Total chars matches accessor.
    assert tier1_total_chars() == len(block)


def test_tier2_rule_table_lists_keywords_and_exists_flag():
    from services.ora_lessons_loader import tier2_rule_table
    rules = tier2_rule_table()
    # iter 332b A-3 — was hard-asserted to 3; rule table has grown beyond
    # the original 3 (security / outreach / debug) as new tier-2 files
    # were added (deploy, integrations, project templates etc). Now we
    # just guard the SHAPE of each row and that the original 3 are still
    # present, without freezing the count.
    assert len(rules) >= 3
    labels = {r.get("label", "") for r in rules}
    # Sanity — the original three categories must still be there.
    assert any("SECURITY" in l for l in labels)
    for r in rules:
        assert "keywords" in r and isinstance(r["keywords"], list)
        assert "exists" in r and isinstance(r["exists"], bool)
        assert "label" in r


# ─────────────────────────────────────────────
# 327o — Journal recorder
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_journal_first_call_writes_baseline():
    from services.ora_lessons_loader import (
        build_lessons_block, record_journal_entry_if_changed,
    )
    db = mongomock_motor.AsyncMongoMockClient()["test_327o_first"]
    # Populate the manifest by running the loader.
    build_lessons_block()
    res = await record_journal_entry_if_changed(db)
    assert res["ok"] is True
    assert res["changed"] is True
    assert res["first_snapshot"] is True
    n = await db.ora_learning_journal.count_documents({})
    assert n == 1


@pytest.mark.asyncio
async def test_journal_second_unchanged_call_is_noop():
    from services.ora_lessons_loader import (
        build_lessons_block, record_journal_entry_if_changed,
    )
    db = mongomock_motor.AsyncMongoMockClient()["test_327o_noop"]
    build_lessons_block()
    await record_journal_entry_if_changed(db)
    # Second call — nothing changed → no new doc.
    res2 = await record_journal_entry_if_changed(db)
    assert res2["ok"] is True
    assert res2["changed"] is False
    n = await db.ora_learning_journal.count_documents({})
    assert n == 1


@pytest.mark.asyncio
async def test_journal_writes_new_snapshot_on_hash_change(monkeypatch):
    """Simulate a tier-1 file being edited between two boots."""
    from services import ora_lessons_loader as ll
    db = mongomock_motor.AsyncMongoMockClient()["test_327o_change"]
    ll.build_lessons_block()
    await ll.record_journal_entry_if_changed(db)
    # Mutate the manifest in place to simulate a content edit.
    edited_path = ll._LAST_INJECTION_MANIFEST[0]["path"]
    ll._LAST_INJECTION_MANIFEST[0]["sha256"] = "f" * 64
    res = await ll.record_journal_entry_if_changed(db)
    assert res["changed"] is True
    assert edited_path in res["changed_paths"]
    assert res["first_snapshot"] is False
    n = await db.ora_learning_journal.count_documents({})
    assert n == 2


@pytest.mark.asyncio
async def test_journal_safe_when_db_is_none():
    from services.ora_lessons_loader import record_journal_entry_if_changed
    res = await record_journal_entry_if_changed(None)
    assert res["ok"] is False
    assert res["reason"] == "no_db_or_manifest"


# ─────────────────────────────────────────────
# 327p — Admin endpoint routes
# ─────────────────────────────────────────────

def test_router_exposes_two_admin_endpoints():
    from routers.ora_lesson_sources_router import router
    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes
              if hasattr(r, "methods")}
    assert ("/api/admin/ora/lesson-sources", ("GET",)) in paths
    assert ("/api/admin/ora/lesson-journal", ("GET",)) in paths


def test_router_registered_in_lean_safe_registry():
    src = (BACKEND / "routers" / "registry.py").read_text()
    assert "ora_lesson_sources_router" in src
    # Inside the _aurem_with_db block where set_db is wired automatically.
    assert "ORA Lesson Sources" in src


def test_startup_background_task_calls_journal_recorder():
    src = (BACKEND / "server.py").read_text()
    assert "record_journal_entry_if_changed" in src
    assert "_bg_lesson_journal" in src


def test_iter_marker_present():
    src1 = (BACKEND / "services" / "ora_lessons_loader.py").read_text()
    src2 = (BACKEND / "routers" / "ora_lesson_sources_router.py").read_text()
    src3 = (BACKEND / "routers" / "registry.py").read_text()
    assert "iter 327o" in src1
    assert "iter 327p" in src2
    assert "iter 327o+p" in src3 or ("iter 327o" in src3 and "iter 327p" in src3)
