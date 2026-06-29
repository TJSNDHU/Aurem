"""007 Full Audit -- Comprehensive 6-phase security audit orchestrator.

Executes the complete 007 security audit pipeline:
  Phase 1: Surface Mapping      -- file inventory, entry points, dependencies
  Phase 2: Threat Modeling Hints -- identify components for STRIDE analysis
  Phase 3: Security Checklist    -- run all scanners, compile results
  Phase 4: Red Team Scenarios    -- template-based attack scenarios
  Phase 5: Blue Team Recs        -- hardening recommendations per finding
  Phase 6: Verdict               -- compute score and emit final verdict

Generates a comprehensive Markdown report saved to data/reports/ and prints
a summary to stdout.

Usage:
    python full_audit.py --target /path/to/project
    python full_audit.py --target /path/to/project --output markdown
    python full_audit.py --target /path/to/project --phase 3 --verbose
    python full_audit.py --target /path/to/project --output json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the 007 config hub (same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    BASE_DIR,
    DATA_DIR,
    REPORTS_DIR,
    SCANNABLE_EXTENSIONS,
    SKIP_DIRECTORIES,
    SCORING_WEIGHTS,
    SCORING_LABEL