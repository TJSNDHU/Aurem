"""
AUREM Sovereign Boundary Lint (iter 322l — Day 2.1)
====================================================
Customer-ORA chat must NEVER import system-ORA modules.

Customer-facing chat code lives in `services/ora_god_mode.py`,
`routers/ora_chat_router.py`, and `routers/ora_council_router.py`. These
files MUST NOT import any of:
  - services.ora_council        (decision authority)
  - services.latency_guardian   (system self-heal)
  - services.sovereign_watchdog (system self-heal)
  - services.sovereign_memory   (memory guard)
  - services.autopilot_sentinel (anomaly detection)

Why
---
Sycophancy + system authority is the worst combination. A customer chat
endpoint that can read `learnings_pending_review` rows can leak the
Council's reasoning into helpful-sounding prose; one that can write to
those collections can poison the gate.

This script is meant to run:
  - locally as `python3 backend/scripts/lint_sovereign_boundary.py`
  - in CI as the only check that gates a deploy on this property

Exits 0 when clean, 1 when violation found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Customer-facing files that MUST stay isolated.
CUSTOMER_PATHS = [
    "services/ora_god_mode.py",
    "routers/ora_chat_router.py",
    "routers/ora_council_router.py",
]

# System modules that customer code is forbidden from importing.
FORBIDDEN_MODULES = [
    "services.ora_council",
    "services.latency_guardian",
    "services.sovereign_watchdog",
    "services.sovereign_memory",
    "services.autopilot_sentinel",
]

# Forbidden raw collection writes/reads — direct DB access bypasses the
# Memory Guard. Customer chat must go through the public read API
# (`get_promoted_learnings`) only.
FORBIDDEN_COLLECTIONS = [
    "learnings_pending_review",
    "sovereign_council_escalations",
    "sovereign_watchdog_log",
    "system_pulse_actions",
    "pillar_restart_requests",
]


def scan_file(path: Path) -> List[Tuple[int, str, str]]:
    """Return a list of (line_no, kind, snippet) violations."""
    violations: List[Tuple[int, str, str]] = []
    if not path.exists():
        return violations
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip pure comment lines for readability — they describe the
        # boundary intentionally and shouldn't trip the lint.
        if stripped.startswith("#"):
            continue
        for mod in FORBIDDEN_MODULES:
            patterns = [
                rf"^\s*from\s+{re.escape(mod)}\b",
                rf"^\s*import\s+{re.escape(mod)}\b",
                rf"importlib\.import_module\(['\"]{re.escape(mod)}",
            ]
            for pat in patterns:
                if re.search(pat, line):
                    violations.append((i, f"forbidden_import:{mod}", stripped))
                    break
        for coll in FORBIDDEN_COLLECTIONS:
            # Only flag direct collection writes/reads (db.<coll>.<op> or
            # db["<coll>"].<op>). Comments referencing the name are fine.
            if re.search(rf"\bdb\.{re.escape(coll)}\b", line):
                violations.append((i, f"forbidden_collection:{coll}", stripped))
            elif re.search(rf"\bdb\[['\"]{re.escape(coll)}['\"]\]", line):
                violations.append((i, f"forbidden_collection:{coll}", stripped))
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent  # /app/backend
    all_violations: List[Tuple[Path, int, str, str]] = []
    for rel in CUSTOMER_PATHS:
        p = repo_root / rel
        for line_no, kind, snippet in scan_file(p):
            all_violations.append((p, line_no, kind, snippet))

    if not all_violations:
        print("[sovereign-boundary] ✅ clean — customer ORA stays isolated.")
        return 0

    print("[sovereign-boundary] ❌ FAIL — customer ORA must not touch system memory.")
    for p, line_no, kind, snippet in all_violations:
        print(f"  {p.relative_to(repo_root.parent)}:{line_no}  [{kind}]")
        print(f"      {snippet}")
    print()
    print("If a system-side helper is genuinely needed by customer ORA, route")
    print("through a thin read-only adapter (e.g. `services.sovereign_memory.get_promoted_learnings`).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
