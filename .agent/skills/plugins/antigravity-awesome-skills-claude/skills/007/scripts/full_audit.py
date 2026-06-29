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
            "The script executes in victim browsers, stealing session tokens, "
            "redirecting users, or performing actions on their behalf."
        ),
        "impact": "Session hijacking, credential theft, phishing",
        "difficulty": "Easy",
    },
    "ssrf": {
        "title": "Internal Network Scanning via SSRF",
        "persona": "External attacker",
        "scenario": (
            "Attacker manipulates server-side request through {pattern} in {file}. "
            "The server makes requests to internal services, cloud metadata endpoints, "
            "or other internal resources on the attacker's behalf."
        ),
        "impact": "Internal network exposure, cloud credential theft, data access",
        "difficulty": "Medium",
    },
    "path_traversal": {
        "title": "Sensitive File Access via Path Traversal",
        "persona": "Malicious user",
        "scenario": (
            "Attacker uses directory traversal sequences (../) through {pattern} "
            "in {file} to access files outside the intended directory, "
            "including configuration files, credentials, or system files."
        ),
        "impact": "Credential exposure, configuration leak, source code theft",
        "difficulty": "Easy",
    },
    # --- Dependencies ---
    "dependency": {
        "title": "Supply Chain Attack via Vulnerable Dependency",
        "persona": "Supply chain attacker",
        "scenario": (
            "Attacker compromises a dependency ({pattern}) used in {file}. "
            "Malicious code in the dependency executes during install or runtime, "
            "exfiltrating secrets, installing backdoors, or modifying behavior."
        ),
        "impact": "Full compromise, backdoor installation, data exfiltration",
        "difficulty": "Hard (requires compromising upstream package)",
    },
    # --- Auth missing ---
    "no_auth": {
        "title": "Unauthorized Access to Unprotected Endpoints",
        "persona": "Any external attacker / Bot",
        "scenario": (
            "Attacker discovers unprotected API endpoints or routes "
            "with no authentication middleware. Direct access allows "
            "data extraction, modification, or service abuse without credentials."
        ),
        "impact": "Data breach, unauthorized actions, resource abuse",
        "difficulty": "Easy",
    },
    # --- Dangerous code ---
    "dangerous_code": {
        "title": "Exploitation of Dangerous Code Pattern",
        "persona": "Malicious user / Insider",
        "scenario": (
            "Attacker exploits dangerous code construct ({pattern}) in {file}. "
            "The construct allows unintended behavior such as arbitrary code "
            "execution, deserialization attacks, or unsafe data processing."
        ),
        "impact": "Code execution, data manipulation, service disruption",
        "difficulty": "Medium",
    },
}

# Fallback template for finding types not explicitly mapped
_RED_TEAM_FALLBACK = {
    "title": "Exploitation of Security Weakness",
    "persona": "Opportunistic attacker",
    "scenario": (
        "Attacker discovers and exploits security weakness ({pattern}) "
        "in {file}. The specific impact depends on the context and "
        "the attacker's capabilities."
    ),
    "impact": "Variable -- depends on finding severity and context",
    "difficulty": "Variable",
}


# =========================================================================
# BLUE TEAM RECOMMENDATION TEMPLATES
# =========================================================================

