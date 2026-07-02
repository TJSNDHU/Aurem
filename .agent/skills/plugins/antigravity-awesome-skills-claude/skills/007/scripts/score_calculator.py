"""007 Score Calculator -- Unified security scoring engine.

Aggregates results from all scanners (secrets, dependency, injection, quick_scan)
into a unified, per-domain security score with a weighted final verdict.

The score covers 8 security domains as defined in config.SCORING_WEIGHTS:
  - secrets, input_validation, authn_authz, data_protection,
    resilience, monitoring, supply_chain, compliance.

Results are appended to data/score_history.json for trend analysis and
every run is recorded in the audit log.

Usage:
    python score_calculator.py --target /path/to/project
    python score_calculator.py --target /path/to/project --output json
    python score_calculator.py --target /path/to/project --verbose
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the 007 config hub (same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    BASE_DIR,
    DATA_DIR,
    SCORING_WEIGHTS,
    SCORING_LABELS,
    SCORE_HISTORY_PATH,
    SEVERITY,
    SCANNABLE_EXTENSIONS,
    SKIP_DIRECTORIES,
    LIMITS,
    ensure_directories,
    get_verdict,
    get_timestamp,
    log_audit_event,
    setup_logging,
    calculate_weighted_score,
)

# ---------------------------------------------------------------------------
# Import scanners (each lives in scanners/ sub-package or sibling script)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent / "scanners"))

import secrets_scanner  # noqa: E402
import dependency_scanner  # noqa: E402
import injection_scanner  # noqa: E402

# quick_scan is a sibling script in the same directory
import quick_scan  # noqa: E402

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = setup_logging("007-score-calculator")

_SENSITIVE_FINDING_KEYS = {
    "snippet",
    "secret",
    "token",
    "password",
    "access_token",
    "app_secret",
    "authorization_code",
    "client_secret",
}


# ---------------------------------------------------------------------------
# Positive-signal patterns (auth, encryption, resilience, monitoring)
# ---------------------------------------------------------------------------
# These patterns indicate GOOD practices. Their presence raises the score
# in the relevant domain.

_AUTH_PATTERNS = [
    re.compile(r"""(?i)(?:@login_required|@auth|@require_auth|@authenticated|@permission_required)"""),
    re.compile(r"""(?i)(?:passport\.authenticate|isAuthenticated|requireAuth|authMiddleware)"""),
    re.compile(r"""(?i)(?:jwt\.verify|jwt\.decode|verify_jwt|decode_token)"""),
    re.compile(r"""(?i)(?:OAuth|oauth2|OpenID|openid)"""),
    re.compile(r"""(?i)(?:session\.get|flask_login|django\.contrib\.auth)"""),
    re.compile(r"""(?i)(?:bcrypt|argon2|pbkdf2|scrypt)"""),
    re.compile(r"""(?i)(?:RBAC|role_required|has_permission|check_permission)"""),
]

_ENCRYPTION_PATTERNS = [
    re.compile(r"""(?i)(?:from\s+cryptography|import\s+cryptography)"""),
    re.compile(r"""(?i)(?:from\s+hashlib|import\s+hashlib)"""),
    re.compile(r"""(?i)(?:from\s+hmac|import\s+hmac)"""),
    re.compile(r"""(?i)(?:AES|Fernet|RSA|ECDSA|ChaCha20)"""),
    re.compile(r"""(?i)(?:https://|TLS|ssl_context|ssl\.create_default_context)"""),
    re.compile(r"""(?i)verify\s*=\s*True"""),
    re.compile(r"""(?i)(?:encrypt|decrypt|sign|verify_signature)"""),
]

_RESILIENCE_PATTERNS = [
    re.compile(r"""(?:try\s*:|except\s+)"""),
    re.compile(r"""(?i)(?:timeout|connect_timeout|read_timeout|socket_timeout)"""),
    re.compile(r"""(?i)(?:retry|retries|backoff|exponential_backoff|tenacity)"""),
    re.compile(r"""(?i)(?:circuit_breaker|CircuitBreaker|pybreaker)"""),
    re.compile(r"""(?i)(?:rate_limit|ratelimit|throttle|RateLimiter)"""),
    re.compile(r"""(?i)(?:max_retries|max_attempts)"""),
    re.compile(r"""(?i)(?:graceful_shutdown|signal\.signal|atexit)"""),
]

