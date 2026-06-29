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

    For example, ``eval("1+1")`` or ``os.system("clear")`` with no variables.
    """
    # If there is variable interpolation, not hardcoded
    if _has_variable_interpolation(line):
        return False
    # If there's a user input marker, not hardcoded
    if _has_user_input(line):
        return False
    # Check for variable references inside the call parens
    # Look for identifiers that aren't string literals
    paren = line.find("(")
    if paren == -1:
        return False
    inside = line[paren:]
    # If the argument is just a string literal, treat as hardcoded
    if re.match(r"""\(\s*['\"]{1,3}[^'\"]*['\"]{1,3}\s*\)""", inside):
        return True
    return False


# =========================================================================
# INJECTION PATTERN DEFINITIONS
# =========================================================================
# Each entry: (pattern_name, compiled_regex, base_severity, injection_type,
#              description)
# The scanner applies context analysis on top of base_severity.

_INJECTION_DEFS: list[tuple[str, str, str, str, str]] = [

    # -----------------------------------------------------------------
    # 1. CODE INJECTION (Python)
    # -----------------------------------------------------------------
    (
        "py_eval_user_input",
        r"""\beval\s*\([^)]*(?:\bvar\b|\bdata\b|\brequest\b|\binput\b|\bargv\b|\bparams?\b|"""
        r"""\bquery\b|\bform\b|\buser\b|\bf['\"])""",
        "CRITICAL",
        "code_injection",
        "eval() with potential user input",
    ),
    (
        "py_eval_any",
        r"""\beval\s*\(""",
        "CRITICAL",
        "code_injection",
        "eval() usage -- verify input is not user-controlled",
    ),
    (
        "py_exec_any",
        r"""\b""" + "exec" + r"""\s*\(""",
        "CRITICAL",
        "code_injection",
        "exec() usage -- verify input is not user-controlled",
    ),
    (
        "py_compile_external",
        r"""\bcompile\s*\([^)]*(?:\bvar\b|\bdata\b|\brequest\b|\binput\b|\bargv\b|"""
        r"""\bparams?\b|\bquery\b|\bform\b|\buser\b|\bf['\"])""",
        "CRITICAL",
        "code_injection",
        "compile() with potential user input",
    ),
    (
        "py_dunder_import_dynamic",
        r"""\b__import__\s*\([^'\"][^)]*\)""",
        "HIGH",
        "code_injection",
        "__import__() with dynamic name",
    ),
    (
        "py_importlib_dynamic",
        r"""\bimportlib\.import_module\s*\([^'\"][^)]*\)""",
        "HIGH",
        "code_injection",
        "importlib.import_module() with dynamic name",
    ),
    # Node.js code injection
    (
        "js_eval_any",
        r"""\beval\s*\(""",
        "CRITICAL",
        "code_injection",
        "eval() in JavaScript -- verify input is not user-controlled",
    ),
    (
        "js_function_constructor",
        r"""\bnew\s+Function\s*\(""",
        "CRITICAL",
        "code_injection",
        "Function() constructor -- equivalent to eval",
    ),
    (
        "js_vm_run",
        r"""\bvm\.run(?:InNewContext|InThisContext|InContext)?\s*\(""",
        "HIGH",
        "code_injection",
        "vm.run*() -- verify input is not user-controlled",
    ),
    # Template injection
    (
        "template_injection_fstring",
        r"""(?:render|template|jinja|mako|render_template_string)\s*\(.*\bf['\"]""",
        "CRITICAL",
        "code_injection",
        "f-string in template rendering context (template injection)",
    ),
    (
        "template_injection_format",
        r"""(?:render|template|jinja|mako|render_template_string)\s*\(.*\.format\s*\(""",
        "CRITICAL",
        "code_injection",
        ".format() in template rendering context (template injection)",
    ),

    # -----------------------------------------------------------------
    # 2. COMMAND INJECTION
    # -----------------------------------------------------------------
    (
        "subprocess_shell_true",
        r"""\bsubprocess\.(?:call|run|Popen|check_output|check_call)\s*\("""
        r"""[^)]*shell\s*=\s*True""",
        "CRITICAL",
        "command_injection",
        "subprocess with shell=True -- command injection risk if input is variable",
    ),
    (
        "os_system_var",
        r"""\bos\.system\s*\(""",
        "CRITICAL",
        "command_injection",
        "os.system() -- always uses a shell; prefer subprocess without shell=True",
    ),
    (
        "os_popen_var",
        r"""\bos\.popen\s*\(""",
        "HIGH",
        "command_injection",
        "os.popen() -- shell command execution",
    ),
    (
        "child_process_exec",
        r"""\b(?:child_process\.exec|execSync|exec)\s*\(""",
        "CRITICAL",
        "command_injection",
        "child_process.exec() in Node.js -- uses shell by default",
    ),
    (
        "shell_backtick_var",
        r"""`[^`]*\$\{?\w+\}?[^`]*`""",
        "HIGH",
        "command_injection",
        "Backtick execution with variable interpolation",
    ),

    # -----------------------------------------------------------------
    # 3. SQL INJECTION
    # -----------------------------------------------------------------
    (
        "sql_fstring",
        r"""(?i)\bf['\"](?:[^'\"]*?)(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|"""
        r"""TRUNCATE|UNION|EXEC|EXECUTE)\b""",
        "CRITICAL",
        "sql_injection",
        "f-string in SQL query (SQL injection)",
    ),
    (
        "sql_format_method",
        r"""(?i)(?:['\"]\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|"""
        r"""TRUNCATE|UNION|EXEC|EXECUTE)\b[^'\"]*['\"])\.format\s*\(""",
        "CRITICAL",
        "sql_injection",
        ".format() in SQL query string (SQL injection)",
    ),
    (
        "sql_concat",
        r"""(?i)(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b[^;]*?\+\s*(?!['\"]\s*\+)""",
        "HIGH",
        "sql_injection",
        "String concatenation in SQL query",
    ),
    (
        "sql_percent_format",
        r"""(?i)(?:cursor\.execute|execute|executemany)\s*\(\s*['\"]"""
        r"""[^'\"]*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\b[^'\"]*%[sd]""",
        "CRITICAL",
        "sql_injection",
        "%-format in cursor.execute() (SQL