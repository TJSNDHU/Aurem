"""Tests for Shannon Runner — in-process security scanner.

Run:  cd /app/backend && pytest tests/test_shannon_runner.py -v
"""
import asyncio
from services.shannon_runner import run_real_audit


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_real_audit_runs_against_public_target():
    result = _run(run_real_audit("https://example.com"))
    assert isinstance(result, dict)
    assert "security_score" in result
    assert 0 <= result["security_score"] <= 100
    assert "severity_counts" in result
    assert set(result["severity_counts"].keys()) >= {"critical", "high", "medium", "low", "info"}
    assert result["total_vulnerabilities"] == len(result.get("vulnerabilities", []))
    assert result.get("scanner") == "shannon_runner_v1"


def test_audit_detects_missing_security_headers():
    result = _run(run_real_audit("https://example.com"))
    vulns = result.get("vulnerabilities") or []
    header_findings = [v for v in vulns if v.get("category") == "headers"]
    assert len(header_findings) > 0, f"Expected header findings; got {len(vulns)} total vulns"


def test_audit_severity_counts_match_findings():
    result = _run(run_real_audit("https://example.com"))
    vulns = result.get("vulnerabilities") or []
    counts = result.get("severity_counts") or {}
    recount = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for v in vulns:
        sev = v.get("severity", "info")
        if sev in recount:
            recount[sev] += 1
    for key in recount:
        assert counts.get(key, 0) == recount[key]


def test_audit_handles_unreachable_target_gracefully():
    result = _run(run_real_audit("https://this-host-does-not-exist-42424242.invalid"))
    assert isinstance(result, dict)
    assert "security_score" in result  # doesn't crash
