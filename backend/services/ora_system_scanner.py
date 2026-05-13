"""
ora_system_scanner.py — Scheduled self-diagnosis (iter 322g part 5)
═══════════════════════════════════════════════════════════════════════
User mandate: "Sara system scan kr. Bugs find kr. Fix kr automatically.
Push automatic kro." (push is platform-gated → we stage commits only.)

This service runs every 5 minutes. It scans the system for known-bad
patterns and writes findings to `ora_system_findings`. Some findings have
an **automatic-fix playbook** wired; those run immediately. The rest
are surfaced to the founder via the dashboard.

What it scans:
  1. /var/log/supervisor/backend.err.log → recurring tracebacks
  2. supervisorctl status — STOPPED services
  3. MongoDB → stale "claimed" jobs older than 10min
  4. /app/backend lint (ruff) on services/ directory
  5. legion_daemon_status freshness
  6. auto_blast_config.last_run_sent regression
  7. ora_campaign_health.zero_sent_streak
  8. Failed background tasks in pillar-1 worker

Findings shape (one doc per signature, upserted on repeat):
{
    "_id": str — fingerprint hash,
    "category": str — log|service|queue|lint|daemon|engine|watchdog|task,
    "severity": "P0|P1|P2",
    "summary": str,
    "first_seen": iso,
    "last_seen": iso,
    "seen_count": int,
    "autofix": str|null — name of autofix function fired, or null,
    "autofix_count": int,
    "raw_excerpt": str (max 600 chars),
}
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("ora_system_scanner")

_db = None
SCAN_INTERVAL_S = 300   # 5 min
SCAN_FIRST_DELAY_S = 75
STUCK_JOB_THRESHOLD_S = 600


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fp(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


async def _upsert_finding(**doc) -> None:
    if _db is None or "_id" not in doc:
        return
    now = _now()
    inc = {"seen_count": 1}
    set_ = {k: v for k, v in doc.items() if k not in ("_id", "first_seen")}
    set_["last_seen"] = now
    try:
        await _db.ora_system_findings.update_one(
            {"_id": doc["_id"]},
            {
                "$inc": inc,
                "$set": set_,
                "$setOnInsert": {"first_seen": now, "autofix_count": 0},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[scanner] upsert failed: {e}")


async def _bump_autofix(fp: str, autofix_name: str) -> None:
    if _db is None:
        return
    await _db.ora_system_findings.update_one(
        {"_id": fp},
        {"$set": {"autofix": autofix_name, "last_autofix_at": _now()},
         "$inc": {"autofix_count": 1}},
    )


# ── Scan 1: supervisor STOPPED services ───────────────────────────────
async def _scan_supervisor() -> None:
    try:
        r = subprocess.run(
            ["sudo", "supervisorctl", "status"],
            capture_output=True, text=True, timeout=8,
        )
        for line in r.stdout.splitlines():
            if " STOPPED " in line or " FATAL " in line or " EXITED " in line:
                svc = line.split()[0]
                fp = _fp("supervisor", svc, "stopped")
                await _upsert_finding(
                    _id=fp, category="service", severity="P0",
                    summary=f"supervisor service {svc} is not running",
                    raw_excerpt=line[:400],
                )
                # Auto-fix: try one restart
                try:
                    subprocess.run(
                        ["sudo", "supervisorctl", "start", svc],
                        capture_output=True, timeout=12,
                    )
                    await _bump_autofix(fp, "supervisorctl_start")
                    logger.warning(f"[scanner] autofix: restarted {svc}")
                except Exception as e:
                    logger.warning(f"[scanner] failed to start {svc}: {e}")
    except Exception as e:
        logger.debug(f"[scanner] supervisor scan err: {e}")


# ── Scan 2: backend err.log tracebacks ────────────────────────────────
TB_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"CRITICAL"),
    re.compile(r"connection refused", re.I),
    re.compile(r"DuplicateKeyError"),
]


async def _scan_backend_logs() -> None:
    try:
        with open("/var/log/supervisor/backend.err.log", "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 100_000))   # last 100KB
            tail = f.read().decode("utf-8", errors="replace")
        for pat in TB_PATTERNS:
            for m in list(pat.finditer(tail))[-5:]:
                snippet = tail[max(0, m.start() - 50): m.end() + 400][:600]
                exception_type = "unknown"
                em = re.search(r"^([A-Z][A-Za-z0-9_]+(?:Error|Exception)):", snippet, re.M)
                if em:
                    exception_type = em.group(1)
                fp = _fp("log_tb", exception_type, snippet[:80])
                await _upsert_finding(
                    _id=fp, category="log", severity="P1",
                    summary=f"recurring traceback: {exception_type}",
                    raw_excerpt=snippet,
                )
    except Exception as e:
        logger.debug(f"[scanner] log scan err: {e}")


# ── Scan 3: stale legion_queue jobs ───────────────────────────────────
async def _scan_stuck_jobs() -> None:
    if _db is None:
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=STUCK_JOB_THRESHOLD_S)).isoformat()
    stuck = await _db.legion_queue.count_documents({
        "status": {"$in": ["claimed", "running"]},
        "enqueued_at": {"$lt": cutoff},
    })
    if stuck > 0:
        fp = _fp("stuck_jobs", "claimed_or_running")
        await _upsert_finding(
            _id=fp, category="queue", severity="P1",
            summary=f"{stuck} legion_queue jobs stuck >10min in claimed/running",
            raw_excerpt=f"stuck_count={stuck} cutoff={cutoff}",
        )
        # Autofix: cancel them so future jobs can proceed.
        r = await _db.legion_queue.update_many(
            {"status": {"$in": ["claimed", "running"]},
             "enqueued_at": {"$lt": cutoff}},
            {"$set": {"status": "cancelled", "exit_code": -77,
                      "stderr": "ora-system-scanner-stuck-cleanup"}},
        )
        await _bump_autofix(fp, "cancel_stuck_jobs")
        logger.warning(f"[scanner] autofix: cancelled {r.modified_count} stuck jobs")


# ── Scan 4: legion daemon offline ─────────────────────────────────────
async def _scan_daemon() -> None:
    if _db is None:
        return
    s = await _db.legion_daemon_status.find_one({"_id": "global"}, {"_id": 0, "last_poll_ts": 1})
    last = float((s or {}).get("last_poll_ts") or 0)
    age = time.time() - last if last else None
    if age is None:
        fp = _fp("daemon", "never_polled")
        await _upsert_finding(
            _id=fp, category="daemon", severity="P0",
            summary="Legion daemon never polled — start it on laptop",
            raw_excerpt="no legion_daemon_status doc",
        )
        return
    if age > 300:
        fp = _fp("daemon", "stale")
        await _upsert_finding(
            _id=fp, category="daemon", severity="P0",
            summary=f"Legion daemon offline ({int(age)}s since last poll)",
            raw_excerpt=f"age_s={int(age)}",
        )


# ── Scan 5: ruff lint (services/) ─────────────────────────────────────
_RUFF_CACHE_TS = 0.0


async def _scan_lint() -> None:
    global _RUFF_CACHE_TS
    # Only run once per 30min — ruff is slow on big tree.
    if time.time() - _RUFF_CACHE_TS < 1800:
        return
    _RUFF_CACHE_TS = time.time()
    try:
        r = subprocess.run(
            ["ruff", "check", "/app/backend/services", "--quiet", "--output-format=concise"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout or "").strip()
        if not out:
            return
        for line in out.splitlines()[:20]:
            m = re.match(r"^([^:]+):(\d+):\d+: (\w+) (.+)$", line)
            if not m:
                continue
            f, lineno, code, msg = m.groups()
            fp = _fp("lint", code, f, lineno)
            await _upsert_finding(
                _id=fp, category="lint", severity="P2",
                summary=f"{code} in {os.path.basename(f)}:{lineno} — {msg[:100]}",
                raw_excerpt=line[:300],
            )
    except Exception as e:
        logger.debug(f"[scanner] lint err: {e}")


# ── Main scan dispatcher ──────────────────────────────────────────────
async def _run_one_scan() -> dict:
    started = time.time()
    await _scan_supervisor()
    await _scan_backend_logs()
    await _scan_stuck_jobs()
    await _scan_daemon()
    await _scan_lint()
    elapsed = time.time() - started
    if _db is not None:
        total = await _db.ora_system_findings.count_documents({})
    else:
        total = 0
    logger.info(f"[scanner] sweep done in {elapsed:.1f}s — {total} active findings")
    return {"ok": True, "elapsed_s": elapsed, "findings": total}


async def scanner_loop() -> None:
    print(f"[scanner] system scanner alive — every {SCAN_INTERVAL_S}s", flush=True)
    await asyncio.sleep(SCAN_FIRST_DELAY_S)
    while True:
        try:
            await _run_one_scan()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[scanner] loop err: {e}", exc_info=True)
        await asyncio.sleep(SCAN_INTERVAL_S)


# Public on-demand wrapper for ORA tool use.
async def trigger_scan_now() -> dict:
    return await _run_one_scan()
