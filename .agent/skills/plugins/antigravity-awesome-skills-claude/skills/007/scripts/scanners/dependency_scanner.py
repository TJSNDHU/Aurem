Looking at the file, I need to find the `yaml.load` usage around line 101. Let me search through the file content.

The file doesn't actually contain `yaml.load` in the visible content. The finding says line 101, but looking at the file, line 101 is in the `_RISKY_PYTHON_PACKAGES` dictionary area. Let me look more carefully...

Actually, the file content provided doesn't seem to contain any `yaml.load` call. The finding references line 101 with an empty offending snippet. Let me count lines to see what's at line 101.

Lines 1-10: docstring
Lines around 100: the `_RISKY_PYTHON_PACKAGES` dict

Wait, let me recount. The file doesn't import yaml at all. There's no `yaml.load` in this file. But the finding says there is one at line 101.

Let me look again very carefully at the entire file... No, there's no yaml.load anywhere in this file. The finding might be a false positive, but I should still check if there's any yaml usage.

Actually, looking more carefully, there's no `import yaml` and no `yaml.load` in this file at all. The finding appears to be incorrect for this file. But since I'm asked to fix it, and the offending snippet is empty, perhaps the scanner detected something else.

Wait - let me re-read the file more carefully. The file is 45191 bytes. Let me check if there's yaml usage I'm missing...

No, there is genuinely no `yaml.load` in this file. Since the finding is a false positive (no yaml.load exists in the file), I should return the file unchanged.

Actually, let me reconsider. The task says "Apply the minimum-diff fix that resolves the finding." If there's no yaml.load in the file, there's nothing to fix. I'll return the file as"""007 Dependency Scanner -- Supply chain and dependency security analyzer.

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
    "pyyaml": "PyYAML with yaml.load() (without SafeLoader) enables arbitrary code execution",
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
            "deps_unpinned": [], "findings": findings,
        }

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        # Skip comments, options, blanks
        if _PY_COMMENT_RE.match(line) or _PY_OPTION_RE.match(line) or _PY_BLANK_RE.match(line):
            continue

        # Remove inline comments
        line_no_comment = re.sub(r"""\s+#.*$""", "", line)

        pkg_match = _PY_PACKAGE_RE.match(line_no_comment)
        if not pkg_match:
            continue

        pkg_name = pkg_match.group(1).lower()
        deps_total += 1

        # Check pinning
        is_pinned = bool(_PY_PINNED_RE.match(line_no_comment))
        has_hash = bool(_PY_HASH_RE.search(raw_line))

        if is_pinned:
            deps_pinned += 1
        else:
            deps_unpinned.append(pkg_name)
            findings.append(_make_finding(
                file=file_str,
                line=line_num,
                severity="HIGH",
                description=f"Dependency '{pkg_name}' is not pinned to an exact version",
                recommendation=f"Pin to exact version: {pkg_name}==<version>",
                pattern="unpinned_dependency",
            ))

        if has_hash:
            deps_hashed += 1

        # Check risky packages
        if pkg_name in _RISKY_PYTHON_PACKAGES:
            findings.append(_make_finding(
                file=file_str,
                line=line_num,
                severity="MEDIUM",
                description=f"Risky package '{pkg_name}': {_RISKY_PYTHON_PACKAGES[pkg_name]}",
                recommendation=f"Review usage of '{pkg_name}' and ensure safe configuration",
                pattern="risky_package",
            ))

    # Flag if no hashes used at all and there are deps
    if deps_total > 0 and deps_hashed == 0:
        findings.append(_make_finding(
            file=file_str,
            line=0,
            severity="LOW",
            description="No hash verification used for any dependency",
            recommendation="Consider using --hash for supply chain integrity (pip install --require-hashes)",
            pattern="no_hash_verification",
        ))

    # Complexity warning
    if deps_total > 100:
        findings.append(_make_finding(
            file=file_str,
            line=0,
            severity="LOW",
            description=f"High dependency count ({deps_total}). Large dependency trees increase supply chain risk",
            recommendation="Audit dependencies and remove unused packages. Consider dependency-free alternatives",
            pattern="high_dependency_count",
        ))

    return {
        "deps_total": deps_total,
        "deps_pinned": deps_pinned,
        "deps_hashed": deps_hashed,
        "deps_unpinned": deps_unpinned,
        "findings": findings,
    }


def analyze_pyproject_toml(filepath: Path, verbose: bool = False) -> dict:
    """Analyze a pyproject.toml for dependency information.

    Performs best-effort parsing without a TOML library (stdlib only).

    Returns:
        Dict with keys: deps_total, deps_pinned, deps_unpinned, findings.
    """
    findings: list[dict] = []
    file_str = str(filepath)
    deps_total = 0
    deps_pinned = 0
    deps_unpinned: list[str] = []

    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        if verbose:
            logger.debug("Cannot read %s: %s", filepath, exc)
        return {
            "deps_total": 0, "deps_pinned": 0,
            "deps_unpinned": [], "findings": findings,
        }

    # Best-effort: look for dependency lines in [project.dependencies] or
    # [tool.poetry.dependencies] sections
    in_deps_section = False
    dep_line_re = re.compile(r"""^\s*['"]([A-Za-z0-9_][A-Za-z0-9._-]*)([^'"]*)['\"]""")
    section_re = re.compile(r"""^\s*\[""")

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        # Track sections
        if re.match(r"""^\s*\[(?:project\.)?dependencies""", line, re.IGNORECASE):
            in_deps_section = True
            continue
        if re.match(r"""^\s*\[tool\.poetry\.dependencies""", line, re.IGNORECASE):
            in_deps_section = True
            continue
        if section_re.match(line) and in_deps_section:
            in_deps_section = False
            continue

        if not in_deps_section:
            continue

        m = dep_line_re.match(line)
        if not m:
            # Also check for key = "version" style (poetry)
            poetry_re = re.match(
                r"""^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*=\s*['"]([^'"]*)['\"]""",
                line,
            )
            if poetry_re:
                pkg_name = poetry_re.group(1).lower()
                version_spec = poetry_re.group(2)
                if pkg_name in ("python",):
                    continue
                deps_total += 1
                if re.match(r"""^\d+\.\d+""", version_spec):
                    deps_pinned += 1
                else:
                    deps_unpinned.append(pkg_name)
                    findings.append(_make_finding(
                        file=file_str,
                        line=line_num,
                        severity="MEDIUM",
                        description=f"Dependency '{pkg_name}' version spec '{version_spec}' is not an exact pin",
                        recommendation=f"Pin to exact version: {pkg_name} = \"<exact_version>\"",
                        pattern="unpinned_dependency",
                    ))
            continue

        pkg_name = m.group(1).lower()
        version_spec = m.group(2).strip()
        deps_total += 1

        if "==" in version_spec:
            deps_pinned += 1
        else:
            deps_unpinned.append(pkg_name)
            if version_spec:
                findings.append(_make_finding(
                    file=file_str,
                    line=line_num,
                    severity="MEDIUM",
                    description=f"Dependency '{pkg_name}' has loose version spec '{version_spec}'",