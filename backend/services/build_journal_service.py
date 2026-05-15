"""
build_journal_service.py — iter 322au (May 11, 2026)
=========================================================
THE AUREM BUILD JOURNAL — every code change from Day 1 onward gets captured
into `db.build_journal` and organically fed into the ORA Learning Stack.

Five phases (all running automatically — no human prompt required):
  1. Git Log Backfill  → one-shot historical import (158+ commits → journal rows)
  2. Live Build Hook   → APScheduler cron every 10 min, ingests new commits
  3. Public Build Log  → /build-log page reads from this collection
  4. Founder Digest    → daily 23:00 Toronto Resend email summarising today
  5. ORA Pattern Miner → nightly 03:30 UTC analyses journal → fix_patterns

Storage shape (`db.build_journal`):
{
  "_id": <commit_sha>,
  "sha": "...", "short": "8605e67",
  "ts": ISO datetime,
  "iter": "322au" or null,
  "message": "...",
  "files_changed": 12,
  "additions": 247,
  "deletions": 31,
  "files": ["routers/x.py", "platform/Y.jsx", ...],
  "category": "feat|fix|refactor|docs|infra|test|chore",
  "shipped": ["white-label UI", "booking widget", ...],   # extracted from msg
  "test_status": "pass|fail|unknown",                     # cross-ref test_reports/
  "phase": 1|2,                                            # backfill or live
  "ingested_at": ISO datetime,
  "ora_learned": true|false,
}
"""

from __future__ import annotations

import os
import re
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = "/app"
ITER_RE   = re.compile(r"iter[\s_]*(\d{2,4}[a-z]{0,2})", re.IGNORECASE)
SHIPPED_RE = re.compile(r"(?:shipped|added|built|launched|ship)[:\s]+([^\.\n]+)", re.IGNORECASE)


# ────────────────────────────────────────────────────────────────────
# Git helpers
# ────────────────────────────────────────────────────────────────────
_GIT_AVAILABLE: Optional[bool] = None


def _git(*args: str) -> str:
    """Run `git -C /app <args>`. Caches binary availability after first
    call so production containers without `git` installed don't spam
    warning logs on every scheduler tick (was: ~3 warnings/minute)."""
    global _GIT_AVAILABLE
    if _GIT_AVAILABLE is False:
        return ""
    try:
        out = subprocess.check_output(
            ["git", "-C", REPO_ROOT, *args],
            stderr=subprocess.DEVNULL, timeout=30,
        )
        _GIT_AVAILABLE = True
        return out.decode("utf-8", errors="replace")
    except FileNotFoundError:
        if _GIT_AVAILABLE is None:
            logger.info("[build-journal] git binary not present — disabling for this pod")
        _GIT_AVAILABLE = False
        return ""
    except Exception as e:
        # Real git error — keep logging but rate-limit by only emitting once.
        if _GIT_AVAILABLE is None:
            logger.warning(f"[build-journal] git {args}: {e}")
            _GIT_AVAILABLE = False  # disable retries this pod-lifetime
        return ""


def _all_commits() -> List[Dict[str, Any]]:
    """Return every commit sha + iso ts + subject + body."""
    raw = _git("log", "--all", "--pretty=format:%H||%aI||%s||%b||END_COMMIT")
    if not raw:
        return []
    out: List[Dict[str, Any]] = []
    for block in raw.split("END_COMMIT\n"):
        parts = block.strip().split("||")
        if len(parts) < 4 or not parts[0]:
            continue
        sha, ts, subject, body = parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""
        out.append({"sha": sha.strip(), "ts": ts.strip(), "subject": subject.strip(), "body": body.strip()})
    return out


def _commit_stats(sha: str) -> Dict[str, Any]:
    """numstat → additions, deletions, files_changed, file list."""
    raw = _git("show", "--numstat", "--pretty=format:", sha)
    files: List[str] = []
    additions = 0
    deletions = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            add  = int(parts[0]) if parts[0].isdigit() else 0
            dele = int(parts[1]) if parts[1].isdigit() else 0
            additions += add
            deletions += dele
            files.append(parts[2])
        except Exception:
            continue
    return {
        "files_changed": len(files),
        "additions": additions,
        "deletions": deletions,
        "files": files[:30],   # cap to keep doc small
    }


