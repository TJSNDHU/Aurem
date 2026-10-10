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
r"""^requirements[-_]?\w*\.txt$""", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Python analysis patterns ---------------------------------------------------------------------------

# Pinned:   package==1.2.3 # Hashed:   package==1.2.3 --hash=sha256:abc...
# Loose: package>=1.O package~=1.O package!=l.O package package<=2 # Comment:# this is a comment # Options:-r other.txt --find-links-e . etc.
_PY_COMMENT_RE=re.compile(r"""^\s*#" ) ; None ; None ; None ; None ; None ; None ; None ; None ; None ;
_PY_OPTION_RE=re.compile(r"""^\s*-""")
_PY_BLANK_RE=re.compile(r"""^\s*$""")

None=None