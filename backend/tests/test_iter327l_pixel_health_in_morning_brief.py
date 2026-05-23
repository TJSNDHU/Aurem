"""
iter 327l — Pixel Health in Morning Brief.

Founder mandate (verbatim):
  "Yesterday's universal_events count vs 7-day average.
   If count drops 50%+ below average → Telegram alert same morning.
   Add to morning brief output — plain English line:
     'Yesterday: 247 pixel events (7-day avg: 312) — normal'
   OR
     'Yesterday: 45 pixel events (7-day avg: 312) — LOW, check pixel install'"

What this iter delivers:
  1. services/pixel_health.py
       - compute_pixel_health(db) → {yesterday_count, seven_day_avg,
         classification, brief_line, date_yesterday}
       - maybe_alert_low_pixel_day(db, health) → Telegram alert with
         per-date dedup fingerprint, only when classification='low'
  2. services/morning_brief.py — splices PIXEL HEALTH section into
     the brief_text AND adds `sections.pixel_health` structured data.
  3. Safety: brief never crashes if pixel_health raises; the alert
     dispatch never blocks brief generation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import mongomock_motor
import pytest


# ─────────────────────────────────────────────
# classify()
# ─────────────────────────────────────────────

def test_classify_normal_when_yesterday_close_to_avg():
    from services.pixel_health import _classify
    assert _classify(yesterday=300, avg=312.0) == "normal"
    assert _classify(yesterday=250, avg=312.0) == "normal"  # ~20% drop, still normal


def test_classify_low_when_yesterday_under_50_pct_of_avg():
    from services.pixel_health import _classify
    # 45 < 312 * 0.5 = 156 → LOW
    assert _classify(yesterday=45, avg=312.0) == "low"
    assert _classify(yesterday=100, avg=312.0) == "low"
    # Edge: exactly 50% — strict less-than, so this is normal.
    assert _classify(yesterday=156, avg=312.0) == "normal"


def test_classify_sparse_when_avg_below_threshold():
    """Don't grade days where the 7-day baseline is too small."""
    from services.pixel_health import _classify, MIN_AVG_FOR_ALERT
    assert _classify(yesterday=0, avg=float(MIN_AVG_FOR_ALERT - 1)) == "sparse"
    assert _classify(yesterday=0, avg=0.0) == "sparse"


# ─────────────────────────────────────────────
# compute_pixel_health()
# ─────────────────────────────────────────────

async def _seed(db, dt: datetime, n: int):
    """Insert N synthetic pixel events at the given UTC instant."""
    docs = [{"ts": dt, "tenant_id": "smoke", "universal_type": "custom.pageview"}
             for _ in range(n)]
    if docs:
        await db.universal_events.insert_many(docs)


@pytest.mark.asyncio
async def test_compute_returns_brief_line_normal():
    from services.pixel_health import compute_pixel_health
    db = mongomock_motor.AsyncMongoMockClient()["test_327l"]
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 7-day window: 308 events total → avg ≈ 44
    for i in range(1, 8):
        await _seed(db, midnight - timedelta(days=i, hours=12), 44)
    # Yesterday: 40 → within tolerance of 44 → normal
    await _seed(db, midnight - timedelta(hours=12), 40)

    out = await compute_pixel_health(db)
    assert out["yesterday_count"] == 40
    assert out["seven_day_avg"] == 44.0
    assert out["classification"] == "normal"
    assert "Yesterday: 40 pixel events" in out["brief_line"]
    assert "7-day avg: 44" in out["brief_line"]
    assert "normal" in out["brief_line"]


@pytest.mark.asyncio
async def test_compute_returns_brief_line_low():
    from services.pixel_health import compute_pixel_health
    db = mongomock_motor.AsyncMongoMockClient()["test_327l_low"]
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 7-day baseline: ~50/day → avg = 50
    for i in range(1, 8):
        await _seed(db, midnight - timedelta(days=i, hours=12), 50)
    # Yesterday: 10 (80% drop) → LOW
    await _seed(db, midnight - timedelta(hours=12), 10)

    out = await compute_pixel_health(db)
    assert out["yesterday_count"] == 10
    assert out["classification"] == "low"
    assert "LOW, check pixel install" in out["brief_line"]


