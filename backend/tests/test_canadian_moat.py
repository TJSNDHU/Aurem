"""Canadian Moat + Value-First tests — iter 282al-7.

Validates:
  • get_value_hook returns the right hook per situation × channel × step
  • CANADIAN_TRUST_SIGNALS exposes the strings the frontend uses
  • EMAIL_FOOTER / SMS_FOOTER include the legally-required address + opt-out
  • casl_check_message catches deceptive subjects + missing opt-out
  • compose_outreach (fallback path) emits Canadian-spelling, value-first copy

LLM-dependent assertions are skipped via fallback path so these tests run
even when the gateway is offline / Emergent key is exhausted.
"""
from __future__ import annotations

import asyncio
import os

import pytest

# Make sure no LLM key is set so we deterministically hit the fallback
# branch (which is what we want to assert against).
os.environ["EMERGENT_LLM_KEY"] = ""

from services.outreach_composer import (  # noqa: E402
    EMAIL_FOOTER,
    SMS_FOOTER,
    casl_check_message,
    compose_outreach,
)
from services.value_first_hooks import (  # noqa: E402
    CANADIAN_TRUST_SIGNALS,
    VALUE_HOOKS,
    get_value_hook,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── value hook routing ───────────────────────────────────────────────
def test_value_hook_no_website_lead():
    hook = get_value_hook(
        {"has_website": False, "city": "Mississauga", "category": "plumber"},
        "email", 1,
    )
    assert "value_offer" in hook
    assert hook["value_offer"] != ""


def test_value_hook_bad_website_lead():
    hook = get_value_hook(
        {"has_website": True, "city": "Toronto", "category": "hvac"},
        "email", 1,
    )
    assert hook["value_offer"]
    # bad_website hook references a free scan / report
    blob = (hook["value_offer"] + " " + hook["cta"]).lower()
    assert "scan" in blob or "report" in blob or "audit" in blob


def test_value_hook_unlinked_mentions_priority():
    hook = get_value_hook(
        {"has_website": True, "unlinked_mentions_count": 7,
         "city": "Mississauga", "category": "plumber"},
        "email", 1,
    )
    assert "{count}" in hook["value_offer"]


def test_value_hook_step3_is_soft():
    hook = get_value_hook(
        {"has_website": False, "city": "Toronto", "category": "plumber"},
        "email", 3,
    )
    cta = hook.get("cta", "").lower()
    assert ("no hard feelings" in cta or "no pressure" in cta
            or "either way" in cta)


def test_value_hook_step2_is_followup():
    hook = get_value_hook(
        {"has_website": False, "city": "Toronto", "category": "plumber"},
        "email", 2,
    )
    blob = (hook["value_offer"] + " " + hook["cta"]).lower()
    assert "follow" in blob or "still" in blob or "last week" in blob


def test_value_hook_all_channels_defined():
    for situation, channels in VALUE_HOOKS.items():
        for ch in ("email", "sms", "whatsapp", "linkedin"):
            assert ch in channels, \
                f"VALUE_HOOKS[{situation}] missing channel {ch}"


# ── trust signals ────────────────────────────────────────────────────
def test_trust_bar_content_defined():
    blob = str(CANADIAN_TRUST_SIGNALS)
    assert "Canadian-Owned" in blob
    assert "Mississauga" in blob
    assert "CASL" in blob


def test_trust_bar_has_5_signals():
    assert len(CANADIAN_TRUST_SIGNALS) == 5
    for s in CANADIAN_TRUST_SIGNALS:
        assert "icon" in s and "label" in s


# ── footers (legal floor) ────────────────────────────────────────────
def test_email_footer_has_address():
    assert "Mississauga" in EMAIL_FOOTER
    assert "STOP" in EMAIL_FOOTER
    assert "AUREM" in EMAIL_FOOTER


def test_email_footer_has_postal_address():
    # Full street address required by CASL.
    assert "7221 Sigsbee" in EMAIL_FOOTER
    assert "L4T 3L6" in EMAIL_FOOTER


def test_sms_footer_has_optout():
    assert "STOP" in SMS_FOOTER
    assert "AUREM" in SMS_FOOTER


# ── casl_check_message ──────────────────────────────────────────────
def test_casl_check_pass_email():
    body = (
        "Hi, we noticed your business — built a free preview for you. "
        "Worth a 30-second look?\n\n" + EMAIL_FOOTER
    )
    audit = casl_check_message("email", "Found something about Mike's", body)
    assert audit["passed"] is True
    assert audit["fail_reason"] is None


def test_casl_check_fails_on_no_optout():
    body = "Hi, free preview built for you. AUREM, Mississauga ON."
    audit = casl_check_message("email", "Quick note", body)
    assert audit["passed"] is False
    assert "has_optout" in (audit["fail_reason"] or "")


def test_casl_check_fails_on_deceptive_subject():
    body = "Hi, free report ready. Reply STOP to opt out. AUREM Mississauga ON."
    audit = casl_check_message("email", "Re: your invoice", body)
    assert audit["passed"] is False
    assert "no_deceptive_subject" in (audit["fail_reason"] or "")


def test_casl_check_fails_on_hard_cta():
    body = (
        "Free report. Buy now to save 50%. Reply STOP to opt out. "
        "AUREM Mississauga ON."
    )
    audit = casl_check_message("email", "Quick note", body)
    assert audit["passed"] is False


def test_casl_check_sms_relaxed_address():
    # SMS doesn't need full address (length budget).
    body = "Free site scan ready: aurem.live/r/x. Reply STOP. AUREM."
    audit = casl_check_message("sms", None, body)
    assert audit["passed"] is True


# ── compose_outreach (fallback path) ─────────────────────────────────
def test_email_footer_used_in_fallback_compose():
    lead = {"business_name": "Mike's Plumbing", "city": "Mississauga",
             "category": "plumber", "lead_id": "test-1",
             "has_website": False}
    result = _run(compose_outreach(lead, "email", 1))
    body = result["body"].lower()
    assert "mississauga" in body
    assert "stop" in body
    assert "aurem" in body


def test_canadian_spelling_in_fallback():
    lead = {"business_name": "Mike's Plumbing", "city": "Mississauga",
             "category": "plumber", "lead_id": "test-2",
             "has_website": False}
    result = _run(compose_outreach(lead, "email", 1))
    body = result["body"].lower()
    # American spellings should not appear
    assert "neighbor" not in body
    # Avoid "color " / "center " (with space) so we don't trigger on
    # legitimate words; only catch standalone US spellings.
    assert " color " not in body
    assert " center " not in body


def test_no_hard_sales_cta_in_fallback():
    lead = {"business_name": "Mike's Plumbing", "city": "Mississauga",
             "category": "plumber", "lead_id": "test-3"}
    for channel in ("email", "sms", "whatsapp", "linkedin"):
        result = _run(compose_outreach(lead, channel, 1))
        body = result["body"].lower()
        assert "buy now" not in body
        assert "sign up today" not in body


def test_compose_emits_casl_audit_field():
    lead = {"business_name": "Mike's Plumbing", "city": "Mississauga",
             "category": "plumber", "lead_id": "test-4",
             "has_website": False}
    result = _run(compose_outreach(lead, "email", 1))
    assert "casl_passed" in result
    # Fallback path should be value-first compliant on email.
    assert result["casl_passed"] is True


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_compose_short_channels_have_optout(channel):
    lead = {"business_name": "Mike's Plumbing", "city": "Mississauga",
             "category": "plumber", "lead_id": f"test-{channel}",
             "has_website": False}
    result = _run(compose_outreach(lead, channel, 1))
    body = result["body"].lower()
    assert "stop" in body
    assert "aurem" in body
