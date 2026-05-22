"""
test_iter326ii_jj_cockpit_seed_and_frontend_surfaces.py
══════════════════════════════════════════════════════════════════════════════
iter 326ii  — ORA Watchdog Cockpit + four UI surfaces
iter 326jj  — Skills marketplace seed (5 reference skills)

WHAT THIS TEST LOCKS IN
───────────────────────
  Backend
    • SEED_SKILLS has the 5 promised reference skills with stable IDs
    • ensure_seed_skills inserts missing skills, skips existing ones
    • Seed is hooked into registry.py startup path

  Frontend (file-level smoke — full e2e is a separate playwright run)
    • OraWatchdogCockpit.jsx mounts all 4 cards
    • VoiceProfileEditor.jsx exists + uses correct endpoint + has testids
    • SkillsMarketplace.jsx exists + uses correct endpoint + has testids
    • MorningBriefMobile.jsx exists + uses correct endpoint + has testids
    • MorningBriefCard.jsx exists for the cockpit grid
    • App.js registers the 4 new routes

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326ii_jj_cockpit_seed_and_frontend_surfaces.py -v
"""
from __future__ import annotations

import pathlib
import re

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# iter 326jj — Skills marketplace seed
# ─────────────────────────────────────────────────────────────────────────────
def test_seed_has_five_reference_skills_with_stable_ids():
    from services.ora_skills_seed import SEED_SKILLS
    assert len(SEED_SKILLS) == 5
    ids = {s["skill_id"] for s in SEED_SKILLS}
    expected = {
        "aurem-gst-hst-filing",
        "aurem-wsib-compliance",
        "aurem-gta-seasonal-campaigns",
        "aurem-roofer-snow-clearing-pack",
        "aurem-dental-recall-reminders",
    }
    assert ids == expected, f"id mismatch — got {ids - expected} extra / missing {expected - ids}"


def test_seed_skills_have_required_fields():
    from services.ora_skills_seed import SEED_SKILLS
    for s in SEED_SKILLS:
        for k in ("skill_id", "name", "description", "category",
                  "manifest", "content"):
            assert k in s, f"{s.get('skill_id')} missing field {k}"
        # All skills are free for the v1 seed
        assert s.get("pricing", {}).get("model") == "free"


@pytest.mark.asyncio
async def test_ensure_seed_skills_idempotent_and_inserts_missing(monkeypatch):
    """First call inserts all 5. Second call skips all 5 (no duplicates)."""
    from services import ora_skills as sk
    from services.ora_skills_seed import ensure_seed_skills

    # Use the lightweight fake DB pattern from other Phase 3 tests
    class _Coll:
        def __init__(self): self.docs = {}
        async def create_index(self, *a, **kw): return "idx"
        async def insert_one(self, doc):
            key = doc.get("skill_id") or doc.get("_id")
            self.docs[key] = doc
            return type("R", (), {"inserted_id": key})
        async def find_one(self, filt, projection=None):
            for d in self.docs.values():
                if all(d.get(k) == v for k, v in filt.items()):
                    return dict(d)
            return None
        async def update_one(self, filt, update, upsert=False):
            for d in self.docs.values():
                if all(d.get(k) == v for k, v in filt.items()):
                    for sk2, sv in (update.get("$set") or {}).items():
                        d[sk2] = sv
                    for sk2, sv in (update.get("$inc") or {}).items():
                        d[sk2] = (d.get(sk2) or 0) + sv
                    for sk2, sv in (update.get("$push") or {}).items():
                        d.setdefault(sk2, []).append(sv)
                    return type("R", (), {"matched_count": 1, "modified_count": 1})
            return type("R", (), {"matched_count": 0, "modified_count": 0})

    class _DB:
        def __init__(self):
            self.ora_skills = _Coll()
            self.tenant_installed_skills = _Coll()
        def __getitem__(self, name):
            return getattr(self, name)

    fake = _DB()
    sk.set_db(fake)

    r1 = await ensure_seed_skills()
    assert r1["ok"] is True
    assert r1["created"] == 5
    assert r1["skipped"] == 0
    assert r1["failed"] == 0

    r2 = await ensure_seed_skills()
    assert r2["ok"] is True
    assert r2["created"] == 0       # already there
    assert r2["skipped"] == 5
    assert r2["failed"] == 0


