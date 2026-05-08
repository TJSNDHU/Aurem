"""Tests for services.website_qa — Section 5 of growth-engine upgrade."""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import website_qa as wq


# ── owner-name fallback ───────────────────────────────────────────────

def test_owner_name_fallback():
    assert wq.get_owner_name_or_default({}) == "there"
    assert wq.get_owner_name_or_default({"first_name": "Mike"}) == "Mike"
    assert wq.get_owner_name_or_default({"owner_name": "Mike Smith"}) == "Mike"
    assert wq.get_owner_name_or_default({"owner_first_name": "Sara"}) == "Sara"
    assert wq.get_owner_name_or_default({"first_name": ""}) == "there"


# ── audit shape ───────────────────────────────────────────────────────

def test_audit_returns_required_fields_on_empty_url():
    out = asyncio.run(wq.audit_website(""))
    assert set(out.keys()) >= {"url", "load_time_ms", "ssl_valid",
                               "mobile_responsive", "cta_present",
                               "issues_count", "issues_summary"}
    assert out["issues_count"] >= 1


def test_audit_handles_unreachable_host(monkeypatch):
    async def fake_fetch(url):
        return {"status": None, "body": "", "load_time_ms": None,
                "error": "ConnectError"}
    async def fake_ssl(host):
        return {"valid": False, "reason": "ConnectError"}
    monkeypatch.setattr(wq, "_fetch_with_timing", fake_fetch)
    monkeypatch.setattr(wq, "_check_ssl", fake_ssl)
    out = asyncio.run(wq.audit_website("https://does-not-exist.local"))
    assert out["ssl_valid"] is False
    assert out["http_status"] is None
    assert out["issues_count"] >= 1
    assert any("Insecure" in s or "SSL" in s for s in out["issues_summary"])


def test_audit_detects_mobile_and_cta(monkeypatch):
    body = (
        '<html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '</head><body>'
        '<a href="tel:+14165551234">Call Now</a>'
        '</body></html>'
    )
    async def fake_fetch(url):
        return {"status": 200, "body": body, "load_time_ms": 1500}
    async def fake_ssl(host):
        return {"valid": True}
    monkeypatch.setattr(wq, "_fetch_with_timing", fake_fetch)
    monkeypatch.setattr(wq, "_check_ssl", fake_ssl)
    out = asyncio.run(wq.audit_website("https://example.com"))
    assert out["mobile_responsive"] is True
    assert out["cta_present"] is True
    assert out["issues_count"] == 0
    assert out["load_time_ms"] == 1500


def test_audit_flags_slow_site(monkeypatch):
    body = '<html><meta name="viewport" content="width=device-width"><body>Call Now</body></html>'
    async def fake_fetch(url):
        return {"status": 200, "body": body, "load_time_ms": 5800}
    async def fake_ssl(host):
        return {"valid": True}
    monkeypatch.setattr(wq, "_fetch_with_timing", fake_fetch)
    monkeypatch.setattr(wq, "_check_ssl", fake_ssl)
    out = asyncio.run(wq.audit_website("https://slow.example.com"))
    assert out["load_time_ms"] == 5800
    assert any("Slow load" in s for s in out["issues_summary"])
    assert out["issues_count"] >= 1


# ── blast artifact rendering ──────────────────────────────────────────

def test_render_blast_artifacts_populates_all():
    lead = {
        "lead_id": "L-1",
        "business_name": "Joe's Plumbing",
        "first_name": "Joe",
        "phone_e164": "+14165551234",
    }
    audit = {"issues_count": 3, "issues_summary": ["Slow load — 4.2s vs avg 2.1s",
                                                   "Insecure / no SSL", "Not mobile-responsive"],
             "load_time_ms": 4200}
    out = asyncio.run(wq.render_blast_artifacts(lead, audit))
    assert "Joe's Plumbing" in out["blast_email_subject"]
    assert "Joe" in out["blast_email_body"]
    assert "Joe's Plumbing" in out["blast_email_body"]
    assert "report/L-1" in out["report_url"]
    assert out["blast_sms_body"]
    assert len(out["blast_sms_body"]) <= 160
    # Retell script must mention name + at least one specific issue
    script = out["blast_retell_script"]
    assert "Joe" in script
    assert "Joe's Plumbing" in script


# ── A2A checklist ─────────────────────────────────────────────────────

def test_qa_checklist_passes_when_all_5_satisfied():
    audit = {"issues_count": 1, "issues_summary": ["Slow load — 4.2s vs avg 2.1s"]}
    lead = {
        "business_name": "Joe HVAC",
        "first_name": "Joe",
        "phone_e164": "+14165551234",
        "sort_email_only": False,
        "blast_email_subject": "Joe HVAC — quick site audit",
        "blast_email_body": "Hi Joe, …Joe HVAC site …",
        "blast_sms_body": "Hi Joe, ORA here. Joe HVAC site has 1 issue. https://aurem.live/report/x",
        "blast_retell_script": "Hi Joe, ORA here. Joe HVAC site Slow load — 4.2s vs avg 2.1s",
        "report_url_status_ok": True,
    }
    res = wq.qa_has_website_checklist(lead, audit)
    assert res["passed"] is True
    assert all(res["checks"].values())
    assert res["failures"] == []


def test_qa_checklist_fails_on_long_sms():
    audit = {"issues_count": 1, "issues_summary": ["X"]}
    lead = {
        "business_name": "Biz",
        "first_name": "Joe",
        "phone_e164": "+14165551234",
        "sort_email_only": False,
        "blast_email_subject": "Biz audit",
        "blast_email_body": "Biz body",
        "blast_sms_body": "X" * 200,  # too long
        "blast_retell_script": "Joe X",
        "report_url_status_ok": True,
    }
    res = wq.qa_has_website_checklist(lead, audit)
    assert res["passed"] is False
    assert any(f.startswith("sms_length_") for f in res["failures"])


def test_qa_checklist_fails_on_landline():
    audit = {"issues_count": 1, "issues_summary": ["X"]}
    lead = {
        "business_name": "Biz",
        "first_name": "Joe",
        "phone_e164": "+14165551234",
        "sort_email_only": True,  # ← landline
        "blast_email_subject": "Biz audit",
        "blast_email_body": "Biz body",
        "blast_sms_body": "Hi Joe, ORA here. Biz site issue. https://aurem.live/x",
        "blast_retell_script": "Hi Joe X",
        "report_url_status_ok": True,
    }
    res = wq.qa_has_website_checklist(lead, audit)
    assert res["passed"] is False
    assert "phone_landline_or_missing" in res["failures"]
