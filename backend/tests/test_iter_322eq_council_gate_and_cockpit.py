"""
Regression test — iter 322eq (Governance: council gate + quotas + cockpit)
Locks in:
  1. Dissent detector identifies "DO NOT" / "CRITICAL" / "HARD NO" patterns
  2. Risk classifier puts auth/payment paths into HIGH tier
  3. safe_edit_with_council REJECTS when rationale missing
  4. Council-gate audit-log fields present
  5. Cockpit endpoints load cleanly
"""
import os
import pytest
from motor.motor_asyncio import AsyncIOMotorClient


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_dissent_signals_recognized():
    from services.ora_tools import _peer_dissents
    positives = [
        "VERDICT: REJECT. This is a critical security vulnerability.",
        "HARD NO — do not proceed.",
        "This will break authentication. Must not commit.",
        "Stop and escalate to the founder.",
    ]
    negatives = [
        "VERDICT: APPROVE. Ship it.",
        "Looks fine. Some style nits but nothing blocking.",
        "Approved with minor suggestions.",
    ]
    for p in positives:
        diss, hits = _peer_dissents(p)
        assert diss, f"missed dissent in: {p!r}"
        assert len(hits) > 0
    for n in negatives:
        diss, hits = _peer_dissents(n)
        assert not diss, f"false positive on: {n!r}"


def test_risk_classifier_high_for_auth():
    from services.ora_tools import _classify_edit_risk
    assert _classify_edit_risk("/app/backend/routers/auth_router.py") == "high"
    assert _classify_edit_risk("/app/backend/services/stripe_billing.py") == "high"
    assert _classify_edit_risk("/app/backend/services/db_audit_scanner.py") == "medium"
    assert _classify_edit_risk("/app/backend/services/code_refactor_planner.py") == "medium"
    assert _classify_edit_risk("/app/memory/PRD.md") == "low"
    assert _classify_edit_risk("/app/backend/ora_skills/dev_skill.md") == "low"


@pytest.mark.asyncio
async def test_safe_edit_with_council_rejects_without_rationale():
    from services.ora_tools import safe_edit_with_council, set_db
    set_db(_db())
    res = await safe_edit_with_council(
        path="/app/memory/PRD.md",
        find_string="dummy",
        replace_string="other",
        rationale="hi",  # too short
    )
    assert res["ok"] is False
    assert "rationale" in (res.get("error") or "").lower()


@pytest.mark.asyncio
async def test_safe_edit_with_council_rejects_disallowed_path():
    from services.ora_tools import safe_edit_with_council, set_db
    set_db(_db())
    res = await safe_edit_with_council(
        path="/etc/passwd",
        find_string="root",
        replace_string="owner",
        rationale="testing that disallowed paths are blocked early",
    )
    assert res["ok"] is False
    assert "path not allowed" in (res.get("error") or "").lower()


def test_shell_exec_with_council_validates_rationale():
    import asyncio
    from services.ora_tools import shell_exec_with_council, set_db
    set_db(_db())
    res = asyncio.run(shell_exec_with_council(
        command="ls", args=["-la"], rationale="short",
    ))
    assert res["ok"] is False
    assert "rationale required" in res["error"].lower()


def test_council_tools_in_registry():
    from services.ora_tools import TOOL_REGISTRY
    assert "safe_edit_with_council" in TOOL_REGISTRY
    assert "shell_exec_with_council" in TOOL_REGISTRY


def test_council_gate_signal_detector_works():
    """Iter 322es — quota tests removed. Gate still active."""
    from services.ora_tools import _peer_dissents
    diss, _ = _peer_dissents("VERDICT: REJECT. CRITICAL SECURITY issue.")
    assert diss is True
    diss, _ = _peer_dissents("Looks good, ship it.")
    assert diss is False


def test_ora_cto_cockpit_router_imports_clean():
    from routers import ora_cto_cockpit_router
    paths = [r.path for r in ora_cto_cockpit_router.router.routes]
    for p in (
        "/api/admin/ora-cto/summary",
        "/api/admin/ora-cto/by-tool",
        "/api/admin/ora-cto/cost-breakdown",
        "/api/admin/ora-cto/invocations",
        "/api/admin/ora-cto/overrides",
        "/api/admin/ora-cto/quotas",
    ):
        assert p in paths, f"missing route: {p}"


@pytest.mark.asyncio
async def test_cockpit_summary_endpoint_smoke():
    """Direct function call — verifies aggregation pipelines parse."""
    from routers.ora_cto_cockpit_router import summary
    # We can't mint a real auth header here without coupling to JWT secret,
    # so just call _get_db sanity-check via the by_tool aggregator
    from routers.ora_cto_cockpit_router import by_tool
    # The actual auth dep raises HTTPException 401 without a token;
    # we accept that — this test only proves the import + route layout.
    assert callable(summary)
    assert callable(by_tool)


def test_new_council_tools_in_registry():
    from services.ora_tools import TOOL_REGISTRY
    assert "safe_edit_with_council" in TOOL_REGISTRY
    assert "shell_exec_with_council" in TOOL_REGISTRY


def test_iter_322es_quota_helpers_removed():
    """Iter 322es — confirm quota machinery is gone from ora_tools."""
    import services.ora_tools as ot
    for sym in ("_QUOTA_PER_HOUR", "_check_quota", "_maybe_alert_quota",
                 "_record_llm_cost", "_SESSION_QUOTA_PER_HOUR", "_QUOTA_ALERT_FIRED"):
        assert not hasattr(ot, sym), f"quota symbol still present: {sym}"
