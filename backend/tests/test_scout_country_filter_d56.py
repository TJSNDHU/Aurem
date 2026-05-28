"""
tests/test_scout_country_filter_d56.py — iter D-56

Validates the new junk-email + CA phone enforcement in
`ghost_scout_iproyal.py`. Pure offline.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── Email validation ────────────────────────────────────────────────

def test_rejects_placeholder_emails():
    from services.ghost_scout_iproyal import _is_valid_email
    for junk in ["user@domain.com", "yourname@example.com",
                  "YourPayPalEmail@domain.com", "yourcompany@domain.com",
                  "info@info.com", "test@test.com",
                  "name@example.org", "user@user.com"]:
        assert _is_valid_email(junk) is False, f"should reject {junk}"


def test_accepts_real_emails():
    from services.ghost_scout_iproyal import _is_valid_email
    for ok in ["hello@hamilton-salon.ca", "bookings@spa.io",
                "contact@beautystudio.com"]:
        assert _is_valid_email(ok) is True, f"should accept {ok}"


# ── CA phone enforcement ─────────────────────────────────────────────

def test_ca_phone_filter_rejects_vermont():
    from services.ghost_scout_iproyal import _phone_matches_country
    # Burlington VT area code +1802 must be rejected when country=ca
    assert _phone_matches_country("+18028626762", "ca") is False
    assert _phone_matches_country("+18028645911", "ca") is False


def test_ca_phone_filter_accepts_ontario_area_codes():
    from services.ghost_scout_iproyal import _phone_matches_country
    # Hamilton/Burlington ON (+1905), Toronto (+1416/647), GTA (+1289/365/437)
    for p in ["+19058444443", "+14165551111", "+16472223333",
                "+12895554444", "+13654446666"]:
        assert _phone_matches_country(p, "ca") is True, f"should accept {p}"


def test_ca_phone_filter_accepts_quebec_bc_ab():
    from services.ghost_scout_iproyal import _phone_matches_country
    assert _phone_matches_country("+15145551234", "ca") is True   # Montreal
    assert _phone_matches_country("+16045552222", "ca") is True   # Vancouver
    assert _phone_matches_country("+14035553333", "ca") is True   # Calgary


def test_ca_phone_filter_rejects_garbage_format():
    from services.ghost_scout_iproyal import _phone_matches_country
    assert _phone_matches_country("",            "ca") is True   # no phone = no contradiction
    assert _phone_matches_country("12345",        "ca") is False
    assert _phone_matches_country("+447700900123", "ca") is False  # UK


def test_us_filter_is_permissive():
    """country='us' currently allows anything NANP-shaped."""
    from services.ghost_scout_iproyal import _phone_matches_country
    assert _phone_matches_country("+18028626762", "us") is True
    assert _phone_matches_country("+19058444443", "us") is True


# ── End-to-end style: junk email + bad phone short-circuits insert ───

def test_lead_with_only_junk_email_and_us_phone_is_unreachable_when_ca():
    """A lead with junk email AND a US-only phone, scoped to CA, has
    nothing left to contact. The scout MUST skip it.

    This is the smoke test for the founder's "fake sent=20" bug.
    """
    from services.ghost_scout_iproyal import (
        _is_valid_email, _phone_matches_country, _normalize_phone,
    )
    raw_email = "YourPayPalEmail@domain.com"
    raw_phone = "+18028626762"        # Burlington, Vermont
    email = raw_email if _is_valid_email(raw_email) else ""
    phone = _normalize_phone(raw_phone)
    if not _phone_matches_country(phone, "ca"):
        phone = ""
    assert email == ""
    assert phone == ""
    # → outer scout would `continue` and never insert this lead