# ────────────────────────────────────────────────────────────────────
# Categorisation + extraction
# ────────────────────────────────────────────────────────────────────
def _categorise(subject: str, files: List[str]) -> str:
    s = subject.lower()
    if any(k in s for k in ("fix", "bugfix", "patch", "hotfix")):
        return "fix"
    if any(k in s for k in ("refactor", "rename", "cleanup", "purge")):
        return "refactor"
    if any(k in s for k in ("docs", "readme", "prd")):
        return "docs"
    if any(k in s for k in ("test", "iteration_")):
        return "test"
    if any(k in s for k in ("infra", "supervisor", "docker", "deploy", "atlas", "k8s")):
        return "infra"
    if any(k in s for k in ("chore", "bump", "version")):
        return "chore"
    if any(k in s for k in ("feat", "add", "ship", "build", "launch", "wire")):
        return "feat"
    # File-based heuristic — many docs/test paths → respective category
    if files and all(f.startswith(("docs/", "memory/", "*.md")) for f in files[:3]):
        return "docs"
    if files and all("/tests/" in f or f.endswith("_test.py") or f.startswith("test_") for f in files[:3]):
        return "test"
    return "feat"  # default


def _extract_iter(subject: str, body: str) -> Optional[str]:
    for src in (subject, body):
        m = ITER_RE.search(src or "")
        if m:
            return m.group(1).lower()
    return None


def _extract_iter_from_files(files: List[str]) -> Optional[str]:
    """Fallback: look for `iteration_XXX` or `iter_XXX` in any changed file path.
    Catches backend/tests/test_iteration_322_xyz.py and similar."""
    pat = re.compile(r"iter(?:ation)?[_\-]?(\d{2,4}[a-z]{0,2})(?:[_\-\.]|$)", re.IGNORECASE)
    for f in files or []:
        m = pat.search(f)
        if m:
            return m.group(1).lower()
    return None


def _extract_shipped(subject: str, body: str) -> List[str]:
    """Pull human-readable shipped items from commit message."""
    text = f"{subject}\n{body}"
    items: List[str] = []
    for m in SHIPPED_RE.finditer(text):
        chunk = m.group(1).strip().rstrip(",")
        if chunk and len(chunk) < 120:
            items.append(chunk)
    return list(dict.fromkeys(items))[:5]   # de-dup, cap 5


# ────────────────────────────────────────────────────────────────────
# Test status cross-ref
# ────────────────────────────────────────────────────────────────────
def _test_status_for_iter(iter_tag: Optional[str]) -> str:
    if not iter_tag:
        return "unknown"
    candidate = os.path.join(REPO_ROOT, "test_reports", f"iteration_{iter_tag}.json")
    if not os.path.exists(candidate):
        return "unknown"
    try:
        import json
        with open(candidate) as f:
            d = json.load(f)
        bi = d.get("backend_issues") or {}
        fi = d.get("frontend_issues") or {}
        crit = (bi.get("critical") if isinstance(bi, dict) else []) or []
        crit_f = (fi.get("critical") if isinstance(fi, dict) else []) or []
        if crit or crit_f:
            return "fail"
        return "pass"
    except Exception:
        return "unknown"


# ────────────────────────────────────────────────────────────────────
# Core ingest
# ────────────────────────────────────────────────────────────────────
async def _build_row(commit: Dict[str, Any], phase: int) -> Dict[str, Any]:
    sha = commit["sha"]
    stats = _commit_stats(sha)
    iter_tag = _extract_iter(commit["subject"], commit["body"]) or _extract_iter_from_files(stats["files"])
    shipped = _extract_shipped(commit["subject"], commit["body"])
    return {
        "_id": sha,
        "sha": sha,
        "short": sha[:7],
        "ts": commit["ts"],
        "iter": iter_tag,
        "message": commit["subject"],
        "body": (commit["body"] or "")[:400],
        "files_changed": stats["files_changed"],
        "additions": stats["additions"],
        "deletions": stats["deletions"],
        "files": stats["files"],
        "category": _categorise(commit["subject"], stats["files"]),
        "shipped": shipped,
        "test_status": _test_status_for_iter(iter_tag),
        "phase": phase,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "ora_learned": False,
    }


