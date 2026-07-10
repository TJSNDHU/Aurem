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

# Files that are test fixtures -- lower severity or skip
_TEST_FILE_PATTERNS = re.compile(
    r"""(?i)(?:^test_|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|__tests__|fixtures?[/\\])"""
)

# Placeholder / example value patterns -- these are NOT real secrets
_PLACEHOLDER_PATTERN = re.compile(
    r"""(?i)(?:example|placeholder|changeme|xxx+|your[_-]?key[_-]?here|"""
    r"""insert[_-]?here|replace[_-]?me|todo|fixme|dummy|fake|sample|test123|"""
    r"""sk_test_|pk_test_)"""
)


# ---------------------------------------------------------------------------
# Entropy calculation
# ---------------------------------------------------------------------------

def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string.

    Higher entropy indicates more randomness, which may suggest a secret/token.
    Typical English text: ~3.5-4.0 bits. Random tokens: ~4.5-6.0 bits.

    Args:
        s: Input string.

    Returns:
        Shannon entropy in bits. Returns 0.0 for empty strings.
    """
    if not s:
        return 0.0

    length = len(s)
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1

    entropy = 0.0
    for count in freq.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy


# ---------------------------------------------------------------------------
# Base64 detection
# ---------------------------------------------------------------------------

_BASE64_RE = re.compile(
    r"""[A-Za-z0-9+/]{20,}={0,2}"""
)

_BASE64_URL_RE = re.compile(
    r"""[A-Za-z0-9_-]{20,}"""
)


def _check_base64_secret(token: str) -> bool:
    """Check if a base64-looking string decodes to something high-entropy.

    Args:
        token: A candidate base64 string.

    Returns:
        True if the decoded content has high entropy (likely a secret).
    """
    # Pad if needed for standard base64
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
        decoded_str = decoded.decode("ascii", errors="replace")
        # Only flag if decoded content is also high entropy
        return shannon_entropy(decoded_str) > 4.0 and len(decoded) >= 12
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Hardcoded IP detection
# ---------------------------------------------------------------------------

_IP_RE = re.compile(
    r"""\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"""
)

_SAFE_IP_PREFIXES = (
    "127.",       # localhost
    "0.",         # unspecified
    "10.",        # private class A
    "192.168.",   # private class C
    "169.254.",   # link-local
    "255.",       # broadcast
)


def _is_private_or_localhost(ip: str) -> bool:
    """Return True if IP is localhost, private range, or otherwise safe."""
    if ip.startswith(_SAFE_IP_PREFIXES):
        return True
    # 172.16.0.