@pytest.mark.asyncio
async def test_compute_returns_sparse_when_no_history():
    from services.pixel_health import compute_pixel_health
    db = mongomock_motor.AsyncMongoMockClient()["test_327l_sparse"]
    out = await compute_pixel_health(db)
    assert out["yesterday_count"] == 0
    assert out["seven_day_avg"] == 0.0
    assert out["classification"] == "sparse"
    assert "sparse" in out["brief_line"]


@pytest.mark.asyncio
async def test_compute_never_raises_on_db_failure():
    from services.pixel_health import compute_pixel_health
    out = await compute_pixel_health(None)  # no db → soft path
    assert out["classification"] == "sparse"
    assert "Yesterday: 0 pixel events" in out["brief_line"]


# ─────────────────────────────────────────────
# maybe_alert_low_pixel_day()
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_not_fired_for_normal_classification():
    from services.pixel_health import maybe_alert_low_pixel_day
    res = await maybe_alert_low_pixel_day(
        db=None,
        health={"classification": "normal", "date_yesterday": "2026-02-22"},
    )
    assert res["alerted"] is False
    assert res["reason"] == "not_low"


@pytest.mark.asyncio
async def test_alert_not_fired_for_sparse_classification():
    from services.pixel_health import maybe_alert_low_pixel_day
    res = await maybe_alert_low_pixel_day(
        db=None,
        health={"classification": "sparse", "date_yesterday": "2026-02-22"},
    )
    assert res["alerted"] is False


@pytest.mark.asyncio
async def test_alert_fired_for_low_classification_uses_dated_fingerprint():
    from services.pixel_health import maybe_alert_low_pixel_day
    captured = {}

    async def fake_send(message, alert_type, fingerprint):
        captured["message"] = message
        captured["alert_type"] = alert_type
        captured["fingerprint"] = fingerprint
        return {"ok": True, "sent": True}

    with patch("services.silent_failure_alerts._send", new=fake_send):
        res = await maybe_alert_low_pixel_day(
            db=None,
            health={
                "classification":   "low",
                "yesterday_count":  45,
                "seven_day_avg":    312,
                "date_yesterday":   "2026-02-22",
            },
        )
    assert res["alerted"] is True
    assert captured["alert_type"] == "pixel_health_low"
    # Dedup fingerprint MUST include the date so the alert is fired
    # at most once per day even if the brief reruns.
    assert captured["fingerprint"] == "pixel_low_2026-02-22"
    # Body is plain English with the key numbers + recovery hint.
    assert "45" in captured["message"]
    assert "312" in captured["message"]
    assert "aurem-pixel.js" in captured["message"]
    assert "/api/universal/webhooks/generic" in captured["message"]


# ─────────────────────────────────────────────
# Morning Brief integration
# ─────────────────────────────────────────────

def test_morning_brief_imports_and_calls_pixel_health():
    """Source-level: morning_brief must import compute_pixel_health
    and maybe_alert_low_pixel_day, splice a PIXEL HEALTH section into
    brief_text, and persist pixel_health on `sections`."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent /
            "services" / "morning_brief.py").read_text()
    assert "from services.pixel_health import compute_pixel_health, maybe_alert_low_pixel_day" in src
    assert "PIXEL HEALTH:" in src
    assert '"pixel_health": pixel_health_data or {}' in src
    assert "iter 327l" in src


def test_pixel_health_section_is_optional_in_brief():
    """If pixel_health computation fails, the brief still renders
    (pixel_section is "" and the f-string substitutes empty)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent /
            "services" / "morning_brief.py").read_text()
    # The try/except wrapping pixel_health must exist.
    assert "pixel health unavailable" in src
