"""
Scout webclaw integration test (iter 282ad).

Runs only when WEBCLAW_API_KEY is configured — otherwise tests exercise
the graceful local-first fallback path (legacy httpx scraper).
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.website_scraper import scan_website  # noqa: E402
from services.webclaw_client import is_configured  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if sys.version_info < (3, 10) else asyncio.run(coro)


def test_scan_returns_content():
    result = _run(scan_website("https://example.com"))
    assert result["status"] in ("success", "skipped"), f"got {result}"
    if result["status"] == "success":
        if is_configured():
            # webclaw path returns markdown content
            assert result.get("content") and len(result["content"]) > 100, \
                f"expected >100 chars of markdown, got {len(result.get('content') or '')}"
        else:
            # legacy path has empty content but should carry contacts dict
            assert result.get("contacts") is not None, "legacy fallback must return contacts"


def test_scan_handles_bad_url():
    result = _run(scan_website("https://this-domain-does-not-exist-xyz-123.com"))
    # Legacy fallback returns status=success with empty contacts; webclaw
    # raises → status=failed. Both are correct behaviours of the contract.
    assert result["status"] in ("failed", "success")
    assert result["source_url"].endswith(".com")


def test_brand_extraction():
    if not is_configured():
        pytest.skip("WEBCLAW_API_KEY not set — brand extraction requires webclaw")
    result = _run(scan_website("https://stripe.com"))
    assert result["status"] == "success"
    assert "brand" in result
    assert result["brand"] is not None


# ═════════════════════════════════════════════════════════════════════
# iter 282ae — Prompt 2: brand injection + usage log
# ═════════════════════════════════════════════════════════════════════
from services.brand_injection import (  # noqa: E402
    DEFAULT_BRAND_FONT,
    DEFAULT_BRAND_PRIMARY,
    build_usage_doc,
    inject_brand_css,
)


def test_brand_injection_uses_defaults_when_no_brand():
    # simulate scan with no brand data
    mock_result = {"status": "success", "brand": None, "content": "x"}
    css = inject_brand_css(mock_result)
    assert f"--brand-primary: {DEFAULT_BRAND_PRIMARY}" in css
    assert "--brand-font:" in css


def test_brand_injection_uses_brand_when_present():
    mock = {
        "status": "success",
        "brand": {"colors": [{"hex": "#ff5500"}], "fonts": [{"family": "Poppins"}]},
    }
    css = inject_brand_css(mock)
    assert "--brand-primary: #ff5500" in css
    assert "Poppins" in css


def test_usage_log_structure():
    doc = build_usage_doc("https://example.com", "webclaw", "some content", True, False)
    for key in ("url", "source", "content_length", "brand_extracted",
                "contacts_extracted", "ts", "date"):
        assert key in doc, f"missing {key}"
    assert doc["source"] == "webclaw"
    assert doc["content_length"] == len("some content")
    assert doc["brand_extracted"] is True
    assert doc["contacts_extracted"] is False
    assert len(doc["date"]) == 10  # YYYY-MM-DD


# ═════════════════════════════════════════════════════════════════════
# iter 282af — Prompt 3: diff tracking + rollup
# ═════════════════════════════════════════════════════════════════════
from services.website_diff import (  # noqa: E402
    build_rollup_doc,
    compute_word_count_delta,
    simulate_first_diff,
)


def test_diff_returns_no_change_on_first_scan():
    result = simulate_first_diff("https://example.com")
    assert result["changed"] is False
    assert result["last_snapshot_ts"] is None
    assert result["url"] == "https://example.com"


def test_diff_detects_word_count_change():
    old = {"content": "hello world", "word_count": 2}
    new = {"content": "hello world foo bar baz", "word_count": 5}
    delta = compute_word_count_delta(old, new)
    assert delta == 3


def test_rollup_doc_structure():
    doc = build_rollup_doc("2026-05-01", 10, 0.8, 0.6, 1200)
    assert doc["date"] == "2026-05-01"
    assert doc["count"] == 10
    assert doc["brand_rate"] == 0.8
    assert doc["contacts_rate"] == 0.6
    assert "avg_content_length" in doc
    assert doc["avg_content_length"] == 1200


# ═════════════════════════════════════════════════════════════════════
# iter 282ag — Prompt 4: active site change watcher
# ═════════════════════════════════════════════════════════════════════
from services.site_change_watcher import (  # noqa: E402
    build_trigger_doc,
    build_watcher_summary,
    run_weekly_site_watch_sync,
)


class _MockDB:  # minimal async-shaped stub, never actually awaited
    pass


def test_watcher_skips_when_no_key(monkeypatch):
    monkeypatch.delenv("WEBCLAW_API_KEY", raising=False)
    result = run_weekly_site_watch_sync(_MockDB())
    assert result.get("skipped") == "webclaw_not_configured"


def test_watcher_summary_structure():
    summary = build_watcher_summary(10, 2, 2, 0)
    assert summary["leads_checked"] == 10
    assert summary["changes_detected"] == 2
    assert summary["outreach_fired"] == 2
    assert summary["skipped"] == 0
    assert "ts" in summary


def test_trigger_log_structure():
    doc = build_trigger_doc("lead_123", "https://example.com",
                             "new content snippet here", True)
    assert doc["lead_id"] == "lead_123"
    assert doc["url"] == "https://example.com"
    assert doc["outreach_fired"] is True
    assert "ts" in doc
    assert "date" in doc
    assert len(doc["date"]) == 10


# ═════════════════════════════════════════════════════════════════════
# iter 282ah — Prompt 5: tone tuner + schema drift migration
# ═════════════════════════════════════════════════════════════════════
from services.tone_tuner import get_outreach_tone  # noqa: E402
from services.schema_migrations import (  # noqa: E402
    fix_schema_drift_sync,
    guard_council_record,
    guard_outreach_entry,
)


def test_tone_high_rated_lead():
    lead = {"yelp_rating": 4.7, "review_count": 80}
    tone = get_outreach_tone(lead)
    assert "peer-level" in tone or "professional" in tone


def test_tone_struggling_lead():
    lead = {"yelp_rating": 3.0, "review_count": 3}
    tone = get_outreach_tone(lead)
    assert "empathetic" in tone or "solution" in tone


def test_tone_missing_fields():
    lead = {}
    tone = get_outreach_tone(lead)
    assert tone is not None
    assert "neutral" in tone or "professional" in tone


def test_tone_encouraging_mid_tier():
    lead = {"yelp_rating": 4.1, "review_count": 25}
    tone = get_outreach_tone(lead)
    assert "friendly" in tone or "encouraging" in tone


def test_guard_council_record_fills_required_fields():
    r = guard_council_record({"decision_id": "dec_123",
                                "action_kind": "outreach",
                                "decision": "approve"})
    assert r["lead_id"]
    assert r["created_at"]
    assert r["status"] == "approve"
    assert r["action"] == "outreach"
    assert r["agent"] == "ora"


def test_guard_outreach_entry_canonicalises():
    e = guard_outreach_entry({"type": "email", "sent_at": "2026-05-01T00:00:00Z"})
    assert e["channel"] == "email"
    assert e["dispatched_at"] == "2026-05-01T00:00:00Z"
    assert e["status"] == "unknown"


class _MockMotor:
    """Minimal async-mock mongo surface for migration idempotency test."""
    def __init__(self):
        self._applied = False

    class _Collection:
        def __init__(self, parent, kind):
            self.parent = parent
            self.kind = kind
        async def find_one(self, *a, **k):
            if self.kind == "migrations" and self.parent._applied:
                return {"_id": "282ah_schema_drift_v1"}
            return None
        def find(self, *a, **k):
            class _Cursor:
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    raise StopAsyncIteration
            return _Cursor()
        async def update_one(self, *a, upsert=False, **k):
            if self.kind == "migrations":
                self.parent._applied = True
            class R:
                pass
            return R()
        async def create_index(self, *a, **k):
            return "idx"

    def __getattr__(self, name):
        return _MockMotor._Collection(self, name)


def test_schema_fix_is_idempotent():
    db = _MockMotor()
    r1 = fix_schema_drift_sync(db)
    r2 = fix_schema_drift_sync(db)
    assert r1.get("skipped") != "already_applied"
    assert r2.get("skipped") == "already_applied"
    assert r2.get("fixed", 0) == 0
