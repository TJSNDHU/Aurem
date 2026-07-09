"""007 Injection Scanner -- Specialized scanner for injection vulnerabilities.

Detects code injection, SQL injection, command injection, prompt injection,
XSS, SSRF, and path traversal patterns across Python, JavaScript/Node.js,
and shell codebases.  Performs context-aware analysis to reduce false positives
by tracking user-input sources and adjusting severity for hardcoded values,
test files, comments, and docstrings.

Usage:
    python injection_scanner.py --target /path/to/project
    python injection_scanner.py --target /path/to/project --output json --verbose
    python injection_scanner.py --target /path/to/project --include-low
"""

import argparse
import json
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
logger = config.setup_logging("007-injection-scanner")

# ---------------------------------------------------------------------------
# Context markers: sources of user input
# ---------------------------------------------------------------------------
# If a line (or nearby lines) contain any of these tokens, variables on that
# line are treated as *tainted* (user-controlled).  When a dangerous pattern
# uses only a hardcoded literal, severity is reduced.

_USER_INPUT_MARKERS_PY = re.compile(
    r"""(?:request\.(?:args|form|json|data|files|values|headers|cookies|get_json)|"""
    r"""request\.GET|request\.POST|request\.query_params|"""
    r"""sys\.argv|input\s*\(|os\.environ|"""
    r"""flask\.request|django\.http|"""
    r"""click\.argument|click\.option|argparse|"""
    r"""websocket\.recv|channel\.receive|"""
    r"""getattr\s*\(\s*request)""",
    re.IGNORECASE,
)

_USER_INPUT_MARKERS_JS = re.compile(
    r"""(?:req\.(?:body|params|query|headers|cookies)|"""
    r"""request\.(?:body|params|query|headers)|"""
    r"""process\.argv|"""
    r"""\.useParams|\.useSearchParams|"""
    r"""window\.location|document\.location|"""
    r"""location\.(?:search|hash|href)|"""
    r"""URLSearchParams|"""
    r"""event\.(?:target|data)|"""
    r"""document\.(?:getElementById|querySelector)|\.value|"""
    r"""localStorage|sessionStorage|"""
    r"""socket\.on)""",
    re.IGNORECASE,
)

_USER_INPUT_MARKERS = re.compile(
    _USER_INPUT_MARKERS_PY.pattern + r"|" + _USER_INPUT_MARKERS_JS.pattern,
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Comment / docstring detection
# ---------------------------------------------------------------------------

_COMMENT_LINE_RE = re.compile(
    r"""^\s*(?:#|//|/\*|\*|;|rem\b|@rem\b)""", re.IGNORECASE
)

_TRIPLE_QUOTE_RE = re.compile(r'''^\s*(?:\"{3}|'{3})''')

_MARKDOWN_CODE_FENCE = re.compile(r"""^\s*```""")


def _is_comment_line(line: str) -> bool:
    """Return True if the line is a single-line comment."""
    return bool(_COMMENT_LINE_RE.match(line))


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------

_TEST_FILE_RE = re.compile(
    r"""(?i)(?:^test_|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|"""
    r"""__tests__|fixtures?[/\\]|test[/\\]|tests[/\\]|"""
    r"""mocks?[/\\]|__mocks__[/\\])"""
)


def _is_test_file(filepath: Path) -> bool:
    """Return True if *filepath* looks like a test or fixture file."""
    return bool(_TEST_FILE_RE.search(filepath.name)) or bool(
        _TEST_FILE_RE.search(str(filepath))
    )


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

def _lower_severity(severity: str) -> str:
    """Return the next-lower severity level."""
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    idx = order.index(severity) if severity in order else 0
    return order[min(idx + 1, len(order) - 1)]


def _has_user_input(line: str) -> bool:
    """Return True if *line* references a known user-input source."""
    return bool(_USER_INPUT_MARKERS.search(line))


def _has_variable_interpolation(line: str) -> bool:
    """Return True if *line* contains f-string braces, .format(), or % formatting."""
    # f-string-style braces (not escaped)
    if re.search(r"""(?<!\{)\{[^{}\s][^{}]*\}(?!\})""", line):
        return True
    # .format() call
    if ".format(" in line:
        return True
    # %-style formatting with a variable (%s, %d etc followed by %)
    if re.search(r"""%[sdifr]""", line) and "%" in line:
        return True
    return False


def _only_hardcoded_string(line: str) -> bool:
    """Heuristic: return True if the dangerous call appears to use only literals.

    For example, ``eval("1