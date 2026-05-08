"""Tests for the Sovereign Boundary lint (iter 322l Day 2.1)."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lint_sovereign_boundary.py"


def test_lint_passes_on_clean_repo():
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True,
    )
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "clean" in res.stdout.lower()


def test_scan_file_detects_forbidden_import(tmp_path):
    from scripts.lint_sovereign_boundary import scan_file
    test_file = tmp_path / "ora_chat_router.py"
    test_file.write_text(
        "from fastapi import APIRouter\n"
        "from services.ora_council import convene_council\n"
        "router = APIRouter()\n",
    )
    violations = scan_file(test_file)
    assert len(violations) == 1
    line_no, kind, _ = violations[0]
    assert line_no == 2
    assert "forbidden_import:services.ora_council" in kind


def test_scan_file_ignores_comments(tmp_path):
    from scripts.lint_sovereign_boundary import scan_file
    test_file = tmp_path / "x.py"
    test_file.write_text(
        "# This file used to import services.ora_council\n"
        "# Don't reintroduce that import\n",
    )
    assert scan_file(test_file) == []


def test_scan_file_detects_forbidden_collection_access(tmp_path):
    from scripts.lint_sovereign_boundary import scan_file
    test_file = tmp_path / "x.py"
    test_file.write_text(
        "async def leak(db):\n"
        "    return await db.learnings_pending_review.find_one({})\n",
    )
    violations = scan_file(test_file)
    assert any("forbidden_collection:learnings_pending_review" in v[1]
               for v in violations)


def test_scan_file_detects_bracket_collection_access(tmp_path):
    from scripts.lint_sovereign_boundary import scan_file
    test_file = tmp_path / "x.py"
    test_file.write_text(
        "async def leak(db):\n"
        "    return await db['sovereign_watchdog_log'].find().to_list(10)\n",
    )
    violations = scan_file(test_file)
    assert any("forbidden_collection:sovereign_watchdog_log" in v[1]
               for v in violations)
