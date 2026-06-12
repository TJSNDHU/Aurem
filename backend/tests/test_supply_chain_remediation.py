"""
Regression tests for services.supply_chain_remediation (iter D-82b).

Covers the planner/classification + version-safety logic (deterministic, fast).
The REAL pip-apply path is exercised manually/E2E (it mutates the live venv) and
is intentionally NOT auto-run here to keep the suite side-effect free.

Run:  cd /app/backend && python -m pytest tests/test_supply_chain_remediation.py -v
"""
from services import supply_chain_remediation as r


def test_semver_parse_and_safe_bump():
    assert r._parse_semver("3.13.4") == (3, 13, 4)
    assert r._parse_semver("2.10") == (2, 10, 0)
    assert r._parse_semver("garbage") is None
    # same-major upgrade → safe
    assert r._is_safe_bump("3.13.3", "3.13.4") is True
    assert r._is_safe_bump("1.2.0", "1.5.0") is True
    # major bump → unsafe
    assert r._is_safe_bump("2.9.0", "3.0.0") is False
    # downgrade / equal → unsafe
    assert r._is_safe_bump("3.13.4", "3.13.3") is False
    assert r._is_safe_bump("3.13.3", "3.13.3") is False


def test_parse_pip_finding():
    f = {
        "tool": "pip-audit", "category": "SCA",
        "location": "backend/requirements.txt → aiohttp==3.13.3",
        "fix": "Upgrade to 3.13.4, 3.14.0",
    }
    parts = r._parse_pip_finding(f)
    assert parts == {"name": "aiohttp", "current": "3.13.3", "target": "3.13.4"}


def test_build_plan_lanes():
    findings = [
        {"tool": "pip-audit", "category": "SCA", "severity": "high",
         "location": "backend/requirements.txt → aiohttp==3.13.3",
         "fix": "Upgrade to 3.13.4"},                                   # auto_safe
        {"tool": "pip-audit", "category": "SCA", "severity": "high",
         "location": "backend/requirements.txt → foo==2.0.0",
         "fix": "Upgrade to 3.0.0"},                                    # needs_approval (major)
        {"tool": "pip-audit", "category": "SCA", "severity": "high",
         "location": "backend/requirements.txt → bar==1.0.0",
         "fix": "No fix released yet"},                                 # needs_approval (no fix)
        {"tool": "yarn-audit", "category": "SCA", "severity": "high",
         "location": "frontend/package.json → lodash", "fix": "upgrade"},  # needs_approval
        {"tool": "detect-secrets", "category": "SECRET", "severity": "high",
         "location": "x.py:1", "fix": "rotate"},                       # manual_only
        {"tool": "bandit", "category": "SAST", "severity": "medium",
         "location": "y.py:5", "fix": ""},                             # manual_only
    ]
    plan = r.build_plan(findings)
    assert len(plan["auto_safe"]) == 1
    assert plan["auto_safe"][0]["remediation"]["kind"] == "pip_upgrade"
    assert plan["auto_safe"][0]["remediation"]["target"] == "3.13.4"
    assert len(plan["needs_approval"]) == 3
    assert len(plan["manual_only"]) == 2


def test_severity_mapping():
    assert r._SEV_TO_P["critical"] == "P0"
    assert r._SEV_TO_P["high"] == "P1"
    assert r._SEV_TO_P["medium"] == "P2"
