"""
iter 282al-18 · Part 3 Tests — Report page dynamic CTA by score
================================================================
Tests the _build_cta_for_score() helper:
  score < 60    → type=repair  $197 one-time
  score 60-79   → type=tuneup  $297/mo Growth
  score >= 80   → type=widget  Free trial
  score == 0/None → type=generic (no audit yet)
"""
from __future__ import annotations

import pytest
from routers.aurem_public_report_router import _build_cta_for_score


def test_cta_repair_for_low_score():
    cta = _build_cta_for_score(45, "acme-slug")
    assert cta["type"] == "repair"
    assert cta["price_cad"] == 197
    assert "197" in cta["headline"]
    assert "/api/repair/checkout" in cta["checkout_url"]
    assert "acme-slug" in cta["checkout_url"]


def test_cta_repair_boundary_just_below_60():
    assert _build_cta_for_score(59, "s")["type"] == "repair"


def test_cta_tuneup_for_mid_score():
    cta = _build_cta_for_score(70, "slug-mid")
    assert cta["type"] == "tuneup"
    assert cta["price_cad"] == 297
    assert "297" in cta["headline"]
    assert "growth" in cta["checkout_url"].lower() or "plan=growth" in cta["checkout_url"]


def test_cta_tuneup_boundary_at_60_and_79():
    assert _build_cta_for_score(60, "s")["type"] == "tuneup"
    assert _build_cta_for_score(79, "s")["type"] == "tuneup"


def test_cta_widget_for_high_score():
    cta = _build_cta_for_score(85, "slug-high")
    assert cta["type"] == "widget"
    assert cta["price_cad"] == 0
    assert "free" in cta["price_label"].lower()
    assert "widget-trial" in cta["checkout_url"]


def test_cta_widget_boundary_at_80():
    assert _build_cta_for_score(80, "s")["type"] == "widget"


def test_cta_generic_when_no_audit():
    cta = _build_cta_for_score(0, "slug-new")
    assert cta["type"] == "generic"
    assert "signup" in cta["checkout_url"]
    assert cta["button_text"]


def test_cta_generic_handles_negative_or_none():
    assert _build_cta_for_score(None, "s")["type"] == "generic"  # type: ignore[arg-type]
    assert _build_cta_for_score(-5, "s")["type"] == "generic"


def test_cta_carries_slug_into_all_urls():
    for score in (40, 70, 90, 0):
        cta = _build_cta_for_score(score, "test-slug-123")
        assert "test-slug-123" in cta["checkout_url"]


def test_cta_includes_required_fields():
    cta = _build_cta_for_score(45, "s")
    for key in ("type", "score", "headline", "subline", "price_cad",
                "price_label", "button_text", "checkout_url"):
        assert key in cta, f"missing {key}"
