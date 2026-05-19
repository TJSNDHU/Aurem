"""Regression tests for services.recipient_guard.

Ensures:
- @aurem.live recipients are blocked (except ora@aurem.live)
- Other domains pass through
- Address normalization handles "Name <email>" format
- resend.Emails.send monkey-patch returns a blocked sentinel when all-blocked
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.recipient_guard import (
    is_blocked_recipient,
    filter_recipients,
    install_recipient_guard,
)


def test_blocks_internal_aurem_addresses():
    assert is_blocked_recipient("qa-bot@aurem.live") is True
    assert is_blocked_recipient("admin@aurem.live") is True
    assert is_blocked_recipient("info@aurem.live") is True
    assert is_blocked_recipient("anything@aurem.live") is True


def test_allows_ora_inbox():
    assert is_blocked_recipient("ora@aurem.live") is False
    assert is_blocked_recipient("ORA@aurem.live") is False  # case-insensitive


def test_allows_external_domains():
    assert is_blocked_recipient("user@example.com") is False
    assert is_blocked_recipient("info@duralscleaning.ca") is False
    assert is_blocked_recipient("info@scrubly.ca") is False


def test_handles_name_email_format():
    assert is_blocked_recipient("ORA <ora@aurem.live>") is False
    assert is_blocked_recipient("QA Bot <qa-bot@aurem.live>") is True
    assert is_blocked_recipient("Admin <admin@aurem.live>") is True


def test_handles_empty_or_invalid():
    assert is_blocked_recipient("") is False
    assert is_blocked_recipient(None) is False  # type: ignore
    assert is_blocked_recipient("not-an-email") is False


def test_filter_recipients_drops_blocked():
    result = filter_recipients(
        ["qa-bot@aurem.live", "real@user.com", "ora@aurem.live", "info@aurem.live"]
    )
    assert result == ["real@user.com", "ora@aurem.live"]


def test_filter_recipients_handles_single_string():
    assert filter_recipients("qa-bot@aurem.live") == []
    assert filter_recipients("real@user.com") == ["real@user.com"]


def test_install_recipient_guard_idempotent():
    ok1 = install_recipient_guard()
    ok2 = install_recipient_guard()
    assert ok1 is True
    assert ok2 is True


def test_resend_send_blocked_for_internal():
    install_recipient_guard()
    import resend

    # Use stub key — guard short-circuits before SDK call when all blocked.
    resend.api_key = ""
    result = resend.Emails.send(
        {
            "from": "ORA <ora@aurem.live>",
            "to": ["qa-bot@aurem.live"],
            "subject": "Should be blocked",
            "html": "<p>x</p>",
        }
    )
    assert isinstance(result, dict)
    assert result.get("blocked") is True
    assert result.get("reason") == "internal_domain_block"
