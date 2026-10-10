"""007 Quick Scan -- Fast automated security scan of a target directory.

Recursively scans files in a target directory for secret patterns, dangerous
code constructs, permission issues, and oversized files.  Produces a scored
summary report in text or JSON format.

Usage:
    python quick_scan.py --target /path/to/project
    python quick_scan.py --target /path/to/project --output json --verbose
"""

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the 007 config hub (same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    SCANNABLE_EXTENSIONS,
    SKIP_DIRECTORIES,
    SECRET_PATTERNS,
    DANGEROUS_PATTERNS,
    LIMITS,
    SEVERITY,
    ensure_directories,
    get_verdict,
    get_timestamp,
    log_audit_event,
    setup_logging,
)

# ---------------------------------------------------------------------------
# Constants local to the quick scan
# ---------------------------------------------------------------------------

SCORE_DEDUCTIONS = {
    "CRITICAL": 10,
    "HIGH": 5,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
}

REDACT_KEEP_CHARS = 6  # Number of leading chars to keep in redacted snippets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redact(text: str) -> str:
    """Return a redacted version of *text*, keeping only the first few chars."""
    text = text.strip()
    if len(text) <= REDACT_KEEP_CHARS:
        return text
    return text[:REDACT_KEEP_CHARS] + "****"


def _snippet(line: str, match_start: int, context: int = 40) -> str:
    """Extract a short redacted snippet around the match position."""
    start = max(0, match_start - context // 2)
    end = min(len(line), match_start + context)
    raw = line[start:end].strip()
    return _redact(raw)


def _should_skip_dir(name: str) -> bool:
    """Return True if directory *name* should be skipped."""
    return name in SKIP_DIRECTORIES


def _is_scannable(path: Path) -> bool:
    """Return True if the file extension is in the SCANNABLE_EXTENSIONS set."""
    # Handle compound suffixes like .env.example
    name = path.name
    for ext in SCANNABLE_EXTENSIONS:
        if name.endswith(ext):
            return True
    # Also check the normal suffix
    return path.suffix.lower() in SCANNABLE_EXTENSIONS


def _check_permissions(filepath: Path) -> dict | None:
    """Check for overly permissive file modes on Unix-like systems.

    Returns a finding dict or None.
    """
    # Only meaningful on systems that implement os.stat st_mode properly
    if sys.platform == "win32":
        return None
    try:
        mode = filepath.stat().st_mode
        perms = stat.S_IMODE(mode)
        if perms & 0o777 == 0o777:
            return {
                "type": "permission",
                "pattern": "world_rwx_0777",
                "severity": "HIGH",
                "file": str(filepath),
                "line": 0,
                "snippet": f"mode={oct(perms)}",
            }
        if perms & 0o666 == 0o666:
            return {
                "type": "permission",
                "pattern": "world_rw_0666",
                "severity": "MEDIUM",
                "file": str(filepath),
                "line": 0,
                "snippet": f"mode={oct(perms)}",
            }
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------------
# Core scanning logic
# ---------------------------------------------------------------------------

def collect_files(target: Path, logger) -> list[Path]:
    """Walk *target* recursively and return scannable file paths.

    Respects SKIP_DIRECTORIES and SCANNABLE_EXTENSIONS from config.
    Stops at LIMITS['max_files_per_scan'] with a warning.
    """
    files: list[Path] = []
    max_files = LIMITS["max_files_per_scan"]

    for root, dirs, filenames in os.walk(target):
        # Prune skipped directories in-place so os.walk does not descend
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]

        for fname in filenames:
            if len(files) >= max_files:
                logger.warning(
                    "Reached max_files_per_scan limit (%d). Stopping collection.", max_files
                )
                return files

            fpath = Path(root) / fname
            if _is_scannable(fpath):
                files.append(fpath)

    return files


def scan_file(filepath: Path, verbose: bool = False, logger=None) -> list[dict]:
    """Scan a single file for secrets and dangerous patterns.

    Returns a list of finding dicts.
    """
    findings: list[dict] = []
    max_findings = LIMITS["max_findings_per_file"]

    try:
        size = filepath.stat().st_size
    except OSError:
        return findings

    # Large file check
    if size > LIMITS["max_file_size_bytes"]:
        findings.append({
            "type": "large_file",
            "pattern": "exceeds_max_size",
            "severity": "INFO",
            "file": str(filepath),
            "line": 0,
            "snippet": f"size={size} bytes (limit={LIMITS['max_file_size_bytes']})",
        })
        return findings

    # Permission check
    perm_finding = _check_permissions(filepath)
    if perm_finding:
        findings.append(perm_finding)

    # Read file content
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        if verbose and logger:
            logger.debug("Cannot read %s: %s", filepath, exc)
        return findings

    lines = text.splitlines()

    for line_num, line in enumerate(lines, start=1):
        if len(findings) >= max_findings:
            break

        # -- Secret patterns --
        for pattern_name, regex, severity in SECRET_PATTERNS:
            m = regex.search(line)
            if m:
                findings.append({
                    "type": "secret",
                    "pattern": pattern_name,
                    "severity": severity,
                    "file": str(filepath),
                    "line": line_num,
                    "snippet": _snippet(line, m.start()),
                })

        # -- Dangerous code patterns --
        for pattern_name, regex, severity in DANGEROUS_PATTERNS:
            m = regex.search(line)
            if m:
                findings.append({
                    "type": "dangerous_code",
                    "pattern": pattern_name,
                    "severity": severity,
                    "file": str(filepath),
                    "line": line_num,
                    "snippet": "",
                })

    return findings


def compute_score(findings: list[dict]) -> int:
    """Compute a quick score starting at 100, deducting by severity.

    Returns an integer score clamped between 0 and 100.
    """
    score = 100
    for f in findings:
        deduction = SCORE_DEDUCTIONS.get(f["severity"], 0)
        score -= deduction
    return max(0, score)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_by_severity(findings: list[dict]) -> dict[str, int]:
    """Count findings per severity level."""
    counts: dict[str, int] = {sev: 0 for sev in SEVERITY}
    for f in findings:
        se