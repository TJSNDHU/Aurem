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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

logger = config.setup_logging("007-dependency-scanner")

# Python dependency files
PYTHON_DEP_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements_dev.txt",
    "requirements-test.txt",
    "requirements_test.txt",
    "