_MONITORING_PATTERNS = [
    re.compile(r"""(?:import\s+logging|from\s+logging)"""),
    re.compile(r"""(?i)(?:logger\.\w+|logging\.getLogger)"""),
    re.compile(r"""(?i)(?:sentry|sentry_sdk|raven)"""),
    re.compile(r"""(?i)(?:prometheus|grafana|datadog|newrelic|elastic)"""),
    re.compile(r"""(?i)(?:audit_log|audit_trail|log_event|log_action)"""),
    re.compile(r"""(?i)(?:structlog|loguru)"""),
    re.compile(r"""(?i)(?:alerting|alert_manager|pagerduty|opsgenie)"""),
]

_INPUT_VALIDATION_PATTERNS = [
    re.compile(r"""(?i)(?:pydantic|BaseModel|validator|field_validator)"""),
    re.compile(r"""(?i)(?:jsonschema|validate|Schema|Marshmallow)"""),
    re.compile(r"""(?i)(?:wtforms|FlaskForm|ModelForm)"""),
    re.compile(r"""(?i)(?:sanitize|escape|bleach|html\.escape|markupsafe)"""),
    re.compile(r"""(?i)(?:parameterized|%s.*execute|placeholder|\?)"""),
    re.compile(r"""(?i)(?:zod|yup|joi|express-validator|celebrate)"""),
]


# ---------------------------------------------------------------------------
# File collection (lightweight, only for positive-signal detection)
# ---------------------------------------------------------------------------

def _collect_source_files(target: Path) -> list[Path]:
    """Collect source files for positive-signal pattern scanning."""
    files: list[Path] = []
    max_files = LIMITS["max_files_per_scan"]

    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]
        for fname in filenames:
            if len(files) >= max_files:
                return files
            fpath = Path(root) / fname
            suffix = fpath.suffix.lower()
            name = fpath.name.lower()
            for ext in SCANNABLE_EXTENSIONS:
                if name.endswith(ext) or suffix == ext:
                    files.append(fpath)
                    break

    return files


def _count_pattern_matches(files: list[Path], patterns: list[re.Pattern]) -> int:
    """Count how many files contain at least one match for any of the patterns."""
    count = 0
    for fpath in files:
        try:
            size = fpath.stat().st_size
            if size > LIMITS["max_file_size_bytes"]:
                continue
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for pat in patterns:
            if pat.search(text):
                count += 1
                break  # one match per file is enough

    return count


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate_findings(findings: list[dict]) -> list[dict]:
    """Remove duplicate findings by (file, line, pattern) tuple."""
    seen: set[tuple] = set()
    unique: list[dict] = []

    for f in findings:
        key = (f.get("file", ""), f.get("line", 0), f.get("pattern", ""))
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


# ---------------------------------------------------------------------------
# Per-domain score calculators
# ---------------------------------------------------------------------------

def _score_from_findings(findings: list[dict], max_deduction: int = 100) -> int:
    """Compute a 0-100 score from findings.  Fewer findings = higher score.

    Deductions per severity: CRITICAL=15, HIGH=8, MEDIUM=3, LOW=1, INFO=0.
    """
    deductions = {"CRITICAL": 15, "HIGH": 8, "MEDIUM": 3, "LOW": 1, "INFO": 0}
    total_deduction = 0
    for f in findings:
        total_deduction += deductions.get(f.get("severity", "INFO"), 0)
    return max(0, min(100, max_deduction - total_deduction))


def _score_from_positive_signals(
    match_count: int,
    total_files: int,
    base_score: int = 30,
    max_score: int = 100,
) -> int:
    """Score based on presence of positive patterns.

    If no source files exist, return the base_score (no evidence either way).
    The more files with positive signals, the higher the score.
    """
    if total_files == 0:
        return base_score

    ratio = min(1.0, match_count / max(1, total_files * 0.1))
    return min(max_score, int(base_score + ratio * (max_score - base_score)))


def _score_secrets_domain(secrets_findings: list[dict]) -> float:
    """Compute the secrets domain score."""
    secret_only = [f for f in secrets_findings if f.get("type") == "secret"]
    return float(_score_from_findings(secret_only))


