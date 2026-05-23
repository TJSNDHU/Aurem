"""
iter 331a — Sprints 1+2+3 regression tests
==========================================

Covers:
  - Sprint 1: folder-driven loader, ORA_MEMORY in Tier-1, 6 new files
  - Sprint 2: 8 tools registered + each callable
  - Sprint 3: 6 guards fire correctly
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════
# Sprint 1 — Memory + Loader
# ═══════════════════════════════════════════════════════════

def test_tier1_folder_exists_with_required_files():
    t1 = Path("/app/memory/tier1")
    assert t1.is_dir()
    required = {
        "WATCHDOG_MODE.md", "WORKING_POLICY.md", "SEVEN_WAYS.md",
        "ORA_MEMORY.md",
        "DEVELOPER_CAPABILITIES.md", "CODE_STANDARDS.md", "progress.md",
    }
    present = {p.name for p in t1.iterdir() if p.suffix == ".md"}
    missing = required - present
    assert not missing, f"missing tier1 files: {missing}"


def test_tier2_folder_with_runbook_playbook_templates():
    t2 = Path("/app/memory/tier2")
    assert t2.is_dir()
    required = {
        "DEPLOYMENT_RUNBOOK.md", "INTEGRATION_PLAYBOOK.md",
        "PROJECT_TEMPLATES.md", "SYSTEM_MAP.md",
        "TIER2_TRIGGERS.json",
    }
    present = {p.name for p in t2.iterdir()}
    missing = required - present
    assert not missing, f"missing tier2 files: {missing}"


def test_tier3_folder_holds_legacy_reference_docs():
    t3 = Path("/app/memory/tier3")
    assert t3.is_dir()
    # At least 5 reference docs should have moved here
    md_count = sum(1 for p in t3.iterdir() if p.suffix == ".md")
    assert md_count >= 5, f"tier3 only has {md_count} .md files"


def test_backward_compat_symlinks_still_resolve():
    """Anything that hardcodes /app/memory/SEVEN_WAYS.md must still work."""
    for name in ("WATCHDOG_MODE.md", "WORKING_POLICY.md", "SEVEN_WAYS.md",
                 "ORA_MEMORY.md", "SYSTEM_MAP.md", "ARCHITECTURE.md"):
        p = Path("/app/memory") / name
        assert p.exists(), f"backward-compat symlink missing: {p}"
        # Must be a symlink (proves we routed, not copied)
        assert p.is_symlink(), f"{p} should be a symlink for backward-compat"


def test_loader_is_folder_driven_not_hardcoded():
    """The new loader scans tier1/ instead of a hard-coded list."""
    src = Path("/app/backend/services/ora_lessons_loader.py").read_text()
    # Marker
    assert "iter 331a" in src
    # No hard-coded `_TIER1_FILES` legacy list
    assert "_TIER1_FILES: list[tuple[str, str, int]] = [" not in src
    # The folder scanner exists
    assert "_TIER1_DIR" in src
    assert "_discover" in src


def test_loader_loads_ora_memory_into_tier1():
    """ORA_MEMORY.md must be picked up by the folder scanner now."""
    from services.ora_lessons_loader import build_lessons_block, last_injection_manifest
    block = build_lessons_block()
    assert len(block) > 0
    manifest = last_injection_manifest()
    labels = [m["label"] for m in manifest if m.get("loaded")]
    assert any("ORA MEMORY" in lbl for lbl in labels), \
        f"ORA_MEMORY.md not in tier-1 manifest. Got: {labels}"


# ═══════════════════════════════════════════════════════════
# Sprint 2 — 8 Tools
# ═══════════════════════════════════════════════════════════

def test_sprint2_module_exists():
    """Module must exist and expose all 8 functions."""
    from services import ora_sprint2_tools as S2
    for name in ("web_search", "read_logs", "check_coverage", "run_linter",
                 "mongo_query_safe", "view_bulk", "ask_human", "glob_files"):
        assert hasattr(S2, name), f"missing function: {name}"


def test_sprint2_registry_patch_has_8_entries():
    from services.ora_sprint2_tools import TOOL_REGISTRY_PATCH
    assert len(TOOL_REGISTRY_PATCH) == 8
    expected = {"web_search", "read_logs", "check_coverage", "run_linter",
                "mongo_query_safe", "view_bulk", "ask_human", "glob_files"}
    assert set(TOOL_REGISTRY_PATCH.keys()) == expected


def test_sprint2_tools_spliced_into_main_registry():
    from services.ora_tools import TOOL_REGISTRY
    for name in ("web_search", "read_logs", "check_coverage", "run_linter",
                 "mongo_query_safe", "view_bulk", "ask_human", "glob_files"):
        assert name in TOOL_REGISTRY, f"{name} not in main TOOL_REGISTRY"


def test_sprint2_tools_in_tier1_auto():
    """New tools must be Tier-1 (auto-execute) per spec."""
    from services.ora_agent import TIER_1_AUTO
    for name in ("web_search", "read_logs", "check_coverage", "run_linter",
                 "mongo_query_safe", "view_bulk", "ask_human", "glob_files"):
        assert name in TIER_1_AUTO, f"{name} not in TIER_1_AUTO"


@pytest.mark.asyncio
async def test_view_bulk_reads_real_files():
    """E2E proof: view_bulk returns real file contents."""
    from services.ora_sprint2_tools import view_bulk
    r = await view_bulk(paths=[
        "/app/memory/tier1/CODE_STANDARDS.md",
        "/app/memory/tier1/DEVELOPER_CAPABILITIES.md",
    ])
    assert r["ok"] is True
    assert r["count"] == 2
    assert all(f["exists"] for f in r["files"])
    assert all(len(f["content"]) > 100 for f in r["files"])


@pytest.mark.asyncio
async def test_glob_files_returns_real_paths():
    from services.ora_sprint2_tools import glob_files
    r = await glob_files(pattern="ora_*.py", base="/app/backend/services")
    assert r["ok"] is True
    assert r["count"] >= 5
    assert all(p.startswith("/app/backend/services/ora_") for p in r["files"])


# ═══════════════════════════════════════════════════════════
# Sprint 3 — 6 Guards
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_guard1_cost_cap_three_levels():
    from services import ora_guards as G
    G.SESSION_USD_CAP = 1.00
    G.WARN_FRACTION = 0.80
    r1 = await G.check_cost_cap("s1", 0.50);  assert r1["level"] == "ok"
    r2 = await G.check_cost_cap("s1", 0.85);  assert r2["level"] == "warn"
    r3 = await G.check_cost_cap("s1", 1.10);  assert r3["level"] == "halt"
    assert r3["ok"] is False


@pytest.mark.asyncio
async def test_guard2_edit_loop_halts_on_third_identical_edit():
    from services import ora_guards as G
    G.IDEMPOTENCY_HITS = 3
    G.reset_edit_history("sg2")
    r1 = await G.check_edit_loop("sg2", "/tmp/a.py", "x=1");  assert r1["level"] == "ok"
    r2 = await G.check_edit_loop("sg2", "/tmp/a.py", "x=1");  assert r2["level"] == "warn"
    r3 = await G.check_edit_loop("sg2", "/tmp/a.py", "x=1");  assert r3["level"] == "halt"
    G.reset_edit_history("sg2")


@pytest.mark.asyncio
async def test_guard4_destructive_block_patterns():
    from services.ora_guards import check_destructive
    safe = ["ls /app", "cd backend", "python -m pytest"]
    blocked = [
        "rm -rf /app/backend",
        "db.dropDatabase()",
        "TRUNCATE TABLE users",
        "DELETE FROM users;",
        "kubectl delete namespace prod",
        "DROP TABLE leads",
    ]
    for cmd in safe:
        r = await check_destructive(cmd)
        assert r["level"] == "ok", f"safe cmd blocked: {cmd}"
    for cmd in blocked:
        r = await check_destructive(cmd)
        assert r["level"] == "block", f"destructive cmd allowed: {cmd}"


@pytest.mark.asyncio
async def test_guard5_integration_gate_requires_search():
    from services.ora_guards import check_integration_gate
    # No prior search → block
    r = await check_integration_gate("s5", "stripe_charge",
                                       last_n_turns=[{"role": "user", "content": "go"}])
    assert r["level"] == "block"
    # With wikipedia result in history → pass
    r = await check_integration_gate("s5", "stripe_charge",
                                       last_n_turns=[
                                           {"role": "tool",
                                            "content": '{"source": "wikipedia"}'}
                                       ])
    assert r["level"] == "ok"
    # Non-vendor tools never gated
    r = await check_integration_gate("s5", "view_file",
                                       last_n_turns=[])
    assert r["level"] == "ok"


@pytest.mark.asyncio
async def test_guard6_package_verification_real_pypi():
    """Real PyPI hit — must succeed for fastapi, fail for fake name."""
    from services.ora_guards import verify_package
    r1 = await verify_package("fastapi", "pypi")
    assert r1["ok"] is True
    assert r1["latest_version"] is not None
    r2 = await verify_package("a-fake-package-xyz-99999-aurem", "pypi")
    assert r2["ok"] is False
    assert "not found" in (r2["message"] or "").lower()


def test_iter_331a_marker_in_all_three_modules():
    for path in (
        "/app/backend/services/ora_lessons_loader.py",
        "/app/backend/services/ora_sprint2_tools.py",
        "/app/backend/services/ora_guards.py",
    ):
        assert "iter 331a" in Path(path).read_text(), f"331a marker missing in {path}"
