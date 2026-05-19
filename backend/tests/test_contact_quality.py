"""Tests for services.contact_quality — aggregator-email gate."""
from services.contact_quality import (
    classify_email,
    is_aggregator_domain,
    is_blastable_email,
)


# ── Aggregator detection ──────────────────────────────────────────────
def test_facebook_is_aggregator():
    assert is_aggregator_domain("facebook.com")
    assert is_aggregator_domain("www.facebook.com")
    assert is_aggregator_domain("m.facebook.com")
    assert is_aggregator_domain("https://www.facebook.com/ManeAttraction/")


def test_realtor_is_aggregator():
    assert is_aggregator_domain("realtor.ca")
    assert is_aggregator_domain("realtor.com")


def test_wikipedia_subdomain_is_aggregator():
    assert is_aggregator_domain("en.wikipedia.org")


def test_real_smb_domain_is_not_aggregator():
    assert not is_aggregator_domain("manepluse.ca")
    assert not is_aggregator_domain("auremlive.com")
    assert not is_aggregator_domain("hairworksmississauga.com")


# ── classify_email matrix ─────────────────────────────────────────────
def test_classify_aggregator_role_email():
    v, r = classify_email("info@facebook.com")
    assert v == "junk-aggregator"
    assert "facebook.com" in r


def test_classify_aggregator_named_email():
    # even a "real-looking" address on an aggregator is junk for cold outreach
    v, _ = classify_email("john.smith@fresha.com")
    assert v == "junk-aggregator"


def test_classify_role_only_on_real_domain_allowed():
    v, _ = classify_email("info@manepluse.ca")
    assert v == "junk-role-only"  # allowed by default, just labelled


def test_classify_real_business_email():
    v, _ = classify_email("john@hairworksmississauga.com")
    assert v == "ok"


def test_classify_empty_and_malformed():
    assert classify_email("")[0] == "empty"
    assert classify_email(None)[0] == "empty"
    assert classify_email("not-an-email")[0] == "malformed"
    assert classify_email("foo@")[0] == "malformed"


# ── is_blastable_email gate ───────────────────────────────────────────
def test_blastable_blocks_aggregator():
    assert not is_blastable_email("info@facebook.com")
    assert not is_blastable_email("info@google.com")
    assert not is_blastable_email("press@reddit.com")


def test_blastable_allows_real_smb_role_mailbox():
    # Most SMBs respond on info@, so we still allow them.
    assert is_blastable_email("info@manepluse.ca")
    assert is_blastable_email("contact@hairworks.ca")


def test_blastable_allows_named_business_email():
    assert is_blastable_email("john@hairworksmississauga.com")
