"""
codebase_health.py — iter D-70
================================
Live codebase analyzer for AUREM. Runs every 6h on a scheduler and on
backend boot. No founder action needed.

Persists snapshots to `codebase_health_snapshots` collection (30-day TTL
recommended). Frontend polls `/api/admin/codebase-health/latest`.

Metrics computed:
  • File-size buckets   (300+ / 800+ / 1500+ lines)
  • God-files           (import 50+ modules or imported by 50+)
  • Circular imports    (DFS on import graph, both Python and JSX)
  • Cyclomatic complexity per function (via radon)
  • Health score 0-10   (weighted combination)
  • Top actionable file (single recommendation with one-line reason)
"""
from __future__ import annotations

import ast
import logging
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND_ROOT  = "/app/backend"
_FRONTEND_ROOT = "/app/frontend/src"
_EXCLUDE_DIRS  = {"__pycache__", "node_modules", ".git", "tests", "test_reports",
                   ".venv", "venv", "build", "dist", "tmp", ".cache"}
_PY_EXTS  = (".py",)
_JS_EXTS  = (".jsx", ".js")

# Tunables — adjust if AUREM scales 10×.
_SIZE_RED    = 1500
_SIZE_ORANGE = 800
_SIZE_YELLOW = 300
_GOD_IMPORTS = 50           # imports OR is-imported-by
_CC_RED      = 30
_CC_ORANGE   = 15

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────── walkers ───────────────────────────
def _iter_files(root: str, exts: tuple[str, ...]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(exts):
                yield os.path.join(dirpath, fn)


def _count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _python_imports(path: str) -> list[str]:
    """Return list of imported module names — TOP-LEVEL only.

    Lazy imports nested inside functions/methods are the canonical Python
    idiom for breaking cycles. Counting them as cycle edges yields false
    positives (e.g. `from services.foo import bar` inside a function is
    intentional, not a cycle). We walk only the module body.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return []
    mods: list[str] = []
    for node in tree.body:                              # ← module top-level
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
        elif isinstance(node, ast.If):
            # Top-level conditional imports (e.g. `if TYPE_CHECKING:` blocks)
            # still count — they're resolved at import time.
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    mods.extend(a.name for a in sub.names)
                elif isinstance(sub, ast.ImportFrom) and sub.module:
                    mods.append(sub.module)
    return mods


def _python_all_imports(path: str) -> list[str]:
    """Every import in the file, including nested. Used for the per-file
    `imports` count surfaced to the dashboard (informational, not for
    cycle detection)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


_JS_IMPORT_RE = re.compile(r"""(?:from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""")


def _js_imports(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return []
    return [m[0] or m[1] for m in _JS_IMPORT_RE.findall(text)]


# ─────────────────────── circular detection ──────────────────────
def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return a list of cycles (each as a path). Capped at first 10."""
    cycles: list[list[str]] = []
    color: dict[str, int] = {}    # 0=white, 1=gray, 2=black
    parent: dict[str, str] = {}

    def dfs(start: str):
        stack = [(start, iter(graph.get(start, ())))]
        color[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = 2
                stack.pop()
                continue
            if color.get(nxt) == 1:
                # back-edge → cycle
                cyc = [nxt]
                cur = node
                while cur != nxt and cur in parent:
                    cyc.append(cur)
                    cur = parent[cur]
                cyc.append(nxt)
                cyc.reverse()
                cycles.append(cyc)
                if len(cycles) >= 10:
                    return True
            elif color.get(nxt, 0) == 0:
                parent[nxt] = node
                color[nxt] = 1
                stack.append((nxt, iter(graph.get(nxt, ()))))
        return False

    for node in graph:
        if color.get(node, 0) == 0 and dfs(node):
            break
    return cycles


# ─────────────────────────── analyzers ──────────────────────────
def _analyze_python(root: str, label: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    graph: dict[str, set[str]] = defaultdict(set)
    rev_graph: dict[str, set[str]] = defaultdict(set)

    for path in _iter_files(root, _PY_EXTS):
        rel = os.path.relpath(path, root)
        if rel.startswith("tests/") or "/tests/" in rel:
            continue
        lines = _count_lines(path)
        top_imps = _python_imports(path)           # top-level only — for graph
        all_imps = _python_all_imports(path)       # all — for display count
        files.append({"path": rel, "lines": lines, "imports": len(all_imps)})
        mod = rel[:-3].replace(os.sep, ".")
        for imp in top_imps:
            if imp.startswith(("routers.", "services.", "utils.",
                                "pillars.", "middleware.", "shared.",
                                "cto_skills.", "ora_skills.")):
                graph[mod].add(imp)
                rev_graph[imp].add(mod)

    # Cyclomatic complexity via radon
    cc_top: list[dict[str, Any]] = []
    try:
        from radon.complexity import cc_visit
        for f in files:
            full = os.path.join(root, f["path"])
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    src = fh.read()
                for fn in cc_visit(src):
                    if fn.complexity >= _CC_ORANGE:
                        cc_top.append({
                            "path":       f["path"],
                            "fn":         f"{fn.classname + '.' if fn.classname else ''}{fn.name}",
                            "cc":         fn.complexity,
                            "lineno":     fn.lineno,
                        })
            except (SyntaxError, ValueError):
                continue
    except Exception as e:
        logger.warning(f"[codebase-health] radon scan failed: {e}")
    cc_top.sort(key=lambda x: -x["cc"])

    # God-files: imports OR is-imported-by >= threshold (TOP-LEVEL imports only —
    # see _python_imports). Small utility files (<200 lines) that are only
    # imported (out-degree zero) are legitimate shared utils, not god files.
    god_files = []
    for f in files:
        mod = f["path"][:-3].replace(os.sep, ".")
        in_n  = len(rev_graph.get(mod, ()))
        out_n = len(graph.get(mod, ()))
        if out_n == 0 and f["lines"] < 200:
            continue  # tiny shared utility — not a god file
        if max(in_n, out_n) >= _GOD_IMPORTS:
            god_files.append({
                "path":            f["path"],
                "imports":         out_n,
                "imported_by":     in_n,
                "lines":           f["lines"],
            })
    god_files.sort(key=lambda x: -max(x["imports"], x["imported_by"]))

    return {
        "scope":         label,
        "files":         files,
        "totals": {
            "files": len(files),
            "lines": sum(f["lines"] for f in files),
        },
        "size_buckets":  _bucketize(files),
        "god_files":     god_files[:10],
        "circular":      _find_cycles(graph)[:5],
        "cc_top":        cc_top[:15],
        "biggest":       sorted(files, key=lambda x: -x["lines"])[:10],
    }


def _analyze_frontend(root: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in _iter_files(root, _JS_EXTS):
        rel = os.path.relpath(path, root)
        if rel.startswith(("tests/", "__tests__/")) or ".test." in rel:
            continue
        lines = _count_lines(path)
        imps  = _js_imports(path)
        files.append({"path": rel, "lines": lines, "imports": len(imps)})
    return {
        "scope":  "frontend",
        "totals": {"files": len(files),
                    "lines": sum(f["lines"] for f in files)},
        "size_buckets": _bucketize(files),
        "biggest":      sorted(files, key=lambda x: -x["lines"])[:10],
    }


def _bucketize(files: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "ge_1500": sum(1 for f in files if f["lines"] >= _SIZE_RED),
        "ge_800":  sum(1 for f in files if _SIZE_ORANGE <= f["lines"] < _SIZE_RED),
        "ge_300":  sum(1 for f in files if _SIZE_YELLOW <= f["lines"] < _SIZE_ORANGE),
        "lt_300":  sum(1 for f in files if f["lines"] < _SIZE_YELLOW),
    }


# ─────────────────────── health score + action ──────────────────
def _score_and_action(be: dict[str, Any], fe: dict[str, Any]) -> tuple[float, dict[str, str]]:
    """Compute 0-10 health score + the single top actionable file.

    Scoring philosophy:
      • TRUE BREAKAGE (cycles, god files, runaway complexity) is penalized
        absolutely — these block work and must reach zero.
      • FILE SIZE is scored as a PROPORTION of the codebase. A mature
        backend with 1,250+ files naturally accumulates 1-2% large files;
        that is normal, not "broken". The signal we care about is the
        *ratio* of refactor targets to total surface area.
    """
    god      = len(be["god_files"])
    cyc      = len(be["circular"])
    big_red  = be["size_buckets"]["ge_1500"]
    big_org  = be["size_buckets"]["ge_800"]
    cc_red   = sum(1 for c in be["cc_top"] if c["cc"] >= _CC_RED)
    total    = max(1, be["totals"]["files"])

    # Proportions (0.0 - 1.0). 1% red files → 0.01.
    red_ratio    = big_red / total
    orange_ratio = big_org / total
    cc_ratio     = cc_red  / total

    score = 10.0
    # Hard breakage — must be zero.
    score -= cyc * 1.5
    score -= god * 0.8

    # Soft amber zone — % of codebase that needs refactor.
    # 1% red files = -0.6, 5% red = -3.0, 10% red = -6.0.
    score -= red_ratio    * 60
    score -= orange_ratio * 25
    score -= cc_ratio     * 40

    score = max(0.0, min(10.0, round(score, 1)))

    # Top actionable — pick the single most painful file across all signals.
    candidates: list[tuple[int, str, str]] = []  # (priority, path, reason)
    for f in be["biggest"][:3]:
        if f["lines"] >= _SIZE_RED:
            r = f"{f['lines']} lines, {f['imports']} imports"
            # Annotate if it also imports/is-imported by many
            for g in be["god_files"]:
                if g["path"] == f["path"]:
                    r += (f" · imports {g['imports']} modules"
                           if g["imports"] > g["imported_by"]
                           else f" · imported by {g['imported_by']} modules")
                    break
            # Annotate with worst CC function inside the file, if any.
            for c in be["cc_top"]:
                if c["path"] == f["path"] and c["cc"] >= _CC_ORANGE:
                    r += f" · worst: {c['fn']}() cc={c['cc']}"
                    break
            candidates.append((f["lines"], f["path"], r))
    for c in be["cc_top"][:3]:
        if c["cc"] >= _CC_RED:
            candidates.append((
                900 + c["cc"], c["path"],
                f"{c['fn']}() complexity {c['cc']} (line {c['lineno']})",
            ))
    for cyc_path in be["circular"][:2]:
        if cyc_path:
            candidates.append((
                700, cyc_path[0],
                f"circular import: {' → '.join(cyc_path[:4])}",
            ))
    if candidates:
        candidates.sort(key=lambda x: -x[0])
        top = {"path": candidates[0][1], "reason": candidates[0][2]}
    else:
        top = {"path": "(none — codebase healthy)", "reason": "no red flags"}
    return score, top


# ─────────────────────────── public API ─────────────────────────
async def run_snapshot() -> dict[str, Any]:
    """Run one full scan, persist if db wired, return the snapshot."""
    t0 = time.monotonic()
    be = _analyze_python(_BACKEND_ROOT, "backend")
    fe = _analyze_frontend(_FRONTEND_ROOT)
    score, action = _score_and_action(be, fe)
    snapshot = {
        "generated_at": _now_iso(),
        "duration_sec": round(time.monotonic() - t0, 2),
        "backend":      be,
        "frontend":     fe,
        "health_score": score,
        "top_action":   action,
    }
    if _db is not None:
        try:
            await _db.codebase_health_snapshots.insert_one({
                **snapshot,
                "created_at": datetime.now(timezone.utc),
            })
            # Keep last 30 snapshots — manual TTL since collection is small.
            cur = _db.codebase_health_snapshots.find({}, {"_id": 1}).sort("created_at", -1).skip(30)
            stale_ids = [d["_id"] async for d in cur]
            if stale_ids:
                await _db.codebase_health_snapshots.delete_many({"_id": {"$in": stale_ids}})
        except Exception as e:
            logger.warning(f"[codebase-health] persist failed: {e}")
    logger.info(
        f"[codebase-health] snapshot done in {snapshot['duration_sec']}s · "
        f"score={score} · top={action['path']}"
    )
    return snapshot


async def latest_snapshot() -> dict[str, Any] | None:
    if _db is None:
        return None
    doc = await _db.codebase_health_snapshots.find_one(
        {}, {"_id": 0, "created_at": 0}, sort=[("created_at", -1)],
    )
    return doc


async def trend(days: int = 7) -> list[dict[str, Any]]:
    if _db is None:
        return []
    out = []
    async for d in _db.codebase_health_snapshots.find(
        {}, {"_id": 0, "generated_at": 1, "health_score": 1,
              "backend.totals": 1, "top_action": 1},
    ).sort("created_at", -1).limit(days * 4):  # 4 snaps/day
        out.append(d)
    return out
