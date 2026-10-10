"""007 Secrets Scanner -- Deep scanner for secrets and credentials.

Goes deeper than quick_scan by performing entropy analysis, base64 detection,
context-aware false positive reduction, and targeted scanning of sensitive
file types (.env, config files, shell scripts, Docker, CI/CD).

Usage:
    python secrets_scanner.py --target /path/to/project
    python secrets_scanner.py --target /path/to/project --output json --verbose
    python secrets_scanner.py --target /path/to/project --include-low
"""

import argparse
import base64
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Import from the 007 config hub (parent directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = config.setup_logging("007-secrets-scanner")

# ---------------------------------------------------------------------------
# Additional patterns beyond config.SECRET_PATTERNS
# ---------------------------------------------------------------------------
# Each entry: (pattern_name, compiled_regex, severity)

_EXTRA_PATTERN_DEFS = [
    # URLs with embedded credentials  (http://user:pass@host)
    (
        "url_embedded_credentials",
        r"""https?://[^:\s]+:[^@\s]+@[^\s/]+""",
        "HIGH",
    ),
    # Stripe keys
    (
        "stripe_key",
        r"""(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}""",
        "CRITICAL",
    ),
    # Google API key
    (
        "google_api_key",
        r"""AIza[0-9A-Za-z\-_]{35}""",
        "HIGH",
    ),
    # Twilio Account SID / Auth Token
    (
        "twilio_key",
        r"""(?:AC[a-f0-9]{32}|SK[a-f0-9]{32})""",
        "HIGH",
    ),
    # Heroku API key
    (
        "heroku_api_key",
        r"""(?i)heroku[_-]?api[_-]?key\s*[:=]\s*['\"]\S{8,}['\"]""",
        "HIGH",
    ),
    # SendGrid API key
    (
        "sendgrid_key",
        r"""SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}""",
        "CRITICAL",
    ),
    # npm token
    (
        "npm_token",
        r"""(?:npm_)[A-Za-z0-9]{36}""",
        "CRITICAL",
    ),
    # Generic connection string (ODBC / ADO style)
    (
        "connection_string",
        r"""(?i)(?:connectionstring|conn_str)\s*[:=]\s*['\"][^'\"]{10,}['\"]""",
        "HIGH",
    ),
    # JWT tokens (three base64 segments separated by dots)
    (
        "jwt_token",
        r"""eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}""",
        "MEDIUM",
    ),
    # Azure storage key
    (
        "azure_storage_key",
        r"""(?i)(?:accountkey|storage[_-]?key)\s*[:=]\s*['\"]\S{44,}['\"]""",
        "CRITICAL",
    ),
]

EXTRA_PATTERNS = [
    (name, re.compile(pattern), severity)
    for name, pattern, severity in _EXTRA_PATTERN_DEFS
]

# Combined pattern set: config patterns first, then extras
ALL_SECRET_PATTERNS = list(config.SECRET_PATTERNS) + EXTRA_PATTERNS


# ---------------------------------------------------------------------------
# Targeted file categories for deep scanning
# ---------------------------------------------------------------------------

# .env variants -- always scanned regardless of SCANNABLE_EXTENSIONS
ENV_FILE_PATTERNS = {
    ".env", ".env.local", ".env.production", ".env.staging",
    ".env.development", ".env.test", ".env.example", ".env.sample",
    ".env.defaults", ".env.template",
}

CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}

SHELL_EXTENSIONS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}

DOCKER_PREFIXES = ("Dockerfile", "dockerfile", "docker-compose")

CICD_PATTERNS = {
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
}

PRIVATE_KEY_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}

# Files