def test_registry_wires_seed_on_startup():
    """The seed must be triggered when the backend boots, otherwise
    the marketplace would stay empty until a manual call. iter 326jj
    moved this from registry.py (sync) to server.py startup_event so
    it runs in an active event loop."""
    p = pathlib.Path("/app/backend/server.py")
    src = p.read_text()
    assert "ensure_seed_skills" in src, (
        "server.py startup_event must call ensure_seed_skills so the "
        "marketplace is seeded on first boot."
    )
    # Verify the phase3 router is still registered
    reg = pathlib.Path("/app/backend/routers/registry.py").read_text()
    assert "ora_phase3_router" in reg


# ─────────────────────────────────────────────────────────────────────────────
# iter 326ii — Frontend surface smoke checks
# ─────────────────────────────────────────────────────────────────────────────
_FRONT = pathlib.Path("/app/frontend/src/platform/admin")
_APP   = pathlib.Path("/app/frontend/src/App.js")

FRONT_FILES = {
    "OraWatchdogCockpit.jsx":  ["/api/admin/ora/cost-summary",
                                "/api/admin/ora/email-health",
                                "/api/admin/ora/morning-brief"],   # via children
    "VoiceProfileEditor.jsx":  ["/api/admin/ora/voice-profile/"],
    "SkillsMarketplace.jsx":   ["/api/admin/ora/skills"],
    "MorningBriefMobile.jsx":  ["/api/admin/ora/morning-brief"],
    "MorningBriefCard.jsx":    ["/api/admin/ora/morning-brief"],
}


@pytest.mark.parametrize("fname", list(FRONT_FILES.keys()))
def test_frontend_file_exists(fname):
    assert (_FRONT / fname).exists(), f"missing {fname}"


def test_voice_profile_editor_endpoints_and_testids():
    src = (_FRONT / "VoiceProfileEditor.jsx").read_text()
    assert "/api/admin/ora/voice-profile/" in src
    assert "method: \"PUT\"" in src or "method: 'PUT'" in src
    for tid in ("voice-profile-editor", "voice-tenant-input",
                "voice-load-btn", "voice-save-btn",
                "voice-tone-chips", "voice-formality-chips",
                "voice-industry-select"):
        assert f'data-testid="{tid}"' in src, f"missing testid {tid}"


def test_skills_marketplace_endpoints_and_testids():
    src = (_FRONT / "SkillsMarketplace.jsx").read_text()
    assert "/api/admin/ora/skills" in src
    assert "/install" in src
    for tid in ("skills-marketplace", "skills-filters",
                "skills-grid", "skills-install-btn"):
        assert f'data-testid="{tid}"' in src, f"missing testid {tid}"


def test_morning_brief_mobile_uses_correct_endpoint():
    src = (_FRONT / "MorningBriefMobile.jsx").read_text()
    assert "/api/admin/ora/morning-brief" in src
    for tid in ("morning-brief-mobile", "morning-brief-mobile-kpis",
                "morning-brief-mobile-refresh"):
        assert f'data-testid="{tid}"' in src, f"missing testid {tid}"


def test_watchdog_cockpit_mounts_all_four_cards():
    src = (_FRONT / "OraWatchdogCockpit.jsx").read_text()
    for child in ("DailySpendCard", "EmailHealthCard",
                  "MorningBriefCard", "RecentDecisionsPanel"):
        assert child in src, f"cockpit must mount {child}"
    assert 'data-testid="ora-watchdog-cockpit"' in src
    assert 'data-testid="ora-watchdog-grid"' in src


def test_app_js_registers_four_new_routes():
    src = _APP.read_text()
    for route in (
        "/admin/ora-watchdog",
        "/admin/ora-voice",
        "/admin/ora-skills",
        "/admin/morning-brief",
    ):
        assert f'path="{route}"' in src, f"missing route {route}"
    for component in (
        "OraWatchdogCockpit",
        "VoiceProfileEditor",
        "SkillsMarketplace",
        "MorningBriefMobile",
    ):
        assert f"import {component}" in src, f"missing import {component}"


def test_all_frontend_files_use_admin_token():
    """No customer-token fallback in these admin surfaces — protects
    the iter 326q auth-separation fix. (Cockpit is pure composition
    with no fetches of its own — token use lives in the child cards.)"""
    for fname in FRONT_FILES:
        if fname == "OraWatchdogCockpit.jsx":
            continue
        src = (_FRONT / fname).read_text()
        assert "aurem_admin_token" in src, (
            f"{fname} must use aurem_admin_token (admin scope), not a "
            f"generic customer token."
        )
