"""007 Dependency Scanner -- Supply chain and dependency security analyzer.

Analyzes dependency security across Python and Node.js projects by inspecting
dependency files (requirements.txt, package.json, Dockerfiles, etc.) for version
pinning, known risky patterns, and supply chain best practices.

Usage:
    python dependency_scanner.py --target /path/to/project
    python dependency_scanner.py --target /path/to/project --output json --verbose
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
logger = config.setup_logging("007-dependency-scanner")


# ---------------------------------------------------------------------------
# Dependency file patterns
# ---------------------------------------------------------------------------

# Python dependency files
PYTHON_DEP_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements_dev.txt",
    "requirements-test.txt",
    "requirements_test.txt",
    "requirements-prod.txt",
    "requirements_prod.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
}

# Node.js dependency files
NODE_DEP_FILES = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
}

# Docker files (matched by prefix)
DOCKER_PREFIXES = ("Dockerfile", "dockerfile", "docker-compose")

# All dependency file names (for fast lookup)
ALL_DEP_FILES = PYTHON_DEP_FILES | NODE_DEP_FILES

# Regex to match requirements*.txt variants
_REQUIREMENTS_RE = re.compile(
    r"""^requirements[-_]?\w*\.txt$""", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Python analysis patterns
# ---------------------------------------------------------------------------

# Pinned:   package==1.2.3
# Hashed:   package==1.2.3 --hash=sha256:abc...
# Loose:    package>=1.0  package~=1.0  package!=1.0  package  package<=2
# Comment:  # this is a comment
# Options:  -r other.txt  --find-links  -e .  etc.

_PY_COMMENT_RE = re.compile(r"""^\s*#""")
_PY_OPTION_RE = re.compile(r"""^\s*-""")
_PY_BLANK_RE = re.compile(r"""^\s*$""")

# Matches: package==version  or  package[extras]==version
_PY_PINNED_RE = re.compile(
    r"""^([A-Za-z0-9_][A-Za-z0-9._-]*)(?:\[.*?\])?\s*==\s*[\d]""",
)

# Matches any package line (not comment, not option, not blank)
_PY_PACKAGE_RE = re.compile(
    r"""^([A-Za-z0-9_][A-Za-z0-9._-]*)""",
)

# Hash present
_PY_HASH_RE = re.compile(r"""--hash[=:]""")

# Known risky Python packages or patterns
_RISKY_PYTHON_PACKAGES = {
    "pyyaml": "PyYAML with yaml.load() without SafeLoader enables arbitrary code execution; use yaml.safe_load() or yaml.load(..., Loader=yaml.SafeLoader) instead",
    "pickle": "pickle module allows arbitrary code execution during deserialization",
    "shelve": "shelve uses pickle internally, same deserialization risks",
    "marshal": "marshal module can execute arbitrary code during deserialization",
    "dill": "dill extends pickle with same arbitrary code execution risks",
    "cloudpickle": "cloudpickle extends pickle with same security concerns",
    "jsonpickle": "jsonpickle can deserialize to arbitrary objects",
    "pyinstaller": "PyInstaller bundles can hide malicious code in executables",
    "subprocess32": "Deprecated subprocess replacement; use stdlib subprocess instead",
}


# ---------------------------------------------------------------------------
# Node.js analysis patterns
# ---------------------------------------------------------------------------

# Exact version:  "1.2.3"
# Pinned prefix:  "1.2.3" (no ^ or ~ or * or > or <)
# Loose:          "^1.2.3"  "~1.2.3"  ">=1.0"  "*"  "latest"

_NODE_EXACT_VERSION_RE = re.compile(
    r"""^\d+\.\d+\.\d+$"""
)

_NODE_LOOSE_INDICATORS = re.compile(
    r"""^[\^~*><=]|latest|next|canary""", re.IGNORECASE
)

# Risky postinstall script patterns
_NODE_RISKY_SCRIPTS = re.compile(
    r"""(?:curl|wget|fetch|http|eval|exec|child_process|\.sh\b|powershell)""",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Dockerfile analysis patterns
# ---------------------------------------------------------------------------

_DOCKER_FROM_RE = re.compile(
    r"""^\s*FROM\s+(\S+)""", re.IGNORECASE
)

_DOCKER_FROM_LATEST_RE = re.compile(
    r"""(?::latest\s*$|^[^:]+\s*$)"""
)

_DOCKER_USER_RE = re.compile(
    r"""^\s*USER\s+""", re.IGNORECASE
)

_DOCKER_COPY_SENSITIVE_RE = re.compile(
    r"""^\s*(?:COPY|ADD)\s+.*?(?:\.env|\.key|\.pem|\.p12|\.pfx|id_rsa|id_ed25519|\.secret)""",
    re.IGNORECASE,
)

_DOCKER_CURL_PIPE_RE = re.compile(
    r"""(?:curl|wget)\s+[^|]*\|\s*(?:bash|sh|zsh|python|perl|ruby|node)""",
    re.IGNORECASE,
)

# Known trusted base images (prefixes)
_DOCKER_TRUSTED_BASES = {
    "python", "node", "golang", "ruby", "openjdk", "amazoncorretto",
    "alpine", "ubuntu", "debian", "centos", "fedora", "archlinux",
    "nginx", "httpd", "redis", "postgres", "mysql", "mongo", "memcached",
    "mcr.microsoft.com/", "gcr.io/", "ghcr.io/", "docker.io/library/",
    "registry.access.redhat.com/",
}


# ---------------------------------------------------------------------------
# Finding builder
# ---------------------------------------------------------------------------

def _make_finding(
    file: str,
    line: int,
    severity: str,
    description: str,
    recommendation: str,
    pattern: str = "dependency",
) -> dict:
    """Create a standardized finding dict.

    Args:
        file:           Absolute path to the dependency file.
        line:           Line number where the issue was found (1-based, 0 if N/A).
        severity:       CRITICAL, HIGH, MEDIUM, or LOW.
        description:    Human-readable description of the issue.
        recommendation: Actionable fix suggestion.
        pattern:        Finding sub-type for aggregation.

    Returns:
        Finding dict compatible with other 007 scanners.
    """
    return {
        "type": "supply_chain",
        "pattern": pattern,
        "severity": severity,
        "file": file,
        "line": line,
        "description": description,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Python dependency analysis
# ---------------------------------------------------------------------------

def analyze_requirements_txt(filepath: Path, verbose: bool = False) -> dict:
    """Analyze a Python requirements.txt file.

    Returns:
        Dict with keys: deps_total, deps_pinned, deps_hashed,
        deps_unpinned, findings.
    """
    findings: list[dict] = []
    file_str = str(filepath)
    deps_total = 0
    deps_pinned = 0
    deps_hashed = 0
    deps_unpinned: list[str] = []

    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        if verbose:
            logger.debug("Cannot read %s: %s", filepath, exc)
        return {
            "deps_total": 0, "deps_pinned": 0, "deps_hashed": 0,
            "deps_unpinned": [], "find