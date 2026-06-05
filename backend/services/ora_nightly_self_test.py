"""
services/ora_nightly_self_test.py — iter 327q (FIX 2)

Runs 5 standard checks at 02:00 UTC every night. Any failure fires a
Telegram alert BEFORE the morning brief so the founder wakes up to a
single-line "X / 5 checks passed" report.

The 5 checks (kept deliberately cheap so the whole run finishes in <10 s):

  1. ora_agent.SYSTEM_PROMPT length > 8 KB
     → confirms the tiered memory injection (iter 327n) is still wired.

  2. ora_agent.TOOL_REGISTRY tier reconciliation returns no orphans
     → confirms no tier-set drift introduced by a code change.

  3. health endpoint (HTTP 200)
     → confirms the backend itself is reachable from inside the pod.

  4. Mongo write+read round-trip
     → confirms the primary DB is still accepting writes.

  5. ora_learning_journal collection is reachable (count_documents)
     → confirms the Tier-1 memory journal cron is still functional.

Every run writes a row to `ora_nightly_self_tests`. On any failure we
emit a Telegram alert with a per-day fingerprint so re-runs don't
double-ping.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_nightly_self_test(db) -> dict:
    """Best-effort self-test. Returns a structured result dict.

    Never raises — failures are captured and surfaced via Telegram.
    """
    if db is None:
        return {"ok": False, "error": "db not ready"}

    ts = datetime.now(timezone.utc)
    checks: list[dict] = []

    # ── 1. SYSTEM_PROMPT length ──────────────────────────────────────
    try:
        from services.ora_agent import SYSTEM_PROMPT
        ok = len(SYSTEM_PROMPT) > 8_000
        checks.append({
            "name":   "system_prompt_size",
            "ok":     ok,
            "detail": f"{len(SYSTEM_PROMPT)} chars",
        })
    except Exception as e:
        checks.append({"name": "system_prompt_size", "ok": False, "detail": str(e)[:200]})

    # ── 2. tool registry reconciliation ─────────────────────────────
    try:
        from services.ora_tools import reconcile_tool_registry
        rec = reconcile_tool_registry()
        ok = not rec.get("orphans")
        checks.append({
            "name":   "tool_registry_reconcile",
            "ok":     ok,
            "detail": f"orphans={len(rec.get('orphans') or [])} hidden={len(rec.get('hidden') or [])}",
        })
    except Exception as e:
        checks.append({"name": "tool_registry_reconcile", "ok": False, "detail": str(e)[:200]})

    # ── 3. health endpoint round-trip ────────────────────────────────
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get("http://localhost:8001/api/health")
            ok = r.status_code == 200
            checks.append({
                "name":   "backend_health",
                "ok":     ok,
                "detail": f"HTTP {r.status_code}",
            })
    except Exception as e:
        checks.append({"name": "backend_health", "ok": False, "detail": str(e)[:200]})

    # ── 4. Mongo write+read round-trip ───────────────────────────────
    try:
        token = f"selftest_{ts.isoformat()}"
        await db.ora_nightly_self_tests_probe.update_one(
            {"_id": "probe"},
            {"$set": {"token": token, "ts": ts}},
            upsert=True,
        )
        doc = await db.ora_nightly_self_tests_probe.find_one({"_id": "probe"})
        ok = bool(doc and doc.get("token") == token)
        checks.append({
            "name":   "mongo_roundtrip",
            "ok":     ok,
            "detail": "write+read confirmed" if ok else "mismatch",
        })
    except Exception as e:
        checks.append({"name": "mongo_roundtrip", "ok": False, "detail": str(e)[:200]})

    # ── 5. learning journal reachable ────────────────────────────────
    try:
        n = await db.ora_learning_journal.count_documents({})
        checks.append({
            "name":   "lesson_journal_reachable",
            "ok":     True,
            "detail": f"{n} entries",
        })
    except Exception as e:
        checks.append({"name": "lesson_journal_reachable", "ok": False, "detail": str(e)[:200]})

    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks)
    summary = f"{passed}/{total} checks passed"

    # Persist a row so we have history.
    try:
        await db.ora_nightly_self_tests.insert_one({
            "ts":      ts.isoformat(),
            "passed":  passed,
            "total":   total,
            "checks":  checks,
        })
    except Exception as e:
        logger.warning(f"[ora-nightly] persist failed: {e}")

    # Telegram alert on any failure — same day fingerprint so re-runs
    # do not double-ping the founder.
    if passed < total:
        try:
            from services.silent_failure_alerts import _send as _tg_send
            failed_names = [c["name"] for c in checks if not c.get("ok")]
            day = ts.strftime("%Y-%m-%d")
            # iter D-65 — _send signature is (message, alert_type, fingerprint).
            # The previous call dropped `alert_type` → TypeError every night.
            await _tg_send(
                f"🌙 ORA Nightly Self-Test FAILED ({summary}) "
                f"— failed: {', '.join(failed_names)} — see "
                f"ora_nightly_self_tests collection for detail.",
                alert_type="ora_nightly_self_test",
                fingerprint=f"ora_nightly_self_test_fail_{day}",
            )
        except Exception as e:
            logger.warning(f"[ora-nightly] telegram alert failed: {e}")

    return {
        "ok":      passed == total,
        "passed":  passed,
        "total":   total,
        "summary": summary,
        "checks":  checks,
    }
