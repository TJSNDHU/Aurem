"""
Engagement webhook tests — simulate Resend + WHAPI payloads end-to-end
without touching the internet.
"""
import os
import sys
import asyncio
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.lead_lifecycle_router import (  # noqa: E402
    resend_webhook, whapi_webhook, set_db, _find_lead_by_email, _find_lead_by_phone,
)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, q, projection=None):
        import re as _re

        def _match(d, cond):
            for k, v in cond.items():
                if k == "$or":
                    if not any(_match(d, sub) for sub in v):
                        return False
                    continue
                if isinstance(v, dict) and "$regex" in v:
                    pattern = v["$regex"]
                    flags = _re.IGNORECASE if "i" in v.get("$options", "") else 0
                    try:
                        if not _re.search(pattern, str(d.get(k, "")), flags):
                            return False
                    except Exception:
                        return False
                else:
                    if d.get(k) != v:
                        return False
            return True

        for d in self.docs:
            if _match(d, q):
                return d
        return None

    async def update_one(self, q, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                for k, items in (update.get("$push") or {}).items():
                    d.setdefault(k, [])
                    if isinstance(items, dict) and "$each" in items:
                        d[k].extend(items["$each"])
                    else:
                        d[k].append(items)
                for k, v in (update.get("$inc") or {}).items():
                    d[k] = d.get(k, 0) + v
                return


class FakeDB:
    def __init__(self):
        self.campaign_leads = FakeCollection()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_req(payload: dict):
    body = json.dumps(payload).encode()

    class _Req:
        headers = {}
        async def body(self):
            return body
    return _Req()


@pytest.fixture(autouse=True)
def _setup_db(monkeypatch):
    # Disable signature verification (no secret set in test env)
    monkeypatch.delenv("RESEND_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("WHAPI_WEBHOOK_SECRET", raising=False)
    db = FakeDB()
    set_db(db)
    # Seed 2 test leads
    db.campaign_leads.docs.append({
        "lead_id": "wh-email", "business_id": "AUR-FNDR-001",
        "email": "target@example.com", "phone": "+16135551111",
        "lifecycle_stage": "contacted",
        "verification": {"channel_gating": {"email": True}},
    })
    db.campaign_leads.docs.append({
        "lead_id": "wh-phone", "business_id": "AUR-FNDR-001",
        "email": "p@example.com", "phone": "+16135552222",
        "lifecycle_stage": "contacted",
    })
    return db


def test_email_opened_transitions_to_engaged(_setup_db):
    payload = {"type": "email.opened", "data": {"email_id": "e1", "to": ["target@example.com"]}}
    res = _run(resend_webhook(_make_req(payload)))
    assert res["received"] is True
    lead = next(d for d in _setup_db.campaign_leads.docs if d["lead_id"] == "wh-email")
    assert lead["lifecycle_stage"] == "engaged"


def test_email_clicked_boosts_flame(_setup_db):
    payload = {"type": "email.clicked", "data": {"email_id": "e2", "to": ["target@example.com"], "click": {"link": "x"}}}
    _run(resend_webhook(_make_req(payload)))
    lead = next(d for d in _setup_db.campaign_leads.docs if d["lead_id"] == "wh-email")
    assert lead.get("flame_score_boost", 0) == 20


def test_email_complained_sets_dnc(_setup_db):
    payload = {"type": "email.complained", "data": {"email_id": "e3", "to": ["target@example.com"]}}
    _run(resend_webhook(_make_req(payload)))
    lead = next(d for d in _setup_db.campaign_leads.docs if d["lead_id"] == "wh-email")
    assert lead.get("dnc") is True


def test_email_to_unknown_lead_returns_matched_false(_setup_db):
    payload = {"type": "email.opened", "data": {"email_id": "e4", "to": ["unknown@example.com"]}}
    res = _run(resend_webhook(_make_req(payload)))
    assert res.get("matched_lead") is False


def test_whapi_read_transitions_to_engaged(_setup_db):
    payload = {"statuses": [{"status": "read", "id": "msg1", "recipient_id": "16135552222@s.whatsapp.net"}]}
    res = _run(whapi_webhook(_make_req(payload)))
    assert res["received"] is True
    lead = next(d for d in _setup_db.campaign_leads.docs if d["lead_id"] == "wh-phone")
    assert lead["lifecycle_stage"] == "engaged"


def test_whapi_inbound_transitions_to_following_up(_setup_db):
    payload = {"messages": [{"from": "16135552222@s.whatsapp.net", "from_me": False,
                             "text": {"body": "Yes I'm interested!"}}]}
    res = _run(whapi_webhook(_make_req(payload)))
    assert res["received"] is True
    lead = next(d for d in _setup_db.campaign_leads.docs if d["lead_id"] == "wh-phone")
    assert lead["lifecycle_stage"] == "following_up"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
