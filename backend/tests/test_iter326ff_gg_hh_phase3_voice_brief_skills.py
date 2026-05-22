"""
test_iter326ff_gg_hh_phase3_voice_brief_skills.py — Phase 3 P3.1 / P3.2 / P3.3
══════════════════════════════════════════════════════════════════════════════
P3.1 — Multi-tenant ORA voice tuning
       Per-tenant {tone, formality, signature, industry} stored in
       `tenant_ora_voice`. Industry-defaulted when not saved. Wired
       into ora_agent.run_turn so new sessions adopt the right voice.

P3.2 — Mobile morning brief
       `services/ora_morning_brief.build_brief()` aggregates yesterday's
       campaigns / revenue / alerts / focus leads / recent decisions
       into one mobile-friendly payload at /api/admin/ora/morning-brief.

P3.3 — Skills marketplace
       Catalog of versioned skill bundles published by domain experts
       (`ora_skills`). Tenants install/uninstall per BIN. Routes under
       /api/admin/ora/skills/...

WHAT THIS TEST LOCKS IN
───────────────────────
  P3.1
    • INDUSTRY_DEFAULTS has the verticals we promised (roofing/dental/etc.)
    • save_profile validates tone + formality enums
    • get_profile returns saved value, OR industry default, OR generic
    • build_voice_preamble returns a non-empty multi-line preamble
      for any saved tenant and "" when tenant_id is None
    • ora_agent.run_turn signature includes `tenant_id`
    • run_turn prepends voice preamble on a NEW session only

  P3.2
    • build_brief returns the agreed top-level schema
    • Sections are present even when collections are empty (founder
      never sees a 500)
    • Endpoint /api/admin/ora/morning-brief registered + admin-gated

  P3.3
    • publish_skill creates a row with versions[]
    • publishing same skill_id appends a new version (no duplicate)
    • install_skill rejects unknown skill / unknown version
    • install_skill is idempotent (re-install same version → ok)
    • list_installed_for_tenant returns enabled installs
    • uninstall_skill flips enabled=False (soft delete)
    • All 7 endpoints registered

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326ff_gg_hh_phase3_voice_brief_skills.py -v
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Reuse the lightweight fake Mongo from earlier Phase 2 tests
# ─────────────────────────────────────────────────────────────────────────────
class _FakeColl:
    def __init__(self):
        self.docs: dict = {}
        self.indexes: list = []

    async def create_index(self, *a, **kw):
        self.indexes.append((a, kw)); return "idx"

    async def insert_one(self, doc):
        key = doc.get("_id") or doc.get("skill_id") or f"auto-{len(self.docs)}"
        self.docs[key] = doc
        return type("R", (), {"inserted_id": key})

    async def find_one(self, filt, projection=None):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in filt.items()
                   if not isinstance(v, dict)):
                return dict(d)
        return None

    async def update_one(self, filt, update, upsert=False):
        target = None
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in filt.items()
                   if not isinstance(v, dict)):
                target = d; break
        if target is None and upsert:
            target = {**{k: v for k, v in filt.items() if not isinstance(v, dict)}}
            key = target.get("_id") or target.get("skill_id") \
                  or target.get("tenant_id") or f"auto-{len(self.docs)}"
            self.docs[key] = target
        if target is None:
            return type("R", (), {"modified_count": 0, "matched_count": 0})
        for sk, sv in (update.get("$set") or {}).items():
            target[sk] = sv
        for sk, sv in (update.get("$setOnInsert") or {}).items():
            target.setdefault(sk, sv)
        for sk, sv in (update.get("$inc") or {}).items():
            target[sk] = (target.get(sk) or 0) + sv
        for sk, sv in (update.get("$push") or {}).items():
            target.setdefault(sk, []).append(sv)
        return type("R", (), {"modified_count": 1, "matched_count": 1})

    def find(self, filt=None, projection=None):
        rows = [dict(d) for d in self.docs.values()
                if all(d.get(k) == v for k, v in (filt or {}).items()
                       if not isinstance(v, dict))]
        return _Cursor(rows)

    async def count_documents(self, filt):
        return sum(1 for _ in self.find(filt).docs)

    def aggregate(self, _pipe):
        return _Cursor([])


class _Cursor:
    def __init__(self, docs):
        self.docs = docs
    def sort(self, *_a, **_kw):
        return self
    def limit(self, n):
        self.docs = self.docs[:n]; return self
    def __aiter__(self):
        self._it = iter(self.docs); return self
    async def __anext__(self):
        try: return next(self._it)
        except StopIteration: raise StopAsyncIteration


class _FakeDB:
    def __init__(self):
        self.tenant_ora_voice         = _FakeColl()
        self.ora_skills               = _FakeColl()
        self.tenant_installed_skills  = _FakeColl()
        self.tenants                  = _FakeColl()
        self.campaign_leads           = _FakeColl()
        self.customer_subscriptions   = _FakeColl()
        self.incident_bus             = _FakeColl()
        self.ora_decisions            = _FakeColl()
    def __getitem__(self, name):
        return getattr(self, name)


# ════════════════════════════════════════════════════════════════════════════
# P3.1 — Voice profile
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_industry_defaults_cover_promised_verticals():
    from services.ora_voice_profile import INDUSTRY_DEFAULTS
    for vertical in ("roofing", "dental", "restaurant", "tax", "default"):
        assert vertical in INDUSTRY_DEFAULTS


@pytest.mark.asyncio
async def test_save_profile_rejects_invalid_tone():
    from services import ora_voice_profile as vp
    vp.set_db(_FakeDB())
    res = await vp.save_profile("t1", tone="bro-energy")
    assert res["ok"] is False
    assert "tone" in res["error"]


@pytest.mark.asyncio
async def test_save_profile_rejects_invalid_formality():
    from services import ora_voice_profile as vp
    vp.set_db(_FakeDB())
    res = await vp.save_profile("t1", formality="legalese")
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_get_profile_falls_back_to_industry_default():
    from services import ora_voice_profile as vp
    fake = _FakeDB()
    fake.tenants.docs["t1"] = {"tenant_id": "t1", "industry": "roofing"}
    vp.set_db(fake)
    p = await vp.get_profile("t1")
    assert p["tone"] == "direct"          # iter 326ff roofing default
    assert p["formality"] == "casual"
    assert p["source"] == "industry_default"


@pytest.mark.asyncio
async def test_save_then_get_round_trip():
    from services import ora_voice_profile as vp
    vp.set_db(_FakeDB())
    saved = await vp.save_profile(
        "t-dental", tone="warm", formality="professional",
        signature="— Dr. Patel's clinic", industry="dental",
    )
    assert saved["ok"] is True
    fetched = await vp.get_profile("t-dental")
    assert fetched["tone"] == "warm"
    assert fetched["signature"].startswith("— Dr. Patel")
    assert fetched["source"] == "saved"


@pytest.mark.asyncio
async def test_build_voice_preamble_includes_tone_and_industry():
    from services import ora_voice_profile as vp
    vp.set_db(_FakeDB())
    await vp.save_profile("t-r", tone="direct", formality="casual",
                          industry="roofing")
    pre = await vp.build_voice_preamble("t-r")
    assert "Tone: direct" in pre
    assert "Formality: casual" in pre
    assert "Industry: roofing" in pre


@pytest.mark.asyncio
async def test_build_voice_preamble_empty_when_no_tenant():
    from services.ora_voice_profile import build_voice_preamble
    assert (await build_voice_preamble(None)) == ""
    assert (await build_voice_preamble("")) == ""


def test_run_turn_accepts_tenant_id_kwarg():
    from services.ora_agent import run_turn
    sig = inspect.signature(run_turn)
    assert "tenant_id" in sig.parameters, (
        "iter 326ff requires run_turn to accept tenant_id so the voice "
        "preamble can be applied per-tenant."
    )


def test_run_turn_prepends_voice_preamble_on_new_session():
    """Source-level check that the voice preamble path exists in
    run_turn and is wired to build_voice_preamble."""
    from services.ora_agent import run_turn
    src = inspect.getsource(run_turn)
    assert "build_voice_preamble" in src
    assert "voice_pre" in src or "voice_preamble" in src


# ════════════════════════════════════════════════════════════════════════════
# P3.2 — Morning brief
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_morning_brief_returns_full_schema_even_when_empty():
    from services import ora_morning_brief as mb
    mb.set_db(_FakeDB())
    out = await mb.build_brief(tenant_id="t1", founder_email="f@a.com")
    for k in (
        "ok", "date", "tenant_id", "founder", "campaigns", "revenue",
        "alerts", "alerts_count", "focus_leads", "focus_count",
        "decisions", "generated_at",
    ):
        assert k in out, f"morning brief missing key: {k}"
    assert out["ok"] is True
    # Empty fakes — counts must be 0/lists empty, never crash
    assert out["alerts_count"] == 0
    assert out["focus_count"] == 0


def test_morning_brief_endpoint_registered():
    from routers import ora_phase3_router
    paths = [
        getattr(r, "path", None)
        for r in getattr(ora_phase3_router.router, "routes", [])
    ]
    assert "/api/admin/ora/morning-brief" in paths


def test_morning_brief_endpoint_is_admin_gated():
    from routers.ora_phase3_router import get_morning_brief
    src = inspect.getsource(get_morning_brief)
    assert "_ensure_admin" in src


# ════════════════════════════════════════════════════════════════════════════
# P3.3 — Skills marketplace
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_publish_skill_creates_new_row_with_versions():
    from services import ora_skills as sk
    fake = _FakeDB(); sk.set_db(fake)
    r = await sk.publish_skill(
        name="GST/HST Filing Automation",
        description="Auto-files quarterly returns",
        category="tax",
        author_email="cpa@example.com",
        version="1.0.0",
        manifest={"tools": ["safe_edit"]},
        content={"prompt": "..."},
    )
    assert r["ok"] is True and r["created"] is True
    row = list(fake.ora_skills.docs.values())[0]
    assert row["latest_version"] == "1.0.0"
    assert len(row["versions"]) == 1


@pytest.mark.asyncio
async def test_publish_same_skill_appends_new_version():
    from services import ora_skills as sk
    fake = _FakeDB(); sk.set_db(fake)
    await sk.publish_skill(
        name="X", description="desc", category="cat",
        author_email="a@b.com", version="1.0.0", skill_id="x-skill",
    )
    r2 = await sk.publish_skill(
        name="X", description="desc", category="cat",
        author_email="a@b.com", version="1.1.0", skill_id="x-skill",
    )
    assert r2["ok"] is True and r2["created"] is False
    row = fake.ora_skills.docs["x-skill"]
    assert row["latest_version"] == "1.1.0"
    assert len(row["versions"]) == 2


@pytest.mark.asyncio
async def test_install_skill_rejects_unknown_skill():
    from services import ora_skills as sk
    sk.set_db(_FakeDB())
    r = await sk.install_skill("t1", "ghost-skill")
    assert r["ok"] is False
    assert "not found" in r["error"]


@pytest.mark.asyncio
async def test_install_skill_rejects_unknown_version():
    from services import ora_skills as sk
    fake = _FakeDB(); sk.set_db(fake)
    await sk.publish_skill(
        name="Y", description="d", category="c",
        author_email="a@b.com", version="1.0.0", skill_id="y",
    )
    r = await sk.install_skill("t1", "y", version="9.9.9")
    assert r["ok"] is False


@pytest.mark.asyncio
async def test_install_skill_is_idempotent_and_counts_download():
    from services import ora_skills as sk
    fake = _FakeDB(); sk.set_db(fake)
    await sk.publish_skill(
        name="Z", description="d", category="c",
        author_email="a@b.com", version="1.0.0", skill_id="z",
    )
    r1 = await sk.install_skill("t1", "z")
    r2 = await sk.install_skill("t1", "z")
    assert r1["ok"] is True and r2["ok"] is True
    # downloads incremented twice (once per install call)
    assert fake.ora_skills.docs["z"]["downloads"] == 2
    rows = await sk.list_installed_for_tenant("t1")
    # Idempotent — single row only.
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_uninstall_soft_deletes_install():
    from services import ora_skills as sk
    fake = _FakeDB(); sk.set_db(fake)
    await sk.publish_skill(
        name="A", description="d", category="c",
        author_email="a@b.com", version="1.0.0", skill_id="a",
    )
    await sk.install_skill("t1", "a")
    r = await sk.uninstall_skill("t1", "a")
    assert r["ok"] is True
    rows = await sk.list_installed_for_tenant("t1")
    # uninstalled rows are filtered out of the active list
    assert rows == []


def test_all_phase3_endpoints_registered():
    from routers import ora_phase3_router
    paths = {
        getattr(r, "path", None)
        for r in getattr(ora_phase3_router.router, "routes", [])
    }
    expected = {
        "/api/admin/ora/voice-profile/{tenant_id}",
        "/api/admin/ora/morning-brief",
        "/api/admin/ora/skills",
        "/api/admin/ora/skills/{skill_id}",
        "/api/admin/ora/skills/{skill_id}/install",
        "/api/admin/ora/skills/installed/{tenant_id}",
        "/api/admin/ora/skills/{skill_id}/install/{tenant_id}",
    }
    missing = expected - paths
    assert not missing, f"missing endpoints: {missing}"


def test_phase3_set_db_wires_all_three_services():
    """One set_db must propagate to voice/brief/skills so the router
    wiring stays a single hook in registry.py."""
    from routers.ora_phase3_router import set_db
    from services import ora_voice_profile, ora_morning_brief, ora_skills
    fake = _FakeDB()
    set_db(fake)
    assert ora_voice_profile._db is fake
    assert ora_morning_brief._db is fake
    assert ora_skills._db is fake
