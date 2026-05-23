"""
tests/test_iter330_outreach_gap_close.py — iter 330

Regression for the 6-fix outreach gap-close batch:
  FIX 1 — Closer Day-5 trigger (services/closer_day5_trigger.py + cron)
  FIX 2 — WhatsApp Twilio WABA gap alert wired into startup
  FIX 3 — Reply-inbox → ORA bridge (classify + act + draft + DNC)
  FIX 4 — Proactive outreach run-row stamp
  FIX 5 — Outreach Health snapshot service + admin router + frontend card
  FIX 6 — Social autopilot daily LinkedIn post via Brightbean
"""
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── FIX 1 — Closer Day-5 ───────────────────────────────────────────


def test_closer_day5_service_exists():
    from services import closer_day5_trigger as c
    assert callable(c.run_closer_day5_sweep)


def test_closer_day5_cron_wired():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_closer_day5" in src
    assert "minutes=30" in src
    assert "run_closer_day5_sweep" in src


@pytest.mark.asyncio
async def test_closer_day5_skips_dnc_and_stamps_lead():
    from services import closer_day5_trigger

    LEAD = {
        "lead_id":   "L1",
        "phone":     "+16139990001",
        "email":     "owner@biz.com",
        "status":    "blasted",
        "blast_chain": {
            "next_touch_n":  4,
            "next_touch_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        },
    }

    class Cursor:
        def __init__(self, rows): self.rows = rows
        def limit(self, n): return self
        async def to_list(self, length=None): return self.rows[:length] if length else self.rows

    class LeadsColl:
        def __init__(self): self.updates = []
        def find(self, q, p): return Cursor([LEAD])
        async def update_one(self, q, u): self.updates.append((q, u))

    class DncColl:
        async def find_one(self, q): return {"email": "owner@biz.com"}  # ← DNC hit

    class RunsColl:
        def __init__(self): self.rows = []
        async def insert_one(self, d): self.rows.append(d)

    class DB:
        def __init__(self):
            self.campaign_leads = LeadsColl()
            self.do_not_contact = DncColl()
            self.closer_day5_runs = RunsColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await closer_day5_trigger.run_closer_day5_sweep(db)
    assert out["ok"] is True
    assert out["skipped"] == 1
    assert out["armed"] == 0
    # The lead must be stamped so we never re-evaluate it.
    assert any("closer_day5_armed_at" in (u[1].get("$set") or {})
                for u in db.campaign_leads.updates)
    assert db.closer_day5_runs.rows[-1]["skipped"] == 1


# ── FIX 2 — Twilio WABA gap alert ──────────────────────────────────


def test_wa_gap_alert_wired_in_registry():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_wa_gap_alert_once" in src
    assert "TWILIO_WA_FROM_NUMBER" in src
    assert "WHAPI_BLAST_DISABLED" in src


# ── FIX 3 — Reply-inbox ────────────────────────────────────────────


def test_reply_inbox_classifier_basic():
    from services.reply_inbox_processor import _classify_intent_quick
    assert _classify_intent_quick("Please unsubscribe me") == "not_interested"
    assert _classify_intent_quick("How much does it cost?") == "question"
    assert _classify_intent_quick("Yes please, interested!") == "interested"
    assert _classify_intent_quick("ok") == "unclear"


@pytest.mark.asyncio
async def test_reply_inbox_processes_not_interested_into_dnc():
    from services import reply_inbox_processor

    class DNCColl:
        def __init__(self): self.upserts = []
        async def update_one(self, q, u, upsert=False): self.upserts.append((q, u, upsert))

    class LeadsColl:
        async def find_one(self, q, p=None):
            return {"lead_id": "L9", "email": q.get("email")}
        async def update_one(self, q, u): pass

    class InboxColl:
        async def update_one(self, q, u): pass

    class AuditColl:
        def __init__(self): self.rows = []
        async def insert_one(self, d): self.rows.append(d)

    class DB:
        def __init__(self):
            self.do_not_contact = DNCColl()
            self.campaign_leads = LeadsColl()
            self.email_inbox    = InboxColl()
            self.reply_inbox_actions = AuditColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await reply_inbox_processor.process_reply(db, {
        "_id_orig":   "abc",
        "__source":   "email_inbox",
        "from_email": "lead@biz.com",
        "body_text":  "please remove me from your list",
    })
    assert out["ok"] is True
    assert out["intent"] == "not_interested"
    assert out["did"] == "added_to_dnc"
    assert len(db.do_not_contact.upserts) == 1
    assert db.reply_inbox_actions.rows[-1]["action"] == "added_to_dnc"


@pytest.mark.asyncio
async def test_reply_inbox_drafts_for_question_intent_not_auto_send():
    from services import reply_inbox_processor

    class DraftsColl:
        def __init__(self): self.rows = []
        async def insert_one(self, d): self.rows.append(d)

    class LeadsColl:
        async def find_one(self, q, p=None): return None
        async def update_one(self, q, u): pass

    class InboxColl:
        async def update_one(self, q, u): pass

    class AuditColl:
        async def insert_one(self, d): pass

    class DB:
        def __init__(self):
            self.reply_inbox_drafts = DraftsColl()
            self.campaign_leads = LeadsColl()
            self.email_inbox = InboxColl()
            self.reply_inbox_actions = AuditColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await reply_inbox_processor.process_reply(db, {
        "_id_orig":   "id1",
        "__source":   "email_inbox",
        "from_email": "lead@biz.com",
        "body_text":  "What is your pricing?",
    })
    assert out["intent"] == "question"
    assert out["auto"] is False
    assert out["did"] == "drafted_for_approval"
    assert db.reply_inbox_drafts.rows[-1]["status"] == "pending_approval"
    assert "draft_reply" in db.reply_inbox_drafts.rows[-1]


def test_reply_inbox_cron_wired():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_reply_inbox" in src
    assert "reply_inbox_sweep" in src


def test_morning_brief_includes_reply_inbox_line():
    src = Path("/app/backend/services/morning_brief.py").read_text()
    assert "REPLY INBOX" in src
    assert "daily_reply_summary" in src


# ── FIX 4 — Proactive outreach run-row ────────────────────────────


def test_proactive_outreach_stamps_run_row():
    src = Path("/app/backend/services/proactive_outreach.py").read_text()
    assert "proactive_outreach_runs" in src
    assert "FIX 4" in src or "iter 330" in src


# ── FIX 5 — Outreach Health snapshot ──────────────────────────────


def test_outreach_health_module_exists():
    from services import outreach_health
    assert callable(outreach_health.outreach_health_snapshot)


@pytest.mark.asyncio
async def test_outreach_health_returns_7_channels_with_empty_db(monkeypatch):
    monkeypatch.setenv("SMS_DISABLED", "true")
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "true")
    monkeypatch.setenv("TWILIO_WA_FROM_NUMBER", "")
    monkeypatch.setenv("RETELL_API_KEY", "test")

    from services.outreach_health import outreach_health_snapshot

    class EmptyCursor:
        def limit(self, n): return self
        def sort(self, *a, **k): return self
        async def to_list(self, length=None): return []
        def __aiter__(self):
            self._d = False
            return self
        async def __anext__(self):
            if not self._d:
                self._d = True
                raise StopAsyncIteration
            raise StopAsyncIteration

    class Coll:
        def find(self, q=None, p=None): return EmptyCursor()
        async def find_one(self, *a, **k): return None
        async def count_documents(self, q): return 0

    class DB:
        def __init__(self):
            for name in (
                "outreach_history", "campaign_leads", "do_not_contact",
                "hunt_commands", "proactive_outreach_log", "proactive_outreach_runs",
                "social_autopilot_posts", "closer_day5_runs", "reply_inbox_actions",
            ):
                setattr(self, name, Coll())

    snap = await outreach_health_snapshot(DB())
    assert snap["ok"] is True
    assert len(snap["channels"]) == 7
    labels = {c["label"] for c in snap["channels"]}
    assert labels == {
        "Email", "WhatsApp", "SMS", "Voice (Retell)",
        "Daily Hunt", "Proactive Follow-up", "Social (LinkedIn)",
    }
    assert snap["overall"] in ("green", "yellow", "red")


