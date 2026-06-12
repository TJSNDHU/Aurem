"""
Regression tests for services.supply_chain_scanner (iter D-82).

Covers:
  • Pure summarisation/scoring logic (deterministic, fast).
  • Finding schema normalisation.
  • A REAL detect-secrets run against a temp file with a planted secret —
    proves the secret scanner actually fires (no mock).

Run:  cd /app/backend && python -m pytest tests/test_supply_chain_scanner.py -v
"""
import os
import tempfile

import pytest

from services import supply_chain_scanner as sc


def test_finding_schema_and_truncation():
    f = sc._finding("bandit", "SAST", "HIGH", "x" * 500, location="y" * 400,
                    identifier="z" * 200, fix="w" * 400)
    assert f["tool"] == "bandit"
    assert f["category"] == "SAST"
    assert f["severity"] == "high"          # lower-cased
    assert len(f["title"]) <= 400
    assert len(f["location"]) <= 300
    assert len(f["identifier"]) <= 120
    assert len(f["fix"]) <= 300


def test_summarise_counts_and_score():
    tool_results = [
        {"tool": "bandit", "category": "SAST", "status": "ok", "findings": [
            sc._finding("bandit", "SAST", "high", "a"),
            sc._finding("bandit", "SAST", "medium", "b"),
        ]},
        {"tool": "trufflehog", "category": "SECRET", "status": "ok", "findings": [
            sc._finding("trufflehog", "SECRET", "critical", "c"),
        ]},
        {"tool": "pip-audit", "category": "SCA", "status": "error", "error": "x", "findings": []},
    ]
    s = sc._summarise(tool_results)
    assert s["total_findings"] == 3
    assert s["by_severity"]["critical"] == 1
    assert s["by_severity"]["high"] == 1
    assert s["by_severity"]["medium"] == 1
    assert s["by_category"]["SAST"] == 2
    assert s["by_category"]["SECRET"] == 1
    # critical(25) + high(8) + medium(2) = 35 penalty → 65
    assert s["posture_score"] == 65
    # findings sorted critical-first
    assert s["findings"][0]["severity"] == "critical"
    # per-tool status preserved, including error tools
    assert s["by_tool"]["pip-audit"]["status"] == "error"


def test_summarise_score_floors_at_zero():
    many_crit = [{"tool": "t", "category": "SECRET", "status": "ok",
                  "findings": [sc._finding("t", "SECRET", "critical", str(i)) for i in range(10)]}]
    s = sc._summarise(many_crit)
    assert s["posture_score"] == 0


@pytest.mark.asyncio
async def test_detect_secrets_finds_planted_key():
    """Real run — plant an AWS-style key and confirm detect-secrets flags it."""
    with tempfile.TemporaryDirectory() as d:
        # Point the scanner at our temp dir by monkeypatching the module paths.
        secret_file = os.path.join(d, "leak.py")
        with open(secret_file, "w") as fh:
            fh.write('GITHUB_TOKEN = "ghp_aB3dEfGh1jKlMnOpQrStUvWxYz0123456789"\n')
            fh.write('password = "hunter2superSecretValue99XZ"\n')

        orig_run = sc._run

        async def patched_run(cmd, cwd, timeout=sc.PER_TOOL_TIMEOUT_S):
            # Redirect to our planted file. cwd must be the (non-git) temp dir
            # so detect-secrets does not apply git-tracked-only filtering.
            if cmd and cmd[0] == "detect-secrets":
                cmd = ["detect-secrets", "scan", "leak.py"]
                cwd = d
            return await orig_run(cmd, cwd=cwd, timeout=timeout)

        sc._run = patched_run
        try:
            res = await sc.scan_detect_secrets()
        finally:
            sc._run = orig_run

        assert res["status"] == "ok", res
        assert len(res["findings"]) >= 1
        assert all(f["category"] == "SECRET" for f in res["findings"])
        assert all(f["severity"] == "high" for f in res["findings"])
