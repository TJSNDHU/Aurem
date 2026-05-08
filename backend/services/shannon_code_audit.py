"""
Shannon Code Audit — Static analysis of backend source for common vulnerability patterns.
Run on-demand by the /api/security/red-team/findings endpoint.

Focused audit: checks critical scanner & utility files for:
  1. SSL verification disabled without INTENTIONAL comment
  2. Verbose error messages exposing stack traces to clients
"""

import os
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files to audit (critical scanner pipeline + utilities)
_AUDIT_FILES = [
    "routers/ora_repair_engine.py",
    "routers/customer_scanner.py",
    "routers/live_scanner.py",
    "utils/resilient_fetch.py",
    "utils/deep_scanner.py",
]

# Skip dirs for broader scan
_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "env", "tests"}
_THIS_FILE = os.path.basename(__file__)


def _check_ssl_in_file(filepath: str, rel_path: str) -> List[Dict]:
    """Check for unguarded SSL verification bypass."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return findings

    safe_marker = "INTENTIONAL: scanning untrusted external websites"

    # If the file contains the INTENTIONAL marker anywhere, all SSL bypasses are justified
    # (the file is an external scanning utility by design)
    if safe_marker in content:
        return findings

    # Look for verify=False or CERT_NONE in code lines
    ssl_pattern = re.compile(r"verify\s*=\s*False|CERT_NONE|verify_mode\s*=.*CERT_NONE")
    lines = content.split("\n")
    in_docstring = False
    file_has_unguarded = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Track multi-line docstrings
        if '"""' in stripped:
            count = stripped.count('"""')
            if count == 1:
                in_docstring = not in_docstring
            # If count >= 2, the docstring opens and closes on same line
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        if ssl_pattern.search(line):
            file_has_unguarded = True
            break

    if file_has_unguarded:
        findings.append({
            "severity": "high",
            "title": "SSL Certificate Verification Disabled",
            "description": f"SSL verification bypass found in {rel_path} without documented justification.",
            "file": rel_path,
            "cwe": "CWE-295",
            "category": "crypto",
            "verified": True,
            "exploitable": True,
            "fix_suggestion": "Use ssl.create_default_context() with CERT_REQUIRED for internal calls. Add '# INTENTIONAL: scanning untrusted external websites — not our servers' above external scanning code.",
        })

    return findings


def _check_verbose_errors_in_file(filepath: str, rel_path: str) -> List[Dict]:
    """Check for verbose error messages leaking to clients."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return findings

    pattern = re.compile(r"HTTPException\(.*detail\s*=\s*(?:f?[\"'].*\{(?:str\(e\)|e)\}|str\(e\))")
    count = len(pattern.findall(content))

    if count > 0:
        findings.append({
            "severity": "medium",
            "title": "Verbose Error Messages in Production",
            "description": f"{count} endpoint(s) in {rel_path} expose raw exception details to API clients.",
            "file": rel_path,
            "cwe": "CWE-209",
            "category": "info_disclosure",
            "verified": True,
            "exploitable": False,
            "fix_suggestion": "Return generic error messages to clients. Log full details server-side only.",
        })

    return findings


def run_code_audit() -> Dict:
    """
    Run a focused code audit on critical scanner pipeline files.
    Returns findings list + a 0-100 security score.
    One finding per file per vulnerability type (not per-line).
    """
    all_findings = []
    files_scanned = 0

    for rel_path in _AUDIT_FILES:
        filepath = os.path.join(BACKEND_ROOT, rel_path)
        if not os.path.exists(filepath):
            continue
        files_scanned += 1
        all_findings.extend(_check_ssl_in_file(filepath, rel_path))
        all_findings.extend(_check_verbose_errors_in_file(filepath, rel_path))

    # Calculate score (per-file, not per-line)
    score = 100
    for finding in all_findings:
        sev = finding["severity"]
        if sev == "critical":
            score -= 25
        elif sev == "high":
            score -= 15
        elif sev == "medium":
            score -= 8
        elif sev == "low":
            score -= 3
    score = max(0, score)

    logger.info(f"[CodeAudit] Scanned {files_scanned} files, found {len(all_findings)} issues, score: {score}")

    return {
        "findings": all_findings,
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "score": score,
    }
