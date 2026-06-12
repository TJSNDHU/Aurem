"""
CI guard (P1-6) — lean-prune drift protection.

The production registry deletes ~1,600 routes by prefix (_registry_lean_prune).
Each prune entry is justified as "0 frontend refs". This test enforces that
claim continuously: if ANY frontend `/api/...` call matches a pruned prefix or
exact path, the build fails — catching the drift that would 404 a live feature
in production only.

Run:  cd /app/backend && python -m pytest tests/test_lean_prune_drift.py -v
"""
import glob
import os
import re

from routers._registry_lean_prune import _PRUNE_PREFIXES, _PRUNE_EXACT

REPO_ROOT = "/app"
FRONTEND_GLOB = os.path.join(REPO_ROOT, "frontend/src/**/*.js*")
_NOISE = re.compile(r"\$\{|/api/foo$|/api/auth$|/api/password$")


def _frontend_api_refs() -> set[str]:
    refs: set[str] = set()
    for f in glob.glob(FRONTEND_GLOB, recursive=True):
        if "_archive" in f or "node_modules" in f:
            continue
        try:
            src = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in re.findall(r"[`\"'](/api/[A-Za-z0-9_\-/${}.:]+)", src):
            p = re.sub(r"\$\{[^}]+\}", "{p}", m).split("?")[0].rstrip("/")
            if len(p) > 5 and not _NOISE.search(p):
                refs.add(p)
    return refs


def test_no_frontend_ref_hits_a_pruned_prefix():
    refs = _frontend_api_refs()
    assert refs, "no frontend /api/ refs found — extractor broken?"

    violations = []
    for ref in sorted(refs):
        concrete = ref.replace("{p}", "X")
        if any(concrete.startswith(pref) for pref in _PRUNE_PREFIXES):
            violations.append((ref, "prefix"))
        elif concrete in _PRUNE_EXACT:
            violations.append((ref, "exact"))

    assert not violations, (
        "Lean-prune DRIFT — these frontend calls hit a pruned route and will "
        "404 in production:\n" + "\n".join(f"  {r}  ({why})" for r, why in violations)
    )