def test_outreach_admin_router_exposes_endpoints():
    src = Path("/app/backend/routers/outreach_admin_router.py").read_text()
    for p in ("/health", "/closer-day5/run", "/reply-inbox/run", "/social/post-now"):
        assert p in src


def test_outreach_admin_router_registered():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "routers.outreach_admin_router" in src


def test_frontend_outreach_card_has_testids():
    src = Path("/app/frontend/src/platform/admin/OutreachHealthCard.jsx").read_text()
    for tid in ("outreach-health-card", "outreach-overall-status",
                  "outreach-refresh", "outreach-run-reply-inbox",
                  "outreach-action-msg"):
        assert f'data-testid="{tid}"' in src


def test_outreach_card_mounted_in_cockpit():
    src = Path("/app/frontend/src/platform/admin/OraCtoCockpit.jsx").read_text()
    assert "OutreachHealthCard" in src
    assert "<OutreachHealthCard" in src


# ── FIX 6 — Social autopilot ──────────────────────────────────────


def test_social_autopilot_exists_with_5_topics():
    from services import social_autopilot
    assert callable(social_autopilot.run_daily_social_post)
    # 5 weekday topics + 2 weekend skips.
    weekday_topics = [v for v in social_autopilot.TOPIC_ROTATION.values() if v]
    assert len(weekday_topics) == 5
    assert "success_story" in weekday_topics
    assert "founder_voice" in weekday_topics


@pytest.mark.asyncio
async def test_social_autopilot_skips_weekend(monkeypatch):
    from services import social_autopilot

    class FakeTorontoNow:
        weekday = lambda self: 5   # Saturday
        def strftime(self, _): return "2026-02-28"
    async def fake_now():
        return FakeTorontoNow()
    monkeypatch.setattr(social_autopilot, "_toronto_now", fake_now)

    class Coll:
        async def find_one(self, *a, **k): return None
        async def insert_one(self, d): pass

    class DB:
        social_autopilot_posts = Coll()

    out = await social_autopilot.run_daily_social_post(DB())
    assert out.get("ok") is True
    assert out.get("skipped") is True


@pytest.mark.asyncio
async def test_social_autopilot_idempotent_same_day(monkeypatch):
    from services import social_autopilot

    class WeekdayNow:
        def weekday(self): return 1   # Tuesday
        def strftime(self, _): return "2026-02-24"
    async def fake_now(): return WeekdayNow()
    monkeypatch.setattr(social_autopilot, "_toronto_now", fake_now)

    class Coll:
        async def find_one(self, q):
            return {"day_id": q.get("day_id"), "topic_key": "practical_tip"}
        async def insert_one(self, d): pass

    class DB:
        social_autopilot_posts = Coll()

    out = await social_autopilot.run_daily_social_post(DB())
    assert out.get("skipped") is True
    assert out.get("reason") == "already posted today"


def test_social_cron_wired_at_10_toronto():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_social_autopilot" in src
    assert 'pytz.timezone("America/Toronto")' in src
    assert "run_daily_social_post" in src


def test_morning_brief_includes_social_line():
    src = Path("/app/backend/services/morning_brief.py").read_text()
    assert "SOCIAL" in src
    assert "latest_social_post_line" in src
