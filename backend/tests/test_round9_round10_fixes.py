"""Regression tests for Round 9 + Round 10 security bug fixes (74–89) +
Ghost Scout query rotation (P0).

Bugs covered:
  74  SOC2 kill-switch — email-only JWT must NOT be admin
  75  aurem-billing portal/checkout/customers/status — require JWT match
  76  Stripe webhook — reject without signature unless explicit dev opt-in
  77  panic_takeover_router — require real JWT, no silent platform fallback
  78  subscription_public sync-stripe — require admin auth (file-level)
  79  soc2_compliance — _jwt_secret initialised from env at module load
  80  ora_tools env — REDIS/DATABASE/DB_/CAPSOLVER/IPROYAL redacted
  81  aurem-billing webhook — sync Stripe call wrapped in asyncio.to_thread
  83  owner_panel — no default OWNER_PANEL_TOKEN; fail closed if unset
  84  ssot_admin_router — remove `or payload.get("email")` admin bypass
  85  a2a-learning /message /daily-learning /skills/upgrade — require admin
  86  github_deploy push_fix — repo must be in tenant's authorized list
  87  morning_brief /tasks POST/DELETE — require JWT + business_id match
  88  cart endpoints — bound carts require auth match user_id
  89  bin_service — counts scoped to tenant_id

  P0  Ghost Scout — dedup-park after 3 zero-insert cycles + rotation queue
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


# ─── Bug 74 + 79 ────────────────────────────────────────────────────
def test_bug74_soc2_no_email_only_admin_bypass():
    """soc2._require_admin must not accept a JWT that only has `email`."""
    from routers import soc2_compliance_router as soc2
    src = inspect.getsource(soc2._require_admin)
    assert 'payload.get("email")' not in src, (
        "Bug 74 regression: the old email-bypass still present in _require_admin"
    )


def test_bug79_soc2_jwt_secret_initialised_from_env():
    """_jwt_secret must be set at module import (not None) so kill-switch
    routes stay reachable when set_jwt() is never called."""
    from routers import soc2_compliance_router as soc2
    # Either env-derived or set via set_jwt — must NOT be None.
    assert soc2._jwt_secret is not None
    # Most installs have JWT_SECRET set; if so it must be non-empty.
    if os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY"):
        assert soc2._jwt_secret != ""


# ─── Bug 75 + 76 + 81 ───────────────────────────────────────────────
def test_bug75_billing_portal_requires_auth():
    from routers import aurem_billing_router as br
    src = inspect.getsource(br.create_portal_session)
    assert "_verify_caller" in src, "Bug 75: /portal must call _verify_caller"


def test_bug75_billing_checkout_requires_auth():
    from routers import aurem_billing_router as br
    src = inspect.getsource(br.create_checkout)
    assert "_verify_caller" in src, "Bug 75: /checkout must call _verify_caller"


def test_bug75_billing_status_requires_auth():
    from routers import aurem_billing_router as br
    src = inspect.getsource(br.get_billing_status)
    assert "_verify_caller" in src, "Bug 75: /status must call _verify_caller"


def test_bug76_webhook_rejects_without_secret_in_prod():
    from routers import aurem_billing_router as br
    src = inspect.getsource(br.stripe_webhook)
    assert "AUREM_ALLOW_UNVERIFIED_WEBHOOK" in src, (
        "Bug 76: webhook must require explicit dev opt-in to skip sig check"
    )
    assert "Webhook signature verification required" in src


def test_bug81_billing_webhook_no_sync_stripe_in_async():
    """The webhook handler must wrap sync stripe calls with asyncio.to_thread."""
    from routers import aurem_billing_router as br
    src = inspect.getsource(br.stripe_webhook)
    # No bare `_stripe.Customer.retrieve(` calls — must be wrapped
    bare_calls = src.count("_stripe.Customer.retrieve(customer_id)")
    wrapped = src.count("asyncio.to_thread(_stripe.Customer.retrieve")
    assert bare_calls == 0, "Bug 81: sync stripe call still present in async webhook"
    assert wrapped >= 2, "Bug 81: must wrap each stripe.Customer.retrieve call"


# ─── Bug 77 ─────────────────────────────────────────────────────────
def test_bug77_panic_uses_real_auth_not_silent_fallback():
    from routers import panic_takeover_router as pt
    src = inspect.getsource(pt)
    assert "_require_tenant" in src, "Bug 77: panic must use _require_tenant"
    # Every route uses Depends(_require_tenant), not Depends(current_tenant)
    take_src = inspect.getsource(pt.take_control)
    send_src = inspect.getsource(pt.send_manual_message)
    assert "Depends(_require_tenant)" in take_src
    assert "Depends(_require_tenant)" in send_src


# ─── Bug 78 ─────────────────────────────────────────────────────────
def test_bug78_sync_stripe_requires_admin():
    from routers import subscription_public_router as sp
    src = inspect.getsource(sp.sync_plans_to_stripe)
    assert "verify_admin" in src, "Bug 78: sync-stripe must call verify_admin"


# ─── Bug 80 ─────────────────────────────────────────────────────────
def test_bug80_env_tool_redacts_redis_and_database():
    from services import ora_tools
    src = inspect.getsource(ora_tools._redact_env)
    # The SENSITIVE tuple must include explicit REDIS/DATABASE/DB_ guards
    assert '"REDIS"' in src and '"DATABASE"' in src and '"DB_"' in src
    assert '"CAPSOLVER"' in src and '"IPROYAL"' in src
    # Functional check: REDIS_URL must be redacted
    out = ora_tools._redact_env("REDIS_URL=redis://:password@host:6379\nFOO=bar")
    assert "<redacted>" in out
    assert "password@host" not in out


# ─── Bug 83 ─────────────────────────────────────────────────────────
def test_bug83_owner_panel_no_default_token():
    """OWNER_PANEL_TOKEN must not have a hardcoded default; verifier must
    fail closed if unset."""
    from routers import owner_panel_router as op
    # The runtime OWNER_TOKEN must come strictly from env (no hardcoded fallback)
    token_src = inspect.getsource(op).split("OWNER_TOKEN = ")[1].split("\n")[0]
    assert "owner_secret_token_change_me" not in token_src, (
        "Bug 83: hardcoded default token in OWNER_TOKEN assignment"
    )
    # verifier must fail closed
    verify_src = inspect.getsource(op.verify_owner_token)
    assert "503" in verify_src or "disabled" in verify_src.lower(), (
        "Bug 83: must reject when env unset (fail-closed message)"
    )


# ─── Bug 84 ─────────────────────────────────────────────────────────
def test_bug84_ssot_no_email_admin_bypass():
    from routers import ssot_admin_router as ssot
    src = inspect.getsource(ssot._verify_admin)
    # The active check must require explicit admin claims; the old
    # `or payload.get("email")` truthy-bypass must be gone from the
    # active condition. We assert the new is_admin_email path is wired.
    assert "is_admin_email" in src, (
        "Bug 84: must check ADMIN_EMAIL_WHITELIST instead of any email"
    )
    # No active line with the bypass — only references in comments are OK.
    code_lines = [l for l in src.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    code_body = "\n".join(code_lines)
    assert 'or payload.get("email")' not in code_body, (
        "Bug 84: email-only admin bypass still present in active code"
    )


# ─── Bug 85 ─────────────────────────────────────────────────────────
def test_bug85_a2a_endpoints_require_admin():
    from routers import a2a_learning_router as a2a
    for fn in (a2a.send_agent_message, a2a.trigger_daily_learning, a2a.manual_skill_upgrade):
        src = inspect.getsource(fn)
        assert "_require_admin_a2a" in src, f"Bug 85: {fn.__name__} missing auth"


# ─── Bug 86 ─────────────────────────────────────────────────────────
def test_bug86_github_push_fix_validates_repo_authorization():
    from services import github_deploy_service as g
    src = inspect.getsource(g.push_fix)
    assert "_is_repo_authorized" in src, (
        "Bug 86: push_fix must verify repo is authorized for tenant"
    )


# ─── Bug 87 ─────────────────────────────────────────────────────────
def test_bug87_tasks_endpoints_require_business_owner():
    from routers import morning_brief_router as mb
    for fn in (mb.create_task, mb.complete_task):
        src = inspect.getsource(fn)
        assert "_require_business_owner" in src, (
            f"Bug 87: {fn.__name__} must call _require_business_owner"
        )


# ─── Bug 88 ─────────────────────────────────────────────────────────
def test_bug88_cart_endpoints_enforce_owner():
    from routes import orders as o
    for fn in (o.add_to_cart, o.update_cart_item, o.remove_from_cart, o.clear_cart):
        src = inspect.getsource(fn)
        assert "_enforce_cart_owner" in src, (
            f"Bug 88: {fn.__name__} must call _enforce_cart_owner"
        )


# ─── Bug 89 ─────────────────────────────────────────────────────────
def test_bug89_bin_service_scopes_by_tenant():
    from services import bin_service
    src = inspect.getsource(bin_service.get_bin_data)
    # Counts must use the tenant filter, not bare empty filter
    assert "t_filter" in src
    # The old unscoped count_documents calls must be gone
    assert 'count_documents({"status": {"$in":' not in src
    assert 'count_documents({\n        "sent_at"' not in src


# ─── P0 — Ghost Scout dedup-park rotation ───────────────────────────
def test_p0_ghost_scout_park_after_zero_streak():
    """After PARK_AFTER_ZERO_CYCLES consecutive zero inserts on the same
    (q,loc,ctry), the entry must be parked."""
    from services import ghost_scout_iproyal as gs
    key = gs._entry_key("roofing contractor", "Toronto", "ca")
    # Reset any previous state for this key
    gs._QUEUE_STATS.pop(key, None)
    threshold = gs._PARK_AFTER_ZERO_CYCLES
    for _ in range(threshold):
        gs._record_cycle(key, 0)
    assert gs._is_parked(key), "Park did not trip after threshold zero cycles"


def test_p0_ghost_scout_unpark_after_insertion():
    """A non-zero insertion must reset the zero streak."""
    from services import ghost_scout_iproyal as gs
    key = gs._entry_key("plumber", "Mississauga", "ca")
    gs._QUEUE_STATS.pop(key, None)
    gs._record_cycle(key, 0)
    gs._record_cycle(key, 0)
    gs._record_cycle(key, 5)  # fresh leads → reset
    assert gs._QUEUE_STATS[key]["zero_streak"] == 0
    assert not gs._is_parked(key)


def test_p0_ghost_scout_queue_health_endpoint_data():
    """get_queue_health must return per-entry telemetry."""
    from services import ghost_scout_iproyal as gs
    h = gs.get_queue_health()
    assert "queue_len" in h
    assert h["queue_len"] >= 20  # we expanded to 30+ verticals
    assert "park_threshold_cycles" in h
    assert any(e["query"] for e in h["entries"])


def test_p0_ghost_scout_queue_expanded_for_rotation():
    """Queue must have meaningful breadth — the bug was 8 entries spinning
    on dups. Now we expect a much wider rotation."""
    from services import ghost_scout_iproyal as gs
    assert len(gs.HARVEST_QUEUE) >= 20, "Queue too small to escape dedup-spin"
    # Multiple verticals
    verticals = {q for q, _, _ in gs.HARVEST_QUEUE}
    assert len(verticals) >= 8


def test_p0_next_unparked_skips_parked_entries():
    from services import ghost_scout_iproyal as gs
    # Park the first three entries
    for q, loc, ctry in gs.HARVEST_QUEUE[:3]:
        key = gs._entry_key(q, loc, ctry)
        gs._QUEUE_STATS[key] = {
            "zero_streak": gs._PARK_AFTER_ZERO_CYCLES,
            "parked_until": 9_999_999_999,
            "total_inserted": 0, "total_runs": 3,
        }
    idx = gs._next_unparked_index(0)
    assert idx is not None and idx >= 3, (
        f"_next_unparked_index returned a parked slot: {idx}"
    )
    # Cleanup
    for q, loc, ctry in gs.HARVEST_QUEUE[:3]:
        gs._QUEUE_STATS.pop(gs._entry_key(q, loc, ctry), None)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])
