"""007 Full Audit -- Comprehensive 6-phase security audit orchestrator.

Executes the complete 007 security audit pipeline:
  Phase 1: Surface Mapping      -- file inventory, entry points, dependencies
  Phase 2: Threat Modeling Hints -- identify components for STRIDE analysis
  Phase 3: Security Checklist    -- run all scanners, compile results
  Phase 4: Red Team Scenarios    -- template-based attack scenarios
  Phase 5: Blue Team Recs        -- hardening recommendations per finding
  Phase 6: Verdict               -- compute score and emit final verdict

Generates a comprehensive Markdown report saved to data/reports/ and prints
a summary to stdout.

Usage:
    python full_audit.py --target /path/to/project
    python full_audit.py --target /path/to/project --output markdown
    python full_audit.py --target /path/to/project --phase 3 --verbose
    python full_audit.py --target /path/to/project --output json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the 007 config hub (same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    BASE_DIR,
    DATA_DIR,
    REPORTS_DIR,
    SCANNABLE_EXTENSIONS,
    SKIP_DIRECTORIES,
    SCORING_WEIGHTS,
    SCORING_LABELS,
    SEVERITY,
    LIMITS,
    ensure_directories,
    get_verdict,
    get_timestamp,
    log_audit_event,
    setup_logging,
    calculate_weighted_score,
)

# ---------------------------------------------------------------------------
# Import scanners
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent / "scanners"))

import secrets_scanner  # noqa: E402
import dependency_scanner  # noqa: E402
import injection_scanner  # noqa: E402
import quick_scan  # noqa: E402
import score_calculator  # noqa: E402

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = setup_logging("007-full-audit")


# =========================================================================
# RED TEAM SCENARIO TEMPLATES
# =========================================================================
# Mapping from finding type/pattern -> attack scenario template.

_RED_TEAM_TEMPLATES: dict[str, dict] = {
    # --- Secrets ---
    "secret": {
        "title": "Credential Theft via Leaked Secret",
        "persona": "External attacker / Insider",
        "scenario": (
            "Attacker discovers leaked credential ({pattern}) in {file} "
            "and uses it to gain unauthorized access to the associated "
            "service or resource. Depending on the credential scope, "
            "the attacker may escalate to full account takeover."
        ),
        "impact": "Unauthorized access, data exfiltration, lateral movement",
        "difficulty": "Easy (if credential is in public repo) / Medium (if private)",
    },
    # --- Injection ---
    "code_injection": {
        "title": "Remote Code Execution via Code Injection",
        "persona": "Malicious user / Compromised agent",
        "scenario": (
            "Attacker crafts malicious input targeting {pattern} in {file}. "
            "The injected code executes in the server context, allowing "
            "arbitrary command execution, data access, or system compromise."
        ),
        "impact": "Full server compromise, data breach, service disruption",
        "difficulty": "Medium",
    },
    "command_injection": {
        "title": "System Compromise via Command Injection",
        "persona": "Malicious user / API abuser",
        "scenario": (
            "Attacker injects OS commands through {pattern} in {file}. "
            "The shell executes attacker-controlled commands, enabling "
            "file access, reverse shells, or privilege escalation."
        ),
        "impact": "Full system compromise, lateral movement",
        "difficulty": "Medium",
    },
    "sql_injection": {
        "title": "Data Breach via SQL Injection",
        "persona": "Malicious user / Bot",
        "scenario": (
            "Attacker crafts SQL payload targeting {pattern} in {file}. "
            "The malformed query bypasses authentication, extracts sensitive "
            "data, modifies records, or drops tables."
        ),
        "impact": "Data breach, data loss, authentication bypass",
        "difficulty": "Easy to Medium",
    },
    "prompt_injection": {
        "title": "AI Manipulation via Prompt Injection",
        "persona": "Malicious user / Compromised data source",
        "scenario": (
            "Attacker injects adversarial prompt through {pattern} in {file}. "
            "The LLM follows injected instructions, potentially exfiltrating "
            "data, bypassing safety controls, or performing unauthorized actions."
        ),
        "impact": "Data leakage, unauthorized actions, reputation damage",
        "difficulty": "Easy to Medium",
    },
    "xss": {
        "title": "User Account Takeover via XSS",
        "persona": "Malicious user",
        "scenario": (
            "Attacker injects JavaScript through {pattern} in {file}. "
            "The script executes in victim browsers,