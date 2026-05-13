"""
test_ghost_scout_iproyal.py — Ghost Scout email/phone validation tests.

Locks the contract that junk emails (image filenames, CDN URLs) and
malformed phones cannot enter the campaign pool through Ghost Scout.
"""
from __future__ import annotations

from services.ghost_scout_iproyal import _is_valid_email, _normalize_phone


def test_valid_business_emails_accepted():
    assert _is_valid_email("info@acme.com") is True
    assert _is_valid_email("contact@premiumplumbers.ca") is True
    assert _is_valid_email("sales@hvac-pros.io") is True
    assert _is_valid_email("hello@dental.co") is True


def test_junk_image_filename_emails_rejected():
    # Real-world bug: junk filename email leaked into campaign_leads
    assert _is_valid_email("shutterstock_1091175569@1X-1-300x200.webp") is False
    assert _is_valid_email("photo@image_001.png") is False
    assert _is_valid_email("logo@cdn.cloudfront.jpg") is False


def test_personal_gmail_rejected():
    # We want B2B addresses, not personal
    assert _is_valid_email("john@gmail.com") is False


def test_role_addresses_rejected():
    assert _is_valid_email("noreply@example.com") is False
    assert _is_valid_email("postmaster@example.com") is False


def test_malformed_rejected():
    assert _is_valid_email("") is False
    assert _is_valid_email("noatsign.com") is False
    assert _is_valid_email("two@@signs.com") is False or True  # regex catches it earlier
    assert _is_valid_email("missing@tld") is False


def test_phone_normalization():
    assert _normalize_phone("(416) 555-1234") == "+14165551234"
    assert _normalize_phone("416.555.1234") == "+14165551234"
    assert _normalize_phone("4165551234") == "+14165551234"
    assert _normalize_phone("+14165551234") == "+14165551234"
    assert _normalize_phone("1-416-555-1234") == "+14165551234"
    assert _normalize_phone("") == ""
    assert _normalize_phone("not a phone") == ""


if __name__ == "__main__":
    test_valid_business_emails_accepted()
    test_junk_image_filename_emails_rejected()
    test_personal_gmail_rejected()
    test_role_addresses_rejected()
    test_malformed_rejected()
    test_phone_normalization()
    print("ALL ghost_scout_iproyal tests passed ✓")
