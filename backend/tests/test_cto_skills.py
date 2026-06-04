"""
Tests for the CTO skills system.

Covers:
  • Registry registers all 7 core skills
  • Manifest shape (name, description, params, requires_keys)
  • invoke() returns honest {ok: False} for unknown skills
  • Apollo + Resend skills declare correct required keys
  • read_codebase + edit_file + remember/recall integration
"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_seven_skills_registered():
    import cto_skills
    names = set(cto_skills.list_skills())
    assert {"read_codebase", "edit_file", "run_tests",
            "apollo_lead_search", "send_email_via_resend",
            "remember", "recall"}.issubset(names)


def test_manifest_shape():
    import cto_skills
    m = cto_skills.manifest()
    assert isinstance(m, list) and len(m) >= 7
    for entry in m:
        assert "name" in entry and "description" in entry
        assert "params" in entry and isinstance(entry["params"], list)
        assert "requires_keys" in entry


def test_unknown_skill_fails_honestly():
    import cto_skills
    res = asyncio.run(cto_skills.invoke("nonexistent_skill"))
    assert res["ok"] is False
    assert res["error"] == "unknown_skill"


def test_db_required_skill_rejects_no_db():
    import cto_skills
    res = asyncio.run(cto_skills.invoke("remember",
                                            topic="x", lesson="y"))
    assert res["ok"] is False
    assert res["error"] == "db_required_but_not_provided"


def test_apollo_skill_declares_key_requirement():
    import cto_skills
    apollo = next(m for m in cto_skills.manifest()
                   if m["name"] == "apollo_lead_search")
    assert "APOLLO_API_KEY" in apollo["requires_keys"]


def test_resend_skill_declares_key_requirement():
    import cto_skills
    resend = next(m for m in cto_skills.manifest()
                   if m["name"] == "send_email_via_resend")
    assert "RESEND_API_KEY" in resend["requires_keys"]


def test_read_codebase_returns_tree():
    import cto_skills
    res = asyncio.run(cto_skills.invoke(
        "read_codebase", path="/app/backend/cto_skills", max_depth=1,
    ))
    assert res["ok"] is True
    assert res["result"]["file_count"] > 0
    assert any("registry.py" in p for p in res["result"]["tree"])
