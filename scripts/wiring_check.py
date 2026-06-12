#!/usr/bin/env python3
"""
wiring_check.py — AUREM frontend <-> backend wiring verifier.

Three modes:
  python wiring_check.py                          # static diff (repo root)
  python wiring_check.py --live https://aurem.live # verify against /openapi.json
  python wiring_check.py --orphans                # unimported frontend components

Static mode is best-effort (registry is dynamic); LIVE mode is the truth.
Exit code 1 if any frontend call has no live route — wire it into CI.
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
       if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "scripts" \
       else os.getcwd()

NOISE = re.compile(r"\$\{|/api/foo$|/api/auth$|/api/password$")


def frontend_paths() -> set[str]:
    out: set[str] = set()
    for f in glob.glob(os.path.join(ROOT, "frontend/src/**/*.js*"), recursive=True):
        if "_archive" in f or "node_modules" in f:
            continue
        try:
            src = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in re.findall(r"[`\"'](/api/[A-Za-z0-9_\-/${}.:]+)", src):
            p = re.sub(r"\$\{[^}]+\}", "{p}", m).split("?")[0].rstrip("/")
            if len(p) > 5 and not NOISE.search(p):
                out.add(p)
    return out


def backend_paths_static() -> set[str]:
    out: set[str] = set()
    pats = [os.path.join(ROOT, "backend/routers/*.py"),
            os.path.join(ROOT, "backend/routes/**/*.py")]
    for pat in pats:
        for f in glob.glob(pat, recursive=True):
            try:
                src = open(f, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            pm = re.search(r"APIRouter\([^)]*prefix\s*=\s*[fr]?[\"']([^\"']+)", src)
            prefix = pm.group(1) if pm else ""
            for _v, path in re.findall(
                    r"@\w+\.(get|post|put|delete|patch)\(\s*[fr]?[\"']([^\"']*)", src):
                full = (prefix + path).rstrip("/") or "/"
                out.add(full)
                out.add("/api" + full if not full.startswith("/api") else full)
    return out


def backend_paths_live(base: str) -> set[str]:
    url = base.rstrip("/") + "/openapi.json"
    with urllib.request.urlopen(url, timeout=15) as r:
        spec = json.load(r)
    return {p.rstrip("/") for p in spec.get("paths", {})}


def matches(fe: str, be: set[str]) -> bool:
    segs = fe.replace("{p}", "X").split("/")
    for b in be:
        bs = b.split("/")
        if len(bs) != len(segs):
            continue
        if all(a == c or a.startswith("{") or c == "X" for a, c in zip(bs, segs)):
            return True
    return False


def orphan_components() -> list[str]:
    src_dir = os.path.join(ROOT, "frontend/src")
    comps = {}
    for f in glob.glob(os.path.join(src_dir, "platform/**/*.jsx"), recursive=True):
        if "_archive" in f:
            continue
        comps[os.path.splitext(os.path.basename(f))[0]] = f
    blob = ""
    for f in glob.glob(os.path.join(src_dir, "**/*.js*"), recursive=True):
        if "_archive" in f:
            continue
        try:
            blob += open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            pass
    orphans = []
    for name, path in sorted(comps.items()):
        # imported if its name appears outside its own file >= 2 times
        if blob.count(name) <= open(path, encoding="utf-8",
                                    errors="ignore").read().count(name):
            orphans.append(os.path.relpath(path, ROOT))
    return orphans


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", metavar="BASE_URL")
    ap.add_argument("--orphans", action="store_true")
    args = ap.parse_args()

    if args.orphans:
        o = orphan_components()
        print(f"Orphan platform components: {len(o)}")
        for p in o:
            print("  -", p)
        return 0

    fe = frontend_paths()
    be = backend_paths_live(args.live) if args.live else backend_paths_static()
    mode = "LIVE /openapi.json" if args.live else "STATIC (best-effort)"
    missing = sorted(p for p in fe if not matches(p, be))

    print(f"Mode: {mode}")
    print(f"Frontend /api/ refs: {len(fe)}   Backend routes: {len(be)}")
    print(f"Frontend calls with NO backend match: {len(missing)}")
    for p in missing:
        print("  X", p)
    return 1 if (missing and args.live) else 0


if __name__ == "__main__":
    sys.exit(main())