_BLUE_TEAM_TEMPLATES: dict[str, dict] = {
    "secret": {
        "recommendation": (
            "Move secrets to environment variables, a secrets manager (e.g. AWS "
            "Secrets Manager, HashiCorp Vault), or a .env file excluded from "
            "version control. Add a pre-commit hook (e.g. detect-secrets, "
            "gitleaks) to prevent future leaks. Rotate the compromised credential "
            "immediately."
        ),
        "priority": "CRITICAL",
        "effort": "Low",
    },
    "code_injection": {
        "recommendation": (
            "Remove all uses of eval(), exec(), and Function(). If dynamic "
            "code execution is absolutely necessary, use a sandboxed environment "
            "(e.g. RestrictedPython, vm2 in strict mode) with allowlisted "
            "operations only. Never pass user input to code execution functions."
        ),
        "priority": "CRITICAL",
        "effort": "Medium",
    },
    "command_injection": {
        "recommendation": (
            "Replace unsafe shell calls (os module system/popen, and subprocess with shell=True) "
            "with subprocess.run() using shell=False and a list of arguments. "
            "Never concatenate user input into shell commands. Validate and "
            "sanitize all inputs. Use shlex.quote() if shell is unavoidable."
        ),
        "priority": "CRITICAL",
        "effort": "Low to Medium",
    },
    "sql_injection": {
        "recommendation": (
            "Use parameterized queries (placeholders) for ALL database operations. "
            "Never use f-strings, .format(), or string concatenation in SQL. "
            "Use an ORM (SQLAlchemy, Django ORM) when possible. Add input "
            "validation and type checking before database operations."
        ),
        "priority": "CRITICAL",
        "effort": "Low",
    },
    "prompt_injection": {
        "recommendation": (
            "Separate system prompts from user content using proper message "
            "structure (system/user/assistant roles). Never concatenate user "
            "input directly into system prompts. Add input sanitization, "
            "output filtering, and content safety guardrails. Limit tool "
            "access and implement output validation."
        ),
        "priority": "HIGH",
        "effort": "Medium",
    },
    "xss": {
        "recommendation": (
            "Never set innerHTML or use dangerouslySetInnerHTML with user content. "
            "Use textContent for safe text insertion. Implement Content Security "
            "Policy (CSP) headers. Use template engines with auto-escaping "
            "(Jinja2 with autoescape, React JSX). Sanitize user HTML with "
            "DOMPurify or bleach."
        ),
        "priority": "HIGH",
        "effort": "Low to Medium",
    },
    "ssrf": {
        "recommendation": (
            "Implement URL allowlisting for outbound requests. Block requests "
            "to private IP ranges (10.x, 172.16-31.x, 192.168.x), localhost, "
            "and cloud metadata endpoints (169.254.169.254). Validate and "
            "parse URLs before making requests. Use a dedicated HTTP client "
            "with SSRF protections."
        ),
        "priority": "HIGH",
        "effort": "Medium",
    },
    "path_traversal": {
        "recommendation": (
            "Use Path.resolve() and verify the resolved path starts with the "
            "expected base directory. Never pass raw user input to open() or "
            "file operations. Use os.path.realpath() followed by a prefix check. "
            "Implement a file access allowlist."
        ),
        "priority": "HIGH",
        "effort": "Low",
    },
    "dependency": {
        "recommendation": (
            "Pin all dependency versions with exact versions (not ranges). "
            "Use lock files (pip freeze, package-lock.json, poetry.lock). "
            "Run regular vulnerability scans (safety, npm audit, Snyk). "
            "Remove unused dependencies. Verify package integrity with hashes."
        ),
        "priority": "MEDIUM",
        "effort": "Low",
    },
    "dangerous_code": {
        "recommendation": (
            "Replace dangerous constructs with safe alternatives: "
            "pickle -> json, yaml.load -> yaml.safe_load, eval -> ast.literal_eval "
            "(for literals only). Add input validation before any dynamic operation. "
            "Implement proper error handling and type checking."
        ),
        "priority": "HIGH",
        "effort": "Low to Medium",
    },
    "no_auth": {
        "recommendation": (
            "Add authentication middleware to all endpoints except public "
            "health checks. Implement RBAC/ABAC for authorization. Use "
            "established auth libraries (Flask-Login, Passport.js, Django auth). "
            "Add rate limiting to prevent brute force attacks."
        ),
        "priority": "CRITICAL",
        "effort": "Medium",
    },
    "permission": {
        "recommendation": (
            "Set restrictive file permissions (600 for secrets, 644 for configs, "
            "755 for executables). Never use 777. Run services as non-root users. "
            "Use chown/chmod to enforce ownership."
        ),
        "priority": "MEDIUM",
        "effort": "Low",
    },
    "large_file": {
        "recommendation": (
            "Investigate oversized files for accidentally committed binaries, "
            "databases, or data dumps. Add them to .gitignore. Use Git LFS "
            "for legitimate large files."
        ),
        "priority": "LOW",
        "effort": "Low",
    },
}

_BLUE_TEAM_FALLBACK = {
    "recommendation": (
        "Review the finding in context and apply the principle of least "
        "privilege. Add input validation, proper error handling, and "
        "logging. Consult OWASP guidelines for the specific vulnerability type."
    ),
    "priority": "MEDIUM",
    "effort": "Variable",
}


# =========================================================================
# PHASE IMPLEMENTATIONS
# =========================================================================

def _phase1_surface_mapping(target: Path, verbose: bool = False) -> dict:
    """Phase 1: Surface Mapping -- inventory files, entry points, dependencies."""
    logger.info("Phase 1: Surface Mapping")

    files_by_type: dict[str, int] = {}
    entry_points: list[str] = []
    dependency_files: list[str] = []
    config_files: list[str] = []
    total_files = 0

    _entry_point_patterns = [
        re.compile(r"""(?i)(?:^main\.py|^app\.py|^server\.py|^index\.\w+|^manage\.py)"""),
        re.compile(r"""(?i)(?:^wsgi\.py|^asgi\.py|^gunicorn|^uvicorn)"""),
        re.compile(r"""(?i)(?:^Dockerfile|^docker-compose)"""),
        re.compile(r"""(?i)(?:\.github[/\\]workflows|Jenkinsfile|\.gitlab-ci)"""),
    ]

    _dep_file_names = {
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "setup.py", "setup.cfg", "pyproject.toml", "Pipfile", "Pipfile.lock",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
        "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
    }

    _config_extensions = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env"}

    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]