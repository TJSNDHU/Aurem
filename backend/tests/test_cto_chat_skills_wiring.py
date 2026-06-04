"""Skills wiring into dev_cto_chat — parser + manifest block."""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_helpers_exist():
    from services import dev_cto_chat
    assert hasattr(dev_cto_chat, "_build_skills_block")
    assert hasattr(dev_cto_chat, "_maybe_invoke_skill")


def test_skills_block_renders_manifest():
    from services.dev_cto_chat import _build_skills_block
    from cto_skills import manifest
    block = _build_skills_block(manifest())
    assert "AVAILABLE SKILLS" in block
    assert "[[SKILL:" in block
    assert "apollo_lead_search" in block
    assert "read_codebase" in block


def test_block_empty_for_empty_manifest():
    from services.dev_cto_chat import _build_skills_block
    assert _build_skills_block([]) == ""


def test_parser_returns_none_when_no_marker():
    from services.dev_cto_chat import _maybe_invoke_skill
    res = asyncio.run(_maybe_invoke_skill("just a plain reply"))
    assert res is None


def test_parser_catches_marker_and_runs_real_skill():
    from services.dev_cto_chat import _maybe_invoke_skill
    reply = ('Sure, listing files now. '
              '[[SKILL: read_codebase {"path": "/app/backend/cto_skills"}]]')
    res = asyncio.run(_maybe_invoke_skill(reply))
    assert res is not None
    assert res["ok"] is True
    assert res["skill"] == "read_codebase"
    assert res["result"]["file_count"] > 0


def test_parser_rejects_bad_json():
    from services.dev_cto_chat import _maybe_invoke_skill
    reply = '[[SKILL: read_codebase {not-json}]]'
    res = asyncio.run(_maybe_invoke_skill(reply))
    assert res["ok"] is False
    assert "bad_json_args" in res["error"]


def test_parser_rejects_unknown_skill():
    from services.dev_cto_chat import _maybe_invoke_skill
    reply = '[[SKILL: nonexistent {}]]'
    res = asyncio.run(_maybe_invoke_skill(reply))
    assert res["ok"] is False
    assert res["error"] == "unknown_skill"
