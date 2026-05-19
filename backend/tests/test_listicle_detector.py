"""Tests for the listicle / SEO-page-title detector in hunt_live.

Imports the helper directly rather than via the full hunt_live module
to keep this test fast (hunt_live drags in motor + httpx + many services).
"""
import importlib
import sys


def _get_detector():
    """Import _is_listicle_title from services.hunt_live."""
    sys.path.insert(0, "/app/backend")
    mod = importlib.import_module("services.hunt_live")
    return mod._is_listicle_title


def test_real_smb_name_passes():
    fn = _get_detector()
    for name in [
        "Mane Attraction Hair Studio",
        "TJ Auto Clinic",
        "Mississauga Family Dentistry",
        "Boston Dental Group",  # short, no separator → passes
        "Sandhair Co",
    ]:
        listicle, reason = fn(name)
        assert not listicle, f"{name!r} flagged as listicle: {reason}"


def test_html_title_separator_rejected():
    fn = _get_detector()
    for name in [
        "Dental Care That Feels Like Self-Care | Boston Dental",
        "Top Plumbers in Toronto — HomeStars",
        "Buy a Well-established Spa And Salon - Eastern Canada",
        "Best Roofers (2025) - Yelp",
    ]:
        listicle, reason = fn(name)
        assert listicle, f"{name!r} should be listicle"
        assert reason, "reason must be non-empty"


def test_listicle_keywords_rejected():
    fn = _get_detector()
    for name in [
        "Top 10 Hair Salons in Mississauga",
        "Best Plumbers Near Me",
        "How to Find a Good Dentist",
        "Buying Guide for Auto Repair",
        "What is the Cost of a Roof Replacement",
    ]:
        listicle, reason = fn(name)
        assert listicle, f"{name!r} should be listicle: got {reason}"


def test_aggregator_suffix_rejected():
    fn = _get_detector()
    for name in [
        "Mississauga Plumbing - Yelp",
        "Hair Salon - Wikipedia",
        "Dentist Office - Reddit",
        "Plumber Mississauga - Yellowpages",
    ]:
        listicle, reason = fn(name)
        assert listicle, f"{name!r} should be aggregator-suffix"


def test_year_in_parens_rejected():
    fn = _get_detector()
    listicle, reason = fn("Top Salons in Mississauga (2025 Edition)")
    assert listicle
    assert "20" in reason or "edition" in reason.lower() or "top" in reason.lower()


def test_empty_and_too_long_rejected():
    fn = _get_detector()
    assert fn("")[0]
    assert fn("a" * 100)[0]
