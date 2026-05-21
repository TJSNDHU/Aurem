"""
services/self_audit_scheduler.py — auto-trigger for self-audit (iter
325f Phase 3a).

Previously the self-audit endpoint was manual-only ("admin clicks
button"). This scheduler runs it every 6 hours and pipes findings
with severity HIGH (overall_score below SELF_AUDIT_ALERT_THRESHOLD)
into incident_bus so the rest of the autonomous repair stack reacts.

Collections touched:
  - db.self_audit_log  (written by services.self_audit.run_self_audit)
  - db.incident_ledger (written via incident_bus.report)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def run_self_audit_tick(db=None) -> Dict[str, Any]:
    """Run one self-audit pass and emit incident_bus on HIGH severity."""
    db = db or _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    try:
        from services.self_audit import run_self_audit
        row = await run_self_audit(db)
    except Exception as e:
        logger.error(f"[self_audit_scheduler] run failed: {e}")
        return {"ok": False, "error": str(e)[:200]}

    threshold = int(os.environ.get("SELF_AUDIT_ALERT_THRESHOLD") or 70)
    score = int(row.get("overall_score") or 0)
    emitted = False
    if score < threshold:
        try:
            from services import incident_bus
            await incident_bus.report(
                category="self_audit_low_score",
                signature=f"self_audit:{row.get('target')}:score_below_{threshold}",
                severity="high" if score < (threshold - 20) else "medium",
                source="self_audit",
                title=f"Self-audit score {score}/100 (threshold {threshold})",
                detail=str(row.get("findings") or row.get("summary") or "")[:1500],
                metadata={"score": score, "target": row.get("target"),
                          "threshold": threshold},
                actor="self_audit_scheduler",
            )
            emitted = True
        except Exception as e:
            logger.warning(f"[self_audit_scheduler] incident emit failed: {e}")

    return {"ok": True, "score": score, "threshold": threshold,
            "emitted": emitted, "target": row.get("target")}
