"""Tests for iter 324q subject-line redesign + A/B variants."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.aurem_outreach_templates import (
    render_email_subject,
    render_email_subject_variant_a,
    render_email_subject_variant_b,
    pick_subject_variant,
    render_all,
    _short_business_name,
    _format_search_volume,
)


SAMPLE_LEAD = {
    "lead_id": "osm-brampton-deadbeef00",
    "business_name": "AtlasCare Heating & Cooling",
    "city": "Brampton",
    "category": "hvac",
    "email": "info@atlascare.ca",
    "website_url": "https://atlascare.ca",
    "phone": "9051234567",
}


def test_variant_a_matches_user_spec_format():
    """User-provided example: 'Found 3 gaps hurting AtlasCare's Google ranking'."""
    subj = render_email_subject_variant_a(SAMPLE_LEAD)
    assert subj.startswith("Found "), subj
    assert "gaps hurting" in subj, subj
    assert "AtlasCare" in subj, subj
    assert "Google ranking" in subj, subj
    # Must include the actual integer
    assert any(ch.isdigit() for ch in subj), subj


def test_variant_b_loss_frame_location():
    subj = render_email_subject_variant_b(SAMPLE_LEAD)
    assert "AtlasCare" in subj, subj
    assert "Brampton" in subj, subj
    assert "missing you" in subj, subj
    assert "K" in subj or any(ch.isdigit() for ch in subj), subj


def test_subjects_under_70_chars_for_reasonable_names():
    """Gmail truncates subjects around 70 chars."""
    for variant in ("A", "B"):
        subj = render_email_subject(SAMPLE_LEAD, variant=variant)
        assert len(subj) <= 70, f"Variant {variant} too long ({len(subj)}): {subj!r}"


def test_long_business_names_get_truncated():
    lead = {**SAMPLE_LEAD,
            "business_name": "Mr. Rooter Plumbing of Greater Toronto Area Inc."}
    subj_a = render_email_subject_variant_a(lead)
    subj_b = render_email_subject_variant_b(lead)
    assert len(subj_a) <= 70, subj_a
    assert len(subj_b) <= 70, subj_b
    # Inc. suffix should be stripped
    assert "Inc." not in subj_a, subj_a


def test_picker_is_deterministic_per_lead_id():
    """Same lead_id MUST always pick same variant (consistent A/B data)."""
    for _ in range(5):
        assert pick_subject_variant("osm-test-001") == pick_subject_variant("osm-test-001")
        assert pick_subject_variant("osm-test-002") == pick_subject_variant("osm-test-002")


def test_picker_splits_population_roughly_evenly():
    """Across many lead IDs, the bucket split should be roughly 40-60%."""
    a, b = 0, 0
    for i in range(2000):
        v = pick_subject_variant(f"osm-mississauga-{i:08x}")
        if v == "A":
            a += 1
        else:
            b += 1
    ratio_a = a / (a + b)
    assert 0.40 <= ratio_a <= 0.60, f"Skewed bucketing: A={a} B={b}"


def test_render_all_exposes_both_variants():
    out = render_all(SAMPLE_LEAD)
    assert "email" in out
    email = out["email"]
    assert email["subject_variant"] in ("A", "B")
    assert email["subject_variants"]["A"].startswith("Found ")
    assert "missing you" in email["subject_variants"]["B"]
    # subject equals whichever variant was picked
    picked = email["subject_variant"]
    assert email["subject"] == email["subject_variants"][picked]


def test_short_business_name_handles_edge_cases():
    assert _short_business_name("") == ""
    assert _short_business_name("Short Name") == "Short Name"
    assert _short_business_name("AtlasCare Heating & Cooling Inc.") == "AtlasCare Heating & Cooling"
    long_name = "A" * 50
    truncated = _short_business_name(long_name, max_len=20)
    assert len(truncated) <= 20
    assert truncated.endswith("…")


def test_format_search_volume_formatting():
    assert _format_search_volume(500) == "500"
    assert _format_search_volume(1000) == "1K"
    assert _format_search_volume(1500) == "1.5K"
    assert _format_search_volume(8500) == "8.5K"
    assert _format_search_volume(34000) == "34K"
    assert _format_search_volume(100) == "100"


def test_variants_actually_differ():
    """Sanity — A and B must produce DIFFERENT subjects (else no A/B test)."""
    a = render_email_subject_variant_a(SAMPLE_LEAD)
    b = render_email_subject_variant_b(SAMPLE_LEAD)
    assert a != b