def _score_input_validation_domain(
    injection_findings: list[dict],
    source_files: list[Path],
    total_source_files: int,
) -> float:
    """Compute the input_validation domain score."""
    injection_input_related = [
        f for f in injection_findings
        if f.get("injection_type") in (
            "sql_injection", "code_injection", "command_injection",
            "xss", "path_traversal",
        )
    ]
    negative_score = _score_from_findings(injection_input_related)
    positive_count = _count_pattern_matches(source_files, _INPUT_VALIDATION_PATTERNS)
    positive_score = _score_from_positive_signals(positive_count, total_source_files)
    return float(min(100, (negative_score + positive_score) // 2))


def _score_authn_authz_domain(
    source_files: list[Path],
    total_source_files: int,
) -> float:
    """Compute the authn_authz domain score."""
    auth_count = _count_pattern_matches(source_files, _AUTH_PATTERNS)
    if total_source_files == 0:
        return 50.0  # no code to evaluate
    if auth_count == 0:
        return 25.0  # no auth patterns found = low score
    return float(_score_from_positive_signals(
        auth_count, total_source_files, base_score=40, max_score=95,
    ))


def _score_data_protection_domain(
    secrets_findings: list[dict],
    source_files: list[Path],
    total_source_files: int,
) -> float:
    """Compute the data_protection domain score."""
    enc_count = _count_pattern_matches(source_files, _ENCRYPTION_PATTERNS)
    data_exposure = [
        f for f in secrets_findings
        if f.get("pattern") in (
            "db_connection_string", "url_embedded_credentials",
            "hardcoded_public_ip",
        )
    ]
    negative_dp = _score_from_findings(data_exposure)
    positive_dp = _score_from_positive_signals(enc_count, total_source_files)
    return float(min(100, (negative_dp + positive_dp) // 2))


def _score_resilience_domain(
    source_files: list[Path],
    total_source_files: int,
) -> float:
    """Compute the resilience domain score."""
    res_count = _count_pattern_matches(source_files, _RESILIENCE_PATTERNS)
    return float(_score_from_positive_signals(
        res_count, total_source_files, base_score=30, max_score=95,
    ))


def _score_monitoring_domain(
    source_files: list[Path],
    total_source_files: int,
) -> float:
    """Compute the monitoring domain score."""
    mon_count = _count_pattern_matches(source_files, _MONITORING_PATTERNS)
    return float(_score_from_positive_signals(
        mon_count, total_source_files, base_score=20, max_score=95,
    ))


def _score_supply_chain_domain(dependency_report: dict) -> float:
    """Compute the supply_chain domain score."""
    dep_score = dependency_report.get("score", 50)
    return float(max(0, min(100, dep_score)))


def _score_compliance_domain(scores: dict[str, float]) -> float:
    """Compute the compliance domain score as an aggregate of other domains."""
    other_scores = [
        scores.get(k, 0.0) for k in SCORING_WEIGHTS if k != "compliance"
    ]
    if other_scores:
        return float(round(sum(other_scores) / len(other_scores), 2))
    return 50.0


def compute_domain_scores(
    secrets_findings: list[dict],
    injection_findings: list[dict],
    dependency_report: dict,
    quick_findings: list[dict],
    source_files: list[Path],
    total_source_files: int,
) -> dict[str, float]:
    """Compute per-domain security scores (0-100).

    Returns:
        Dict mapping domain key -> score (float).
    """
    scores: dict[str, float] = {}

    scores["secrets"] = _score_secrets_domain(secrets_findings)
    scores["input_validation"] = _score_input_validation_domain(
        injection_findings, source_files, total_source_files,
    )
    scores["authn_authz"] = _score_authn_authz_domain(
        source_files, total_source_files,
    )
    scores["data_protection"] = _score_data_protection_domain(
        secrets_findings, source_files, total_source_files,
    )
    scores["resilience"] = _score_resilience_domain(
        source_files, total_source_files,
    )
    scores["monitoring"] = _score_monitoring_domain(
        source_files, total_source_files,
    )
    scores["supply_chain"] = _score_supply_chain_domain(dependency_report)
    scores["compliance"] = _score_compliance_domain(scores)

    return scores


# ---------------------------------------------------------------------------
# Score history persistence
# ---------------------------------------------------------------------------

def _save_score_history(
    target: str,
    domain_scores: dict[str, float],
    final_score: float,
    verdict: dict,
) -> None:
    """Append a score entry to the score history JSON file."""
    ensure_directories()

    entry = {
        "timestamp": get_timestamp(),
        "target": target,
        "domain_scores": domain_scores,
        "final_score": final_score,
        "verdict": {
            "label": verdict["label"],
            "description": verdict["description"],
            "emoji": verdict["emoji"],
        },
    }

    # Read existing history (JSON array)
    history: list[dict] = []
    if SCORE_HISTORY_PATH.exists():
        try:
            raw = SCORE_HISTORY_PATH.read_text