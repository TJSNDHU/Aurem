"""
iter 326qq — council_consult invalid-role graceful fallback
============================================================

Bug: when ORA's driver LLM invented role slugs that aren't in
`_LLM_PEER_PROFILES` (e.g. "legal", "compliance" for a CASL prompt),
council_consult filtered to an empty list and returned
`{"ok": False, "error": "no valid roles after filter"}`. Two such
consecutive failures tripped ORA's fail-ceiling and halted the loop
with "Stopping auto-recovery — founder se discuss kar lo."

Fix:
  1. Tool schema now explicitly lists the 8 valid role slugs AND
     names common invalid ones to avoid ("legal", "compliance",
     "lawyer", "casl_expert"). Surfaces the whitelist to the LLM.
  2. Runtime: when all provided roles filter out, fall back to the
     safe default `["security","backend","qa"]` and attach an
     `invalid_roles_ignored` field + plain-English `note` so the
     LLM can self-correct on the next call.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────
# Schema-level: tool spec now surfaces the whitelist
# ─────────────────────────────────────────────────

def test_council_consult_schema_lists_valid_role_slugs():
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    # Locate the council_consult entry in _TOOL_REGISTRY
    assert '"council_consult": {' in src
    # The roles description must enumerate the whitelist so the
    # driver LLM sees it.
    idx = src.index('"council_consult": {')
    block = src[idx:idx + 1500]
    for slug in ("security", "backend", "devops", "qa", "design",
                 "finance", "marketing", "pricing"):
        assert f"'{slug}'" in block, f"slug {slug} missing from schema"
    # And the common-mistake slugs must be explicitly called out as invalid
    assert "legal" in block.lower()
    assert "compliance" in block.lower()


def test_safe_edit_with_council_schema_also_lists_whitelist():
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    idx = src.index('"safe_edit_with_council": {')
    block = src[idx:idx + 1800]
    assert "whitelist" in block.lower()
    assert "'security'" in block
    assert "'backend'" in block


# ─────────────────────────────────────────────────
# Runtime: graceful fallback instead of ok=False
# ─────────────────────────────────────────────────

def _stub_peer_review(success: bool = True):
    """Patch peer_review so we don't burn LLM tokens in the test."""
    async def fake(role, question, context=""):
        return {
            "ok":         success,
            "role":       role,
            "provider":   "test-stub",
            "opinion":    f"[stub] opinion from {role}",
            "elapsed_ms": 1,
        }
    return fake


def test_invalid_roles_fall_back_to_safe_default():
    """All invalid → default trio used, ok=True (not False)."""
    from services import ora_tools as ot
    fake = _stub_peer_review(True)
    with patch.object(ot, "peer_review", side_effect=fake):
        r = asyncio.run(ot.council_consult(
            "CASL question",
            roles=["legal", "compliance", "lawyer"],
        ))
    assert r["ok"] is True
    assert set(r["consulted"]) == {"security", "backend", "qa"}
    assert r.get("invalid_roles_ignored") == ["legal", "compliance", "lawyer"]
    assert "Valid slugs" in r.get("note", "")
    # Each default peer returned 1 opinion
    assert len(r["opinions"]) == 3


def test_mix_of_valid_and_invalid_keeps_valid_drops_invalid():
    from services import ora_tools as ot
    fake = _stub_peer_review(True)
    with patch.object(ot, "peer_review", side_effect=fake):
        r = asyncio.run(ot.council_consult(
            "Question",
            roles=["legal", "security", "backend"],
        ))
    assert r["ok"] is True
    assert set(r["consulted"]) == {"security", "backend"}
    assert r.get("invalid_roles_ignored") == ["legal"]
    assert "Ignored invalid role(s): ['legal']" in r.get("note", "")


def test_all_valid_roles_no_note_attached():
    from services import ora_tools as ot
    fake = _stub_peer_review(True)
    with patch.object(ot, "peer_review", side_effect=fake):
        r = asyncio.run(ot.council_consult(
            "Question",
            roles=["security", "backend", "qa"],
        ))
    assert r["ok"] is True
    assert r["consulted"] == ["security", "backend", "qa"]
    # No invalid roles → no remediation note
    assert "invalid_roles_ignored" not in r
    assert "note" not in r


def test_empty_roles_uses_default_trio():
    from services import ora_tools as ot
    fake = _stub_peer_review(True)
    with patch.object(ot, "peer_review", side_effect=fake):
        r = asyncio.run(ot.council_consult("Question", roles=None))
    assert r["ok"] is True
    assert r["consulted"] == ["security", "backend", "qa"]
    assert "invalid_roles_ignored" not in r


def test_max_5_peers_still_enforced():
    from services import ora_tools as ot
    fake = _stub_peer_review(True)
    with patch.object(ot, "peer_review", side_effect=fake):
        r = asyncio.run(ot.council_consult(
            "Question",
            roles=["security", "backend", "devops", "qa", "design", "finance"],
        ))
    assert r["ok"] is False
    assert "max 5 peers" in r.get("error", "")


def test_iter_326qq_marker_present():
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    assert "326qq" in src
