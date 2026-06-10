"""
D-77 Repair Plan HTML Email — Regression Tests.

Proves the branded deliverable renders correctly:
  * services/brand_emails.render_repair_plan produces valid HTML
  * Severity tones, score color, and item counts are wired through
  * Empty plan renders the honest "no items" notice (no fake rows)
  * customer_website_repair_router._email_repair_plan sends both text + html

NO MOCKS for template logic — we render real HTML and assert on the
output. Resend HTTP is the only thing we don't hit (we just verify
the payload structure was built).
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest


# ── 1. Brand-emails renderer ────────────────────────────────────────────────

def test_repair_plan_html_renders_with_real_plan():
    from services.brand_emails import render_repair_plan

    audit = {
        "overall_score": 47,
        "issues": [{"a": 1}, {"b": 2}, {"c": 3}],
    }
    plan = [
        {
            "issue_title": "HTTPS redirect missing",
            "severity": "high",
            "llm_response": "ROOT CAUSE: nginx server block lacks 301 redirect.\nFIX: add `return 301 https://...$request_uri;`",
        },
        {
            "issue_title": "Schema.org missing on homepage",
            "severity": "medium",
            "llm_response": "Add LocalBusiness JSON-LD in the <head>.",
        },
    ]
    html = render_repair_plan(
        customer_email="cust@example.ca",
        website="https://example.ca",
        audit=audit,
        plan=plan,
        first_name="Mike",
    )
    assert isinstance(html, str) and len(html) > 500
    # Required template tokens were replaced
    assert "{{" not in html, "unfilled template token leaked into output"
    # Personalization
    assert "Mike" in html
    assert "example.ca" in html
    # Counts
    assert ">2<" in html or ">02<" in html or ">2</div>" in html, "plan_count not surfaced"
    assert "47" in html, "score not surfaced"
    assert "3" in html, "issue_count not surfaced"
    # Item content
    assert "HTTPS redirect missing" in html
    assert "Schema.org missing on homepage" in html
    # Severity badges
    assert "HIGH" in html
    assert "MEDIUM" in html
    # AUREM brand footer
    assert "Polaris Built Inc" in html
    assert "aurem.live" in html.lower()


def test_repair_plan_score_color_thresholds():
    from services.brand_emails import _score_color
    assert _score_color(90) == "#22c55e"     # green
    assert _score_color(80) == "#22c55e"
    assert _score_color(79) == "#f59e0b"     # amber
    assert _score_color(50) == "#f59e0b"
    assert _score_color(49) == "#ef4444"     # red
    assert _score_color(0)  == "#ef4444"


def test_repair_plan_empty_plan_renders_honest_notice():
    from services.brand_emails import render_repair_plan
    html = render_repair_plan(
        customer_email="cust@example.ca",
        website="https://example.ca",
        audit={"overall_score": 88, "issues": []},
        plan=[],
        first_name=None,
    )
    assert "{{" not in html
    assert "No actionable items" in html
    # Falls back to "there" when first_name is None
    assert ">there<" in html or "Hi there" in html


def test_repair_plan_escapes_html_in_llm_body():
    """LLM output may contain <script> or angle brackets from a code
    block. The template MUST escape these so the email client doesn't
    render them as markup."""
    from services.brand_emails import render_repair_plan
    plan = [{
        "issue_title": "XSS escape test",
        "severity": "low",
        "llm_response": "<script>alert(1)</script> & a < b",
    }]
    html = render_repair_plan(
        customer_email="cust@example.ca",
        website="https://example.ca",
        audit={"overall_score": 95, "issues": []},
        plan=plan,
        first_name="Test",
    )
    assert "<script>alert(1)</script>" not in html, "raw script tag leaked"
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_repair_plan_severity_unknown_defaults_to_medium():
    """If LLM emits an unrecognized severity, badge falls back to MEDIUM."""
    from services.brand_emails import render_repair_plan
    plan = [{"issue_title": "X", "severity": "weird", "llm_response": "body"}]
    html = render_repair_plan(
        customer_email="cust@example.ca",
        website="https://example.ca",
        audit={"overall_score": 70, "issues": []},
        plan=plan,
        first_name="T",
    )
    # MEDIUM badge present
    assert re.search(r'>MEDIUM<', html), "fallback severity badge missing"


# ── 2. customer_website_repair_router sends both text + html ────────────────

@pytest.mark.asyncio
async def test_email_repair_plan_sends_html_when_render_succeeds(monkeypatch):
    """End-to-end: _email_repair_plan should attach an `html` field in
    its Resend payload when render_repair_plan succeeds."""
    import sys
    import types
    from routers import customer_website_repair_router as mod

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self): return {"id": "fake_email_id_d77"}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = _FakeClient
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setenv("RESEND_API_KEY", "fake-key-d77")

    res = await mod._email_repair_plan(
        customer_email="qa@aurem.live",
        website="https://qa.example.ca",
        plan=[{"issue_title": "T", "severity": "high",
               "llm_response": "fix this thing"}],
        audit={"overall_score": 50, "issues": [{}]},
        first_name="QA",
    )
    assert res["ok"] is True, f"got {res!r}"
    assert res["email_id"] == "fake_email_id_d77"
    assert res["html_sent"] is True
    payload = captured["json"]
    assert payload["to"] == ["qa@aurem.live"]
    assert "text" in payload and "AUREM Repair Plan" in payload["text"]
    assert "html" in payload and "AUREM" in payload["html"]
    # HTML payload should NOT be the same as text payload
    assert payload["html"] != payload["text"]


@pytest.mark.asyncio
async def test_email_repair_plan_no_plan_returns_error():
    from routers import customer_website_repair_router as mod
    res = await mod._email_repair_plan(
        customer_email="qa@aurem.live",
        website="https://qa.example.ca",
        plan=[],
        audit={"overall_score": 50, "issues": []},
    )
    assert res == {"ok": False, "error": "no_plan_items_to_email"}


@pytest.mark.asyncio
async def test_email_repair_plan_no_resend_key_returns_error():
    from routers import customer_website_repair_router as mod
    with patch.dict("os.environ", {}, clear=False):
        # explicitly delete the var if present
        import os
        prev = os.environ.pop("RESEND_API_KEY", None)
        try:
            res = await mod._email_repair_plan(
                customer_email="qa@aurem.live",
                website="https://qa.example.ca",
                plan=[{"issue_title": "T", "severity": "low",
                       "llm_response": "x"}],
                audit={"overall_score": 90, "issues": []},
            )
        finally:
            if prev is not None:
                os.environ["RESEND_API_KEY"] = prev
    assert res == {"ok": False, "error": "resend_not_configured"}