async def _fire_ora_learn(db, row: Dict[str, Any]) -> None:
    """Feed the commit into the ORA Universal Learner organically."""
    try:
        from services import ora_universal_learner as _oul
        summary = row["message"]
        if row.get("iter"):
            summary = f"iter {row['iter']} — {summary}"
        await _oul.ora_learn({
            "source": "build_journal",
            "event": "BUILD_COMMIT",
            "category": row["category"],
            "summary": summary,
            "outcome": row.get("test_status", "unknown"),
            "files_changed": row.get("files_changed", 0),
            "additions": row.get("additions", 0),
            "shipped": row.get("shipped", []),
            "iter": row.get("iter"),
            "sha": row["sha"],
        })
        try:
            await db.build_journal.update_one(
                {"_id": row["sha"]}, {"$set": {"ora_learned": True}}
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[build-journal] ora_learn failed for {row['sha'][:7]}: {e}")


# ────────────────────────────────────────────────────────────────────
# Phase 1 — Backfill (one-shot, idempotent)
# ────────────────────────────────────────────────────────────────────
async def backfill(db, limit: int = 5000) -> Dict[str, Any]:
    """Read full git history, write any unseen commits to db.build_journal."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    commits = _all_commits()
    if not commits:
        return {"ok": False, "error": "git log empty"}

    commits = commits[:limit]
    # Existing shas — skip
    try:
        existing = set()
        async for r in db.build_journal.find({}, {"_id": 1}):
            existing.add(r["_id"])
    except Exception:
        existing = set()

    new_rows = [c for c in commits if c["sha"] not in existing]
    inserted = 0
    learned = 0
    for c in new_rows:
        row = await _build_row(c, phase=1)
        try:
            await db.build_journal.update_one(
                {"_id": row["_id"]}, {"$setOnInsert": row}, upsert=True,
            )
            inserted += 1
            # Only fire ORA learn on real iter-tagged commits to keep brain signal-rich
            if row.get("iter"):
                await _fire_ora_learn(db, row)
                learned += 1
        except Exception as e:
            logger.warning(f"[build-journal] backfill insert {row['sha'][:7]}: {e}")

    return {
        "ok": True,
        "total_commits": len(commits),
        "already_indexed": len(existing),
        "new_inserted": inserted,
        "ora_learned": learned,
    }


# ────────────────────────────────────────────────────────────────────
# Phase 2 — Live sync (every 10 min cron)
# ────────────────────────────────────────────────────────────────────
async def live_sync(db) -> Dict[str, Any]:
    """
    Incremental sync — read latest 50 commits, ingest unseen. Designed to be
    cheap (skips db work for already-known shas). Wired in registry.py as a
    10-minute APScheduler job.
    """
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    raw = _git("log", "--all", "-50", "--pretty=format:%H||%aI||%s||%b||END_COMMIT")
    if not raw:
        return {"ok": True, "new": 0, "note": "no git history"}

    commits: List[Dict[str, Any]] = []
    for block in raw.split("END_COMMIT\n"):
        parts = block.strip().split("||")
        if len(parts) >= 3 and parts[0]:
            commits.append({
                "sha": parts[0], "ts": parts[1],
                "subject": parts[2], "body": parts[3] if len(parts) > 3 else "",
            })

    shas = [c["sha"] for c in commits]
    existing = set()
    try:
        async for r in db.build_journal.find({"_id": {"$in": shas}}, {"_id": 1}):
            existing.add(r["_id"])
    except Exception:
        pass

    new = 0
    for c in commits:
        if c["sha"] in existing:
            continue
        row = await _build_row(c, phase=2)
        try:
            await db.build_journal.update_one(
                {"_id": row["_id"]}, {"$setOnInsert": row}, upsert=True,
            )
            new += 1
            if row.get("iter"):
                await _fire_ora_learn(db, row)
        except Exception as e:
            logger.warning(f"[build-journal] live-sync insert: {e}")

    if new:
        logger.info(f"[build-journal] live sync — {new} new commits ingested")
    return {"ok": True, "new": new}


# ────────────────────────────────────────────────────────────────────
# Phase 3 — Public feed (paginated, lean)
# ────────────────────────────────────────────────────────────────────
async def public_feed(db, page: int = 1, page_size: int = 25, category: Optional[str] = None) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "error": "db unavailable", "items": [], "total": 0}
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    q: Dict[str, Any] = {}
    if category:
        q["category"] = category
    try:
        total = await db.build_journal.count_documents(q)
        cur = (db.build_journal
               .find(q, {"_id": 0, "body": 0, "files": 0})
               .sort("ts", -1)
               .skip((page - 1) * page_size)
               .limit(page_size))
        items = await cur.to_list(length=page_size)
        return {
            "ok": True,
            "page": page, "page_size": page_size, "total": total,
            "items": items,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "items": [], "total": 0}


async def stats(db) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    try:
        total = await db.build_journal.count_documents({})
        by_cat: Dict[str, int] = {}
        async for r in db.build_journal.find({}, {"_id": 0, "category": 1}):
            c = r.get("category", "unknown")
            by_cat[c] = by_cat.get(c, 0) + 1
        # Distinct iters
        iters = await db.build_journal.distinct("iter")
        iters = [i for i in iters if i]
        # Sum of additions / deletions
        pipeline = [{"$group": {"_id": None, "add": {"$sum": "$additions"}, "del": {"$sum": "$deletions"}}}]
        sums = await db.build_journal.aggregate(pipeline).to_list(length=1)
        total_add = sums[0]["add"] if sums else 0
        total_del = sums[0]["del"] if sums else 0
        return {
            "ok": True,
            "total_commits": total,
            "by_category": by_cat,
            "distinct_iters": len(iters),
            "iters_list": sorted(iters)[-30:],
            "total_additions": total_add,
            "total_deletions": total_del,
            "since": "Day 1",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ────────────────────────────────────────────────────────────────────
# Phase 4 — Daily Founder Digest (23:00 Toronto = 04:00 UTC next day)
# ────────────────────────────────────────────────────────────────────
async def send_daily_digest(db) -> Dict[str, Any]:
    """Aggregate today's journal rows → Resend email to founder."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    # "today" = last 24h to keep things simple across TZ
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        cur = db.build_journal.find({"ts": {"$gte": cutoff}}, {"_id": 0}).sort("ts", -1)
        items = await cur.to_list(length=200)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not items:
        return {"ok": True, "note": "no commits in last 24h, digest skipped"}

    by_iter: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        key = it.get("iter") or "untagged"
        by_iter.setdefault(key, []).append(it)

    total_add = sum(it.get("additions", 0) for it in items)
    total_del = sum(it.get("deletions", 0) for it in items)

    # Build HTML
    rows_html = []
    for iter_tag, group in by_iter.items():
        msgs = "<br/>".join(f"• {x['message'][:140]}" for x in group[:6])
        rows_html.append(
            f"<tr><td style='padding:8px;border-bottom:1px solid #333;font-family:monospace;color:#D4AF37'>{iter_tag}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #333;color:#E8E0D0'>{len(group)} commits"
            f"<br/><span style='color:#8A8070;font-size:12px'>{msgs}</span></td></tr>"
        )
    table = "<table style='width:100%;border-collapse:collapse;background:#0E0E0F;color:#E8E0D0'>" \
            + "".join(rows_html) + "</table>"

    html = f"""
<div style='background:#0E0E0F;color:#E8E0D0;font-family:-apple-system,sans-serif;padding:24px;max-width:680px;margin:0 auto'>
  <h1 style='color:#D4AF37;font-family:Cinzel,serif'>🛠 AUREM Build Journal — Daily Digest</h1>
  <p style='color:#8A8070'>{datetime.now(timezone.utc).strftime('%A, %B %d, %Y')} · Last 24 hours</p>
  <div style='padding:16px;background:rgba(212,175,55,0.05);border:1px solid rgba(212,175,55,0.15);border-radius:10px;margin:16px 0'>
    <strong style='color:#D4AF37'>{len(items)} commits</strong> ·
    <span style='color:#4ADE80'>+{total_add}</span> additions ·
    <span style='color:#EF4444'>-{total_del}</span> deletions ·
    <strong>{len(by_iter)}</strong> distinct iters
  </div>
  {table}
  <p style='color:#8A8070;font-size:12px;margin-top:20px'>
    Every build is auto-fed into ORA Learning Stack. View full log at
    <a href='https://aurem.live/build-log' style='color:#D4AF37'>aurem.live/build-log</a>
  </p>
</div>
"""

    # Resend send (best-effort)
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {"ok": True, "note": "RESEND_API_KEY not set — digest built but not sent", "commits": len(items)}
    try:
        import resend
        resend.api_key = api_key
        founder = os.environ.get("FOUNDER_ALERT_EMAIL", "teji.ss1986@gmail.com")
        resend.Emails.send({
            "from": "AUREM Build <build@aurem.live>",
            "to": [founder],
            "subject": f"🛠 AUREM Build — {len(items)} commits, {len(by_iter)} iters today",
            "html": html,
        })
        # Mark a digest row so we can audit
        await db.build_journal_digests.insert_one({
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "commits": len(items),
            "iters": list(by_iter.keys()),
            "total_additions": total_add,
            "total_deletions": total_del,
        })
        return {"ok": True, "sent": True, "commits": len(items)}
    except Exception as e:
        logger.warning(f"[build-journal] digest send failed: {e}")
        return {"ok": False, "error": str(e)}


# ────────────────────────────────────────────────────────────────────
# Phase 5 — ORA Pattern Miner (nightly 03:30 UTC)
# ────────────────────────────────────────────────────────────────────
async def mine_patterns(db) -> Dict[str, Any]:
    """
    Look at last 200 commits, derive macro-patterns and write to
    db.fix_patterns + db.ora_brain_thoughts so the autonomous fixer
    can leverage build-time learnings.
    """
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    cur = db.build_journal.find({}, {"_id": 0}).sort("ts", -1).limit(200)
    rows = await cur.to_list(length=200)
    if not rows:
        return {"ok": True, "patterns": 0}

    # Pattern: which file paths consistently appear together in fix commits → coupling
    fix_rows = [r for r in rows if r.get("category") == "fix"]
    coupling: Dict[str, Dict[str, int]] = {}
    for r in fix_rows:
        files = (r.get("files") or [])[:6]
        for i, f1 in enumerate(files):
            for f2 in files[i + 1:]:
                key = f1 if f1 < f2 else f2
                other = f2 if f1 < f2 else f1
                coupling.setdefault(key, {})
                coupling[key][other] = coupling[key].get(other, 0) + 1

    # Pick top 20 couplings (count >= 2)
    top = []
    for a, others in coupling.items():
        for b, cnt in others.items():
            if cnt >= 2:
                top.append((cnt, a, b))
    top.sort(reverse=True)
    top = top[:20]

    written = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for cnt, a, b in top:
        pattern = {
            "pattern_id": f"coupling::{a}::{b}",
            "type": "file_coupling",
            "files": [a, b],
            "co_fix_count": cnt,
            "source": "build_journal_miner",
            "last_seen": now_iso,
        }
        try:
            await db.fix_patterns.update_one(
                {"pattern_id": pattern["pattern_id"]},
                {"$set": pattern}, upsert=True,
            )
            written += 1
        except Exception as e:
            logger.warning(f"[build-journal] miner write: {e}")

    # Single roll-up brain thought (very high signal)
    try:
        from services import ora_universal_learner as _oul
        await _oul.ora_learn({
            "source": "build_journal_miner",
            "event": "BUILD_PATTERN_MINED",
            "category": "self_learning",
            "summary": f"Mined {written} file-coupling patterns from {len(rows)} recent commits",
            "outcome": "ok",
            "patterns_mined": written,
            "commits_scanned": len(rows),
        })
    except Exception:
        pass

    return {"ok": True, "patterns": written, "scanned": len(rows)}
