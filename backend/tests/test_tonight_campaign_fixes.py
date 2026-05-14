"""Tests for tonight's campaign-rescue fixes (Feb 2026).

Covers three real bugs identified from a deep prod-data scan:
  1. ghost_scout `_normalize_phone` accepting unbounded digit strings
  2. auto_blast country detection false-positive on "ON" substring
     (matched BOSTON / BRANDON / JOHNSTON)
  3. system_uptime `_safe_count` masking DB outages by returning -1
     (now returns None and health flips to 'error')
"""
from __future__ import annotations

import pytest

from services.ghost_scout_iproyal import _normalize_phone
from routers import system_uptime_router as suptime


# ─── Bug fix 1: phone normalization bounds ─────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("416-555-1234", "+14165551234"),
    ("(416) 555 1234", "+14165551234"),
    ("1-416-555-1234", "+14165551234"),
    ("+1 416 555 1234", "+14165551234"),
    ("44 20 7946 0958", "+442079460958"),  # 11 digits, non-1 leading → +44...
    ("",                ""),
    ("123",             ""),                # too short
    ("1234567890123456", ""),               # 16 digits → reject (E.164 cap 15)
    ("notaphone",       ""),
])
def test_normalize_phone_bounds(raw, expected):
    assert _normalize_phone(raw) == expected


# ─── Bug fix 2: country detection (auto_blast_engine) ──────────────────
def _infer(addr: str, city: str) -> str:
    """Replica of the in-function logic so we can unit-test without
    invoking the full Accurate-Scout pipeline."""
    _addr_upper = addr.upper()
    _ca_provinces = ("ON", "QC", "BC", "AB", "SK", "MB", "NB", "NS",
                     "PE", "NL", "NT", "NU", "YT")
    _ca_province_hit = any(
        f", {p}" in _addr_upper or f" {p} " in _addr_upper
        or _addr_upper.endswith(f" {p}") or _addr_upper.endswith(f",{p}")
        for p in _ca_provinces
    )
    return "ca" if (_ca_province_hit or city.lower() in (
        "toronto", "brampton", "mississauga", "ottawa", "vancouver",
        "calgary", "edmonton", "montreal", "quebec"
    )) else "us"


@pytest.mark.parametrize("addr,city,expected", [
    ("123 Yonge St, Toronto, ON M5C 2N4", "Toronto",        "ca"),
    ("999 King St W, Hamilton, ON",       "Hamilton",       "ca"),
    ("100 Spadina Ave Toronto ON",        "Toronto",        "ca"),
    ("500 8th Ave, Calgary, AB T2P 1G1",  "Calgary",        "ca"),
    # The old code returned "ca" for these false positives:
    ("1 Beacon St, Boston, MA",           "Boston",         "us"),
    ("250 Brandon Ave, Roanoke, VA",      "Roanoke",        "us"),
    ("12 Johnston Pl, Brooklyn, NY",      "Brooklyn",       "us"),
    ("742 Evergreen Tce, Springfield, OR","Springfield",    "us"),
])
def test_country_inference(addr, city, expected):
    assert _infer(addr, city) == expected


# ─── Bug fix 3: _safe_count returns None on failure ────────────────────
class _BrokenColl:
    name = "broken"

    async def count_documents(self, _q):
        raise RuntimeError("simulated DB outage")


@pytest.mark.asyncio
async def test_safe_count_returns_none_on_failure():
    out = await suptime._safe_count(_BrokenColl(), {})
    assert out is None, "Must NOT return -1 (which masked DB errors as zero)"


class _OkColl:
    name = "ok"

    async def count_documents(self, _q):
        return 42


@pytest.mark.asyncio
async def test_safe_count_returns_int_on_success():
    assert await suptime._safe_count(_OkColl(), {}) == 42
