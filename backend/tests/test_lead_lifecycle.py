"""
Lead Lifecycle state-machine tests.
No live integrations — uses FakeDB.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.lead_lifecycle import transition, STAGES, ALLOWED  # noqa: E402


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, q, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return d
        return None

    async def update_one(self, q, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                for k, items in (update.get("$push") or {}).items():
                    d.setdefault(k, [])
                    if isinstance(items, dict) and "$each" in items:
                        d[k].extend(items["$each"])
                    else:
                        d[k].append(items)
                return
        if upsert:
            nd = {**q}
            nd.update(update.get("$set") or {})
            self.docs.append(nd)


class FakeDB:
    def __init__(self):
        self.campaign_leads = FakeCollection()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_valid_transition():
    db = FakeDB()
    db.campaign_leads.docs.append({"lead_id": "l1", "lifecycle_stage": "new"})
    r = _run(transition(db, "l1", "contacted", reason="campaign"))
    assert r["ok"] is True
    assert r["to"] == "contacted"


def test_invalid_transition_blocked():
    db = FakeDB()
    db.campaign_leads.docs.append({"lead_id": "l2", "lifecycle_stage": "won"})
    # won is terminal — can't go back
    r = _run(transition(db, "l2", "contacted"))
    assert r["ok"] is False


def test_force_override_allowed():
    db = FakeDB()
    db.campaign_leads.docs.append({"lead_id": "l3", "lifecycle_stage": "won"})
    r = _run(transition(db, "l3", "contacted", force=True))
    assert r["ok"] is True


def test_called_no_response_starts_drip():
    db = FakeDB()
    db.campaign_leads.docs.append({"lead_id": "l4", "lifecycle_stage": "engaged"})
    r = _run(transition(db, "l4", "called_no_response", reason="flame_dial_failed"))
    assert r["ok"] is True
    lead = db.campaign_leads.docs[0]
    assert "drip.started_at" in lead
    assert lead.get("drip.next_step_day") == 1


def test_won_stops_drip():
    db = FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "l5", "lifecycle_stage": "following_up",
        "drip.next_step_day": 7, "drip.completed": False,
    })
    r = _run(transition(db, "l5", "won"))
    assert r["ok"] is True
    lead = db.campaign_leads.docs[0]
    assert lead.get("drip.completed") is True
    assert lead.get("drip.next_action_at") is None


def test_all_allowed_transitions_consistent():
    # Every stage in STAGES should have an ALLOWED entry
    for s in STAGES:
        assert s in ALLOWED


def test_skip_when_already_in_stage():
    db = FakeDB()
    db.campaign_leads.docs.append({"lead_id": "l6", "lifecycle_stage": "engaged"})
    r = _run(transition(db, "l6", "engaged"))
    assert r["ok"] is True
    assert r.get("skipped") == "already_in_stage"


if __name__ == "__main__":
    test_valid_transition()
    test_invalid_transition_blocked()
    test_force_override_allowed()
    test_called_no_response_starts_drip()
    test_won_stops_drip()
    test_all_allowed_transitions_consistent()
    test_skip_when_already_in_stage()
    print("All lifecycle tests passed")
