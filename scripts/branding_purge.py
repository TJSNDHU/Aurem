#!/usr/bin/env python3
"""
Branding purge — replace ReRoots customer-facing brand text with AUREM.

Strict rules (per user spec — "Do NOT change variable names or logic,
only brand text strings"):

  REPLACE:
    "ReRoots"          → "AUREM"
    "Reroots"          → "AUREM"
    "RE-Roots"         → "AUREM"
    "reroots.ca"       → "aurem.live"
    "@reroots.ca"      → "@aurem.live"

  DO NOT TOUCH:
    "reroots"          (lowercase — used as tenant_id / brand_id / DB key)
    "REROOTS"          (UPPERCASE enum constant)
    "reroots_*" / "*_reroots"  (snake_case identifiers)
    Anything inside binary/cache/log/data dirs

Skip dirs: node_modules, .git, __pycache__, build, .agent, generated_reports,
           data, graphify-out, .claude, .ruff_cache, archive, memory/_archive,
           uploads, _archive, .chromadb

Skip files: any file whose name starts with `test_` or ends `_test.py`,
            anything in a `tests/` directory.

Also skip the explicit safety-listed paths where keeping the old word is
required (legacy DB seed scripts + rls_security defaults):
  - scripts/reroots_recover.py (intentional legacy admin recovery tool)
  - backend/rls_security.py (DB enum + migration default)
  - backend/brands_config.py (legacy brand config)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path("/app")
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "build", ".agent",
    "generated_reports", "data", "graphify-out", ".claude",
    ".ruff_cache", "archive", "uploads", "_archive", ".chromadb",
    "tests", "test_reports",
}
SKIP_FILE_PARTS = (
    "/memory/_archive/",
)
SAFETY_LISTED_PATHS = {
    ROOT / "scripts" / "reroots_recover.py",
    ROOT / "backend" / "rls_security.py",
    ROOT / "backend" / "brands_config.py",
    # this script itself
    ROOT / "scripts" / "branding_purge.py",
}
EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".html", ".css", ".json", ".yml", ".yaml"}

# Ordered: domain replacements FIRST so the rest don't touch the domain match.
RULES = [
    (re.compile(r"@reroots\.ca"), "@aurem.live"),
    (re.compile(r"reroots\.ca"), "aurem.live"),
    (re.compile(r"ReRoots"), "AUREM"),
    (re.compile(r"Reroots"), "AUREM"),
    (re.compile(r"RE-Roots"), "AUREM"),
]


def should_skip_dir(p: Path) -> bool:
    return any(part in SKIP_DIRS for part in p.parts)


def should_skip_file(p: Path) -> bool:
    if p in SAFETY_LISTED_PATHS:
        return True
    s = str(p)
    if any(part in s for part in SKIP_FILE_PARTS):
        return True
    name = p.name
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.js") or name.endswith(".test.jsx"):
        return True
    return False


def walk_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in EXTS:
            continue
        if should_skip_dir(p):
            continue
        if should_skip_file(p):
            continue
        yield p


def transform(src: str) -> tuple[str, int]:
    out = src
    n = 0
    for pat, repl in RULES:
        out, hits = pat.subn(repl, out)
        n += hits
    return out, n


def main(dry: bool) -> None:
    touched = 0
    rewrites = 0
    sample = []
    for p in walk_files():
        try:
            src = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        if "reroots" not in src.lower():
            continue
        out, n = transform(src)
        if out == src:
            continue
        touched += 1
        rewrites += n
        if len(sample) < 10:
            sample.append((str(p.relative_to(ROOT)), n))
        if not dry:
            p.write_text(out, encoding="utf-8")
    print("[branding_purge] summary")
    print(f"  files changed : {touched}{' (dry-run)' if dry else ''}")
    print(f"  text rewrites : {rewrites}")
    print("  sample :")
    for s, n in sample:
        print(f"    {n:3d}  {s}")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
