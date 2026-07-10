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
    SCORING_LABELS,
    SEVERITY,
    LIMITS,
    ensure_directories,
    get_verdict,
    get_timestamp,
    log_audit_event,
    setup_logging,
    calculate_weighted_score,
)

# ---------------------------------------------------------------------------
# Import scanners
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent / "scanners"))

import secrets_scanner  # noqa: E402
import dependency_scanner  # noqa: E402
import injection_scanner  # noqa: E402
import quick_scan  # noqa: E402
import score_calculator  # noqa: E402

# ---------------------------------------------------------------------------
# Import audit templates (extracted to reduce file size)
# ---------------------------------------------------------------------------
from audit_templates import (  # noqa: E402
    _RED_TEAM_TEMPLATES,
    _RED_TEAM_FALLBACK,
    _BLUE_TEAM_TEMPLATES,
    _BLUE_TEAM_FALLBACK,
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = setup_logging("007-full-audit")


# =========================================================================
# PHASE IMPLEMENTATIONS
# =========================================================================

def _phase1_surface_mapping(target: Path, verbose: bool = False) -> dict:
    """Phase 1: Surface Mapping -- inventory files, entry points, dependencies."""
    logger.info("Phase 1: Surface Mapping")

    files_by_type: dict[str, int] = {}
    entry_points: list[str] = []
    dependency_files: list[str] = []
    config_files: list[str] = []
    total_files = 0

    _entry_point_patterns = [
        re.compile(r"""(?i)(?:^main\.py|^app\.py|^server\.py|^index\.\w+|^manage\.py)"""),
        re.compile(r"""(?i)(?:^wsgi\.py|^asgi\.py|^gunicorn|^uvicorn)"""),
        re.compile(r"""(?i)(?:^Dockerfile|^docker-compose)"""),
        re.compile(r"""(?i)(?:\.github[/\\]workflows|Jenkinsfile|\.gitlab-ci)"""),
    ]

    _dep_file_names = {
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "setup.py", "setup.cfg", "pyproject.toml", "Pipfile", "Pipfile.lock",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
        "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
    }

    _config_extensions = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env"}

    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]

        for fname in filenames:
            total_files += 1
            fpath = Path(root) / fname
            suffix = fpath.suffix.lower()

            # Categorize by extension
            ext_key = suffix if suffix else "(no extension)"
            files_by_type[ext_key] = files_by_type.get(ext_key, 0) + 1

            # Detect entry points
            for pat in _entry_point_patterns:
                if pat.search(fname) or pat.search(str(fpath)):
                    entry_points.append(str(fpath))
                    break

            # Detect dependency files
            if fname.lower() in _dep_file_names:
                dependency_files.append(str(fpath))

            # Detect config files
            if suffix in _config_extensions or fname.lower().startswith(".env"):
                config_files.append(str(fpath))

    # Sort by count descending
    sorted_types = sorted(files_by_type.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_files": total_files,
        "files_by_type": dict(sorted_types),
        "entry_points": sorted(set(entry_points)),
        "dependency_files": sorted(set(dependency_files)),
        "config_files": sorted(set(config_files)),
    }


def _phase2_threat_modeling_hints(surface_map: dict, findings: list[dict]) -> dict:
    """Phase 2: Threat Modeling Hints -- identify components for STRIDE analysis."""
    logger.info("Phase 2: Threat Modeling Hints")

    components: list[dict] = []

    # Entry points are high-value STRIDE targets
    for ep in surface_map.get("entry_points", []):
        components.append({
            "component": ep,
            "type": "entry_point",
            "stride_focus": ["