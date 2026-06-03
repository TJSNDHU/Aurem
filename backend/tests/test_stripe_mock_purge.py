"""
Step 1 of P0 mock purge — TOONStripeService must no longer have any
mock_mode pathway. Live STRIPE_SECRET_KEY required; missing/placeholder
must raise RuntimeError.
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _reload_module(modname: str):
    if modname in sys.modules:
        del sys.modules[modname]
    return importlib.import_module(modname)


# ── Source-level invariants ────────────────────────────────────────

def test_toon_stripe_service_has_no_mock_mode_text():
    src = _read(os.path.join(ROOT, "services", "toon_stripe_service.py"))
    for token in ("mock_mode", "mock_prod_", "mock_price_",
                    "mock_cs_", "mock_session"):
        assert token not in src, f"forbidden token still present: {token}"


def test_subscription_router_has_no_mock_branch():
    src = _read(os.path.join(ROOT, "routers", "subscription_router.py"))
    for token in ("is_mock", "mock_mode", '"mock": True'):
        assert token not in src, (
            f"subscription_router still contains mock branch: {token}"
        )


def test_subscription_public_router_returns_no_mock_mode():
    src = _read(os.path.join(ROOT, "routers", "subscription_public_router.py"))
    assert "mock_mode" not in src
    assert 'result.get("mock_mode"' not in src


# ── Runtime behaviour ──────────────────────────────────────────────

def test_constructor_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    svc_mod = _reload_module("services.toon_stripe_service")
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        svc_mod.TOONStripeService(db=object())


def test_constructor_raises_on_placeholder_key(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_emergent")
    svc_mod = _reload_module("services.toon_stripe_service")
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        svc_mod.TOONStripeService(db=object())


def test_constructor_initialises_with_live_key(monkeypatch):
    # Use a fake-but-non-placeholder key so init succeeds without
    # actually calling Stripe.
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_test_dummy_for_unit")
    svc_mod = _reload_module("services.toon_stripe_service")
    inst = svc_mod.TOONStripeService(db=object())
    assert not hasattr(inst, "mock_mode")    # attribute removed entirely
    import stripe
    assert stripe.api_key == "sk_live_test_dummy_for_unit"
