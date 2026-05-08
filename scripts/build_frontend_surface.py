#!/usr/bin/env python3
"""
Build a static Python module containing every /api/... literal referenced in
the frontend source tree. The module is shipped inside the backend container
so the Endpoint Evidence Classifier can compute the 'surface' dignity signal
in production, where /app/frontend/src is not mounted.

iter 277 (rev-b): switched from JSON file (`backend/data/frontend_surface.json`)
to a Python module (`backend/routers/_frontend_surface_data.py`).
Emergent's deploy reliably copies everything under `backend/routers/` but does
NOT copy arbitrary `backend/data/` JSON files, so the JSON approach failed
silently in production.

Output: /app/backend/routers/_frontend_surface_data.py

Schema:
    BUILT_AT: str    — ISO8601 timestamp
    SRC_ROOT: str    — source tree scanned
    SURFACE_MANIFEST: dict[str, list[str]]
        { "/api/admin/pillars-map/overview": ["platform/AdminPillarsMap.jsx"], ... }

Run:
    python3 /app/scripts/build_frontend_surface.py
"""
from __future__ import annotations

import json
import os
import pprint
import subprocess
import sys
from datetime import datetime, timezone

SRC_ROOT = "/app/frontend/src"
OUTPUT   = "/app/backend/routers/_frontend_surface_data.py"

API_PATTERN = r"/api/[a-zA-Z0-9/_\-]+"


def build_manifest() -> dict:
    if not os.path.isdir(SRC_ROOT):
        print(f"[surface] ERROR: {SRC_ROOT} not found", file=sys.stderr)
        sys.exit(1)

    proc = subprocess.run(
        [
            "grep", "-R", "-o", "-E",
            "--include=*.js", "--include=*.jsx",
            "--include=*.ts", "--include=*.tsx",
            "--exclude-dir=node_modules", "--exclude-dir=build",
            "--exclude-dir=dist", "--exclude-dir=.next",
            API_PATTERN,
            SRC_ROOT,
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )

    manifest: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        path, match = line.split(":", 1)
        rel = path.replace(SRC_ROOT + "/", "")
        manifest.setdefault(match, []).append(rel)

    # Deduplicate + cap at 20 files per endpoint
    for key in manifest:
        manifest[key] = sorted(set(manifest[key]))[:20]

    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "src_root": SRC_ROOT,
        "endpoint_count": len(manifest),
        "manifest": manifest,
    }


def main() -> None:
    data = build_manifest()
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    # Serialize as valid Python literal
    body = (
        '"""AUTO-GENERATED — DO NOT EDIT.\n'
        '\n'
        'Run `python3 /app/scripts/build_frontend_surface.py` to regenerate.\n'
        '\n'
        'Captured by a grep of /app/frontend/src/**/*.{js,jsx,ts,tsx} for\n'
        '`/api/…` literals. Consumed by routers/endpoint_audit_router.py to\n'
        'compute the \'surface\' dignity signal in production containers\n'
        'that do not ship frontend source files.\n'
        '"""\n'
        'from __future__ import annotations\n'
        '\n'
        f'BUILT_AT: str = {data["built_at"]!r}\n'
        f'SRC_ROOT: str = {data["src_root"]!r}\n'
        f'ENDPOINT_COUNT: int = {data["endpoint_count"]}\n'
        '\n'
        'SURFACE_MANIFEST: dict[str, list[str]] = '
        + pprint.pformat(data["manifest"], width=120, sort_dicts=True)
        + '\n'
    )
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"[surface] Wrote {OUTPUT}")
    print(f"[surface] {data['endpoint_count']} distinct /api/ literals found")
    print(f"[surface] built_at: {data['built_at']}")


if __name__ == "__main__":
    main()
