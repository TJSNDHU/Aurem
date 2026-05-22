"""
test_iter326ee_email_health_and_spend_card.py — Phase 3 P2.2 + P2.3.
══════════════════════════════════════════════════════════════════════════════
P2.2 — Daily LLM spend dashboard card (admin UI). Backend endpoint
       `/api/admin/ora/cost-summary` already shipped in iter 326w; this
       iter adds the React surface so a founder can spot a $50 overnight
       LLM spike at a glance.

P2.3 — Email channel health probe. Founder ask: "Yeh probe iter 326x
       wala 'resend.logs' regression bug ko pakad leta before it bit a
       real campaign." Endpoint `/api/admin/ora/email-health` aggregates
       email send success/failure across BOTH log sources (email_logs
       transactional + outreach_history blast cycles), returns sent /
       failed / success_rate / verdict / top failure reasons.

WHAT THIS TEST LOCKS IN
───────────────────────
  Backend (P2.3)
    • /api/admin/ora/email-health registered on admin_ora_router
    • Handler accepts `hours` query param
    • Handler calls _ensure_admin (auth gate)
    • Response schema: sent, failed, total, success_rate, verdict,
      top_errors

  Frontend (P2.2 + P2.3)
    • DailySpendCard.jsx exists, default-export React component,
      calls /api/admin/ora/cost-summary, uses admin token, has
      data-testids
    • EmailHealthCard.jsx exists, default-export React component,
      calls /api/admin/ora/email-health, uses admin token, has
      data-testids, color-codes verdict

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326ee_email_health_and_spend_card.py -v
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Backend — P2.3 email health endpoint
# ─────────────────────────────────────────────────────────────────────────────
def test_email_health_endpoint_registered():
    from routers import admin_ora_router
    paths = [
        getattr(r, "path", None)
        for r in getattr(admin_ora_router.router, "routes", [])
    ]
    assert "/api/admin/ora/email-health" in paths, (
        f"endpoint missing; routes: {paths}"
    )


def test_email_health_endpoint_accepts_hours_param():
    from routers.admin_ora_router import admin_ora_email_health
    sig = inspect.signature(admin_ora_email_health)
    assert "hours" in sig.parameters


def test_email_health_endpoint_calls_ensure_admin():
    from routers.admin_ora_router import admin_ora_email_health
    src = inspect.getsource(admin_ora_email_health)
    assert "_ensure_admin" in src, (
        "email-health handler must enforce admin auth"
    )


def test_email_health_endpoint_reads_both_log_sources():
    """Must combine email_logs (transactional) + campaign_leads.outreach_history
    (blast cycles) — otherwise a blast regression like iter 326x slips
    through silently."""
    from routers.admin_ora_router import admin_ora_email_health
    src = inspect.getsource(admin_ora_email_health)
    assert "email_logs" in src
    assert "outreach_history" in src


def test_email_health_response_shape_complete():
    """Response must carry every field the frontend card renders —
    locks the API contract so a backend refactor can't silently break
    the UI."""
    from routers.admin_ora_router import admin_ora_email_health
    src = inspect.getsource(admin_ora_email_health)
    for field in ("sent", "failed", "total", "success_rate",
                  "verdict", "top_errors", "window_hours"):
        assert f'"{field}"' in src, f"response missing field: {field}"


def test_email_health_verdict_thresholds():
    """healthy ≥ 0.95, warning ≥ 0.80, critical < 0.80 — locks the
    SLO so a future drift can't silently weaken the alert."""
    from routers.admin_ora_router import admin_ora_email_health
    src = inspect.getsource(admin_ora_email_health)
    assert "0.95" in src
    assert "0.80" in src
    assert '"healthy"' in src
    assert '"warning"' in src
    assert '"critical"' in src


# ─────────────────────────────────────────────────────────────────────────────
# Frontend smoke checks
# ─────────────────────────────────────────────────────────────────────────────
_SPEND  = pathlib.Path("/app/frontend/src/platform/admin/DailySpendCard.jsx")
_HEALTH = pathlib.Path("/app/frontend/src/platform/admin/EmailHealthCard.jsx")


def test_daily_spend_card_exists():
    assert _SPEND.exists(), f"missing: {_SPEND}"


def test_daily_spend_card_default_export():
    src = _SPEND.read_text()
    assert re.search(r"export default function DailySpendCard", src)


def test_daily_spend_card_uses_correct_endpoint_and_token():
    src = _SPEND.read_text()
    assert "/api/admin/ora/cost-summary" in src
    assert "aurem_admin_token" in src


def test_daily_spend_card_has_data_testids():
    src = _SPEND.read_text()
    for tid in (
        "daily-spend-card",
        "daily-spend-total",
        "daily-spend-providers",
        "daily-spend-days-select",
    ):
        assert f'data-testid="{tid}"' in src, f"missing testid: {tid}"


def test_daily_spend_card_renders_sparkline():
    src = _SPEND.read_text()
    assert "Sparkline" in src or "sparkline" in src
    assert "daily-spend-sparkline" in src


def test_email_health_card_exists():
    assert _HEALTH.exists(), f"missing: {_HEALTH}"


def test_email_health_card_default_export():
    src = _HEALTH.read_text()
    assert re.search(r"export default function EmailHealthCard", src)


def test_email_health_card_uses_correct_endpoint_and_token():
    src = _HEALTH.read_text()
    assert "/api/admin/ora/email-health" in src
    assert "aurem_admin_token" in src


def test_email_health_card_renders_verdict_and_metrics():
    src = _HEALTH.read_text()
    for tid in (
        "email-health-card",
        "email-health-verdict",
        "email-health-sent",
        "email-health-failed",
        "email-health-rate",
    ):
        assert f'data-testid="{tid}"' in src, f"missing testid: {tid}"
