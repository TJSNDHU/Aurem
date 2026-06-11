"""CI wrapper — runs the security suite and emits a deploy-gate verdict.

Usage:
    # Free, structural-only run (CI default):
    python backend/scripts/run_security_suite.py

    # Full run including LLM-cost adversarial probes (deploy gate / weekly):
    RUN_SEC_LLM=1 python backend/scripts/run_security_suite.py

Exit codes:
    0 — all tests passed, zero leaks. Safe to deploy.
    1 — at least one test failed.
    2 — leaks detected. BLOCK DEPLOY.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path("/app/test_reports")


def main() -> int:
    cmd = [
        sys.executable, "-m", "pytest",
        "/app/backend/tests/security",
        "-q", "--tb=short",
        # Show the inline summary block from conftest.write_report:
        "-s",
    ]
    print(f"[sec-suite] RUN_SEC_LLM={os.environ.get('RUN_SEC_LLM', '0')}")
    print(f"[sec-suite] cmd: {' '.join(cmd)}")
    rc = subprocess.call(cmd)

    # Pick the freshest report.
    reports = sorted(REPORT_DIR.glob("security_suite_*.json"))
    if not reports:
        print("[sec-suite] no report produced — failing closed")
        return 1
    payload = json.loads(reports[-1].read_text())
    summary = payload.get("summary", {})

    leaks = summary.get("leaks", 0) or 0
    fails = summary.get("fail", 0) or 0
    blocked_pct = summary.get("blocked_pct")

    print(json.dumps(summary, indent=2))

    if leaks > 0:
        print(f"[sec-suite] ❌ {leaks} LEAK(S) DETECTED — BLOCK DEPLOY")
        return 2
    if fails > 0 or rc != 0:
        print(f"[sec-suite] ❌ {fails} test failure(s) (pytest rc={rc})")
        return 1
    print(f"[sec-suite] ✅ all probes blocked ({blocked_pct}%) — safe to deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
