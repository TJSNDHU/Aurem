"""Tests for the Public Sovereign-Status payload (iter 322m Day 5+).

These are sanitization-first: the real failure mode here is *leaking*
operational internals to the open internet, not a missing field.
"""
from __future__ import annotations

import pytest

from services.public_status_aggregator import (
    ALLOWED_KEYS,
    FORBIDDEN_SUBSTRINGS,
    assert_payload_safe,
    build_public_status,
)


@pytest.mark.asyncio
async def test_payload_with_no_db_returns_safe_defaults():
    """When the DB is unavailable, the public page must still render —
    the payload should fall back to safe defaults instead of 500'ing."""
    out = await build_public_status(db=None)
    assert isinstance(out, dict)
    assert set(out.keys()) == ALLOWED_KEYS
    # Sanity defaults
    assert 0.0 <= out["system_autonomy_pct"] <= 100.0
    assert 0.0 <= out["decision_veracity_pct"] <= 100.0
    assert isinstance(out["heals_sparkline_24h"], list)
    assert len(out["heals_sparkline_24h"]) == 24
    assert all(isinstance(x, int) and x >= 0 for x in out["heals_sparkline_24h"])
    assert out["badge_color"] in {"green", "yellow", "red"}
    assert out["platform"] == "AUREM"


@pytest.mark.asyncio
async def test_payload_passes_sanitization_guard():
    """The payload must pass `assert_payload_safe` — no extra keys, no
    forbidden substrings (auth tokens, error stacks, internal paths, etc).
    """
    out = await build_public_status(db=None)
    # Should not raise
    assert_payload_safe(out)


def test_forbidden_substrings_are_explicit():
    """Catch any future regression where someone adds a sensitive key
    without updating the sanitizer's blocklist."""
    # Critical substrings must remain in the catalog
    for must_be_blocked in (
        "MONGO_URL", "JWT_SECRET", "_id", "tenant_id",
        "Bearer ", "password",
    ):
        assert must_be_blocked in FORBIDDEN_SUBSTRINGS


def test_allowed_keys_are_locked():
    """Lock the public-payload contract. Adding a new key must be a
    deliberate two-line change (here AND in the aggregator)."""
    assert ALLOWED_KEYS == {
        "ts",
        "system_autonomy_pct",
        "watchdog_heals_24h",
        "council_closed_24h",
        "avg_heal_time_ms",
        "decision_veracity_pct",
        "last_incident_at",
        "heals_sparkline_24h",
        "badge_color",
        "platform",
        "tagline",
        "agents_wedged_now",
        "agents_auto_unwedged_24h",
    }


@pytest.mark.asyncio
async def test_assert_payload_safe_rejects_leaks():
    """Manually inject a leak and ensure the guard fires."""
    out = await build_public_status(db=None)
    out_with_leak = {**out, "tenant_id": "tnt_abc123"}
    with pytest.raises(AssertionError):
        assert_payload_safe(out_with_leak)


@pytest.mark.asyncio
async def test_assert_payload_safe_rejects_forbidden_substring():
    """A value that contains `Bearer ` must trigger the substring guard
    even if every key is in the allowlist."""
    out = await build_public_status(db=None)
    out_with_token = {**out, "tagline": "send Bearer jwt.token here"}
    with pytest.raises(AssertionError):
        assert_payload_safe(out_with_token)
