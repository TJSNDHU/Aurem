"""
tests/test_temperature_webhook_d57.py — iter D-57

Three things to assert:
  1. Temperature-by-intent helper (`_temperature_for_intent`) returns
     0.0 for code intents, 0.2 for planning, 0.1 default.
  2. Anti-hallucination guardrail (`_inject_guardrail`) appends the
     marker exactly once.
  3. /api/leads/hot endpoint returns only leads with hot_lead_flag.
  4. WHAPI fallback bug fix — when wresult.success=False, twilio.py
     does NOT early-return.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── Temperature by intent ───────────────────────────────────────────

def test_temperature_for_code_intents_is_zero():
    from services.dev_cto_chat import _temperature_for_intent
    for intent in ("build", "fix_code", "diagnostic", "refactor",
                    "code_review"):
        assert _temperature_for_intent(intent) == 0.0, intent


def test_temperature_for_planning_is_zero_point_two():
    from services.dev_cto_chat import _temperature_for_intent
    for intent in ("strategic", "planning", "architecture", "design"):
        assert _temperature_for_intent(intent) == 0.2, intent


def test_temperature_default_is_zero_point_one():
    from services.dev_cto_chat import _temperature_for_intent
    assert _temperature_for_intent("question") == 0.1
    assert _temperature_for_intent("")          == 0.1
    assert _temperature_for_intent(None)        == 0.1
    assert _temperature_for_intent("random")    == 0.1


# ── Guardrail injection ─────────────────────────────────────────────

def test_guardrail_inserts_once():
    from services.dev_cto_chat import _inject_guardrail
    msgs = [
        {"role": "system", "content": "system prompt"},
        {"role": "user",   "content": "build a thing"},
    ]
    out1 = _inject_guardrail(msgs)
    out2 = _inject_guardrail(out1)
    # Inserted exactly once across two invocations
    assert len(out1) == 3
    assert len(out2) == 3
    assert "GUARDRAIL — Do NOT invent" in out1[-2]["content"]


def test_guardrail_mentions_no_invented_dates_shas():
    from services.dev_cto_chat import _GUARDRAIL_MSG
    assert "commit SHA"  in _GUARDRAIL_MSG
    assert "dates"       in _GUARDRAIL_MSG
    assert "iter tags"   in _GUARDRAIL_MSG
    assert "API endpoint" in _GUARDRAIL_MSG


# ── Resend webhook + /api/leads/hot endpoint ────────────────────────

class _Coll:
    def __init__(self):
        self._rows: list[dict] = []
    def find(self, q, p=None):
        rows = [r for r in self._rows if self._match(r, q)]
        class _C:
            def __init__(s, rs): s._rs = rs
            def sort(s, *a, **kw): return s
            def limit(s, n): s._rs = s._rs[:n]; return s
            def __aiter__(s): s._i = 0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1; return r
        return _C(rows)
    def _match(self, r, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$gte" in v:
                if r.get(k, "") < v["$gte"]:
                    return False
            elif r.get(k) != v:
                return False
        return True


class _DB:
    def __init__(self):
        self.campaign_leads = _Coll()


def test_hot_leads_endpoint_filters_by_flag():
    from routers import resend_webhook_router as mod
    from datetime import datetime, timezone, timedelta

    db = _DB()
    now = datetime.now(timezone.utc)
    db.campaign_leads._rows = [
        {"lead_id": "L1", "business_name": "Hot Salon",
         "email": "a@b.com",
         "hot_lead_flag": True, "hot_lead_reason": "email_opened",
         "hot_lead_signal_at": (now - timedelta(minutes=5)).isoformat()},
        {"lead_id": "L2", "business_name": "Cold Spa",
         "hot_lead_flag": False,
         "hot_lead_signal_at": now.isoformat()},
    ]
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.hot_leads(hours=24, limit=10,
                                      authorization="Bearer x"))
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["items"][0]["business_name"] == "Hot Salon"
    # "ago" string is rendered
    assert out["items"][0]["ago"]
    assert "min ago" in out["items"][0]["ago"]


def test_hot_leads_endpoint_route_registered():
    from routers import resend_webhook_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/cto/leads/hot"       in paths
    assert "/api/webhooks/resend"     in paths


# ── WHAPI fallback bug fix ──────────────────────────────────────────

def test_whapi_failure_falls_through_to_twilio():
    """If WHAPI returns success=False, the function MUST continue to the
    Twilio path instead of early-returning the WHAPI error.

    We verify via source inspection of the precise patched region
    (substring presence only — no catastrophic regex).
    """
    path = os.path.join(ROOT, "shared", "providers", "twilio.py")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    # The fix comment is in place
    assert "iter D-57 — WHAPI returned success=False" in src
    # The fall-through log message exists
    assert "falling back to Twilio WABA" in src
    # Critically: ensure the patched lines exist AND the old buggy
    # `return wresult` (outside the success branch) is no longer
    # there in the WHAPI primary block.
    # The WHAPI primary block starts at "# Primary: WHAPI.cloud" and
    # ends at the matching "except Exception as e:" handler. Grab that
    # slice deterministically.
    start_marker = "# Primary: WHAPI.cloud"
    end_marker   = "WHAPI send failed, falling back to Twilio"
    s_idx = src.find(start_marker)
    e_idx = src.find(end_marker, s_idx)
    assert s_idx >= 0 and e_idx > s_idx
    slice_ = src[s_idx:e_idx]
    # Count actual `return wresult` STATEMENTS (lines that start with
    # whitespace + `return`), ignoring the explanatory comment text.
    lines_with_return = [
        ln for ln in slice_.split("\n")
        if ln.lstrip().startswith("return wresult")
    ]
    assert len(lines_with_return) == 1, (
        f"expected exactly 1 actual `return wresult` statement inside "
        f"WHAPI primary, got {len(lines_with_return)}: "
        f"{lines_with_return}"
    )


# ── Frontend wiring assertions ──────────────────────────────────────

FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src", "platform", "developers")
)


def test_temperature_badge_component_exists():
    p = os.path.join(FRONTEND, "TemperatureBadge.jsx")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "CODE_INTENTS" in src
    assert "PLAN_INTENTS" in src
    assert "temperatureFor" in src


def test_hot_leads_bar_component_exists():
    p = os.path.join(FRONTEND, "HotLeadsBar.jsx")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "/api/leads/hot" in src
    assert "Flame" in src


def test_chat_panel_mounts_temperature_and_hot_leads():
    p = os.path.join(FRONTEND, "DevCtoChatPanel.jsx")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "import TemperatureBadge" in src
    assert "import HotLeadsBar" in src
    assert "<TemperatureBadge" in src
    assert "<HotLeadsBar" in src
