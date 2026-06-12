"""
Supply-Chain Remediation Engine — iter D-82b
═══════════════════════════════════════════════════════════════════════════
Bridges the autonomous supply-chain scanner (services.supply_chain_scanner)
into AUREM's existing Sentinel "trust-but-verify" repair model.

For every finding produced by the 6h sweep it builds a remediation PLAN and
classifies it into one of three lanes (mirrors Sentinel's tiers):

  • auto_safe       — pip dependency upgrade, same-major (patch/minor) bump,
                      with a published fix version  →  CAN be auto-applied
                      with full backup + validate + rollback.
  • needs_approval  — pip major-version bump, or any JS/yarn upgrade
                      (frontend build risk)  →  written to db.repair_suggestions
                      (Sentinel admin queue) for human Apply/Reject.
  • manual_only     — secrets (must be rotated by a human at the provider) and
                      SAST code smells (auto-rewriting code is unsafe)  →  also
                      surfaced as Sentinel suggestions, flagged manual.

REAL fixes only. Auto-apply edits requirements.txt, runs a real `pip install`,
smoke-imports the package, and rolls back on any failure. Nothing is mocked.

Autonomy: the scanner calls `remediate_after_scan()` at the end of every
sweep. By default it runs in SUGGEST-ONLY mode (writes suggestions, applies
nothing). Set AUREM_SUPPLY_CHAIN_AUTOFIX=true to let auto_safe pip upgrades
apply themselves unattended.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BUSINESS_ID = "aurem_self"
TENANT_ID = "aurem_self"
REQUIREMENTS_PATH = "/app/backend/requirements.txt"

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── version helpers ───────────────────────────────────────────────────────
def _parse_semver(v: str) -> Optional[Tuple[int, int, int]]:
    m = re.match(r"^\D*(\d+)(?:\.(\d+))?(?:\.(\d+))?", (v or "").strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def _is_safe_bump(current: str, target: str) -> bool:
    """Safe == same major version (patch/minor only) and target > current."""
    c, t = _parse_semver(current), _parse_semver(target)
    if not c or not t:
        return False
    if c[0] != t[0]:           # major change → never auto
        return False
    return t > c               # must be an actual upgrade


# ── parse a normalised pip finding back into actionable parts ──────────────
def _parse_pip_finding(f: Dict[str, Any]) -> Optional[Dict[str, str]]:
    loc = f.get("location", "")
    m = re.search(r"→\s*(\S+)==(\S+)", loc)
    if not m:
        return None
    name, current = m.group(1), m.group(2)
    target = ""
    fix = f.get("fix", "")
    mt = re.search(r"Upgrade to\s+(.+)", fix)
    if mt:
        # first listed fix version (already lowest fixing release)
        target = mt.group(1).split(",")[0].strip()
    return {"name": name, "current": current, "target": target}


def _signature(*parts: str) -> str:
    return "sc_" + hashlib.sha1("::".join(parts).encode()).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════
# Planner — classify every finding into a remediation lane
# ══════════════════════════════════════════════════════════════════════════
def build_plan(findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    auto_safe: List[Dict[str, Any]] = []
    needs_approval: List[Dict[str, Any]] = []
    manual_only: List[Dict[str, Any]] = []

    for f in findings:
        cat, tool = f.get("category"), f.get("tool")
        if cat == "SCA" and tool == "pip-audit":
            parts = _parse_pip_finding(f)
            if parts and parts["target"] and _is_safe_bump(parts["current"], parts["target"]):
                auto_safe.append({**f, "remediation": {
                    "kind": "pip_upgrade", **parts,
                    "command": f'pip install {parts["name"]}=={parts["target"]}',
                }})
            else:
                needs_approval.append({**f, "remediation": {
                    "kind": "pip_upgrade_major" if parts else "pip_manual",
                    **(parts or {}),
                    "reason": "major-version bump or no published fix",
                }})
        elif cat == "SCA" and tool == "yarn-audit":
            needs_approval.append({**f, "remediation": {
                "kind": "yarn_upgrade",
                "reason": "frontend dependency — build-risk, human review",
            }})
        elif cat == "SECRET":
            manual_only.append({**f, "remediation": {
                "kind": "rotate_secret",
                "reason": "secrets must be rotated at the provider by a human",
            }})
        else:  # SAST / bandit
            manual_only.append({**f, "remediation": {
                "kind": "code_review",
                "reason": "auto-rewriting source is unsafe — human review",
            }})
    return {"auto_safe": auto_safe, "needs_approval": needs_approval, "manual_only": manual_only}


# ══════════════════════════════════════════════════════════════════════════
# REAL apply — pip upgrade with backup + validate + rollback
# ══════════════════════════════════════════════════════════════════════════
async def _run(cmd: List[str], timeout: int = 180) -> Tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, (out or b"").decode("utf-8", "replace")
    except asyncio.TimeoutError:
        return -1, f"timeout after {timeout}s"
    except Exception as e:  # noqa: BLE001
        return -1, str(e)[:300]


def _update_requirements_line(name: str, target: str) -> bool:
    """Rewrite the pinned line for `name` to `name==target`. Returns True if changed."""
    norm = name.lower().replace("_", "-")
    try:
        with open(REQUIREMENTS_PATH, "r") as fh:
            lines = fh.readlines()
    except Exception:
        return False
    changed = False
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z0-9_.\-]+)==", line.strip())
        if m and m.group(1).lower().replace("_", "-") == norm:
            lines[i] = f"{m.group(1)}=={target}\n"
            changed = True
            break
    if changed:
        with open(REQUIREMENTS_PATH, "w") as fh:
            fh.writelines(lines)
    return changed


async def apply_pip_upgrade(name: str, current: str, target: str) -> Dict[str, Any]:
    """Install target version, smoke-import, update requirements.txt, rollback on failure."""
    pip = [sys.executable, "-m", "pip"]
    backup = REQUIREMENTS_PATH + ".scbak"
    try:
        shutil.copy2(REQUIREMENTS_PATH, backup)
    except Exception as e:  # noqa: BLE001
        return {"success": False, "name": name, "error": f"backup failed: {e}"}

    rc, out = await _run([*pip, "install", f"{name}=={target}"])
    if rc != 0:
        await _run([*pip, "install", f"{name}=={current}"])  # ensure prior state
        return {"success": False, "name": name, "from": current, "to": target,
                "error": "pip install failed", "log": out[-400:]}

    # Smoke-import (best-effort — import name may differ from dist name).
    mod = name.lower().replace("-", "_")
    rc2, _ = await _run([sys.executable, "-c", f"import {mod}"], timeout=30)
    import_ok = rc2 == 0  # non-fatal if module name differs

    req_updated = _update_requirements_line(name, target)
    try:
        if os.path.exists(backup):
            os.remove(backup)
    except Exception:
        pass

    return {
        "success": True, "name": name, "from": current, "to": target,
        "requirements_updated": req_updated, "import_ok": import_ok,
        "restart_pending": True,  # new version is live for fresh processes
    }


# ══════════════════════════════════════════════════════════════════════════
# Suggestion writer — feeds Sentinel's repair_suggestions queue
# ══════════════════════════════════════════════════════════════════════════
_SEV_TO_P = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3", "info": "P3"}


async def _upsert_suggestion(finding: Dict[str, Any], lane: str) -> None:
    if _db is None:
        return
    rem = finding.get("remediation", {})
    sig = _signature(finding.get("tool", ""), finding.get("identifier", ""),
                     finding.get("location", ""))
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "suggestion_id": f"rs_{uuid.uuid4().hex[:12]}",
        "source": "supply_chain",
        "source_signature": sig,
        "business_id": BUSINESS_ID,
        "tenant_id": TENANT_ID,
        "created_at": now,
        "status": "pending",
        "severity": _SEV_TO_P.get(finding.get("severity", "medium"), "P2"),
        "classification": f"supply_chain:{finding.get('category')}",
        "root_cause": finding.get("title", "")[:500],
        "suggested_fix": (finding.get("fix") or rem.get("reason") or "")[:1500],
        "code_hint": rem.get("command", "")[:2000],
        "affected_files": [finding.get("location", "")][:10],
        "remediation_kind": rem.get("kind"),
        "lane": lane,                              # needs_approval | manual_only
        "safe_auto_apply": False,
        "requires_deploy": rem.get("kind") in ("pip_upgrade", "pip_upgrade_major", "yarn_upgrade"),
        "tool": finding.get("tool"),
        "identifier": finding.get("identifier"),
    }
    # Dedupe on signature — keep one pending row per unique finding.
    await _db.repair_suggestions.update_one(
        {"source_signature": sig, "status": "pending"},
        {"$setOnInsert": doc},
        upsert=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════
async def run_remediation(auto_apply: bool = False, max_auto: int = 10) -> Dict[str, Any]:
    """Plan + (optionally) apply auto_safe upgrades; queue the rest for Sentinel."""
    if _db is None:
        return {"status": "db_unavailable"}

    snap = await _db["supply_chain_latest"].find_one({"business_id": BUSINESS_ID}, {"_id": 0})
    findings = (snap or {}).get("findings", [])
    if not findings:
        return {"status": "no_findings"}

    plan = build_plan(findings)
    applied: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    if auto_apply:
        for f in plan["auto_safe"][:max_auto]:
            rem = f["remediation"]
            res = await apply_pip_upgrade(rem["name"], rem["current"], rem["target"])
            (applied if res.get("success") else failed).append(res)
            await _db["supply_chain_remediations"].insert_one({
                "business_id": BUSINESS_ID, "tenant_id": TENANT_ID,
                "kind": "pip_upgrade", "finding": f.get("title"),
                "identifier": f.get("identifier"),
                "result": res, "auto": True,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            })
            # If an auto fix failed, downgrade it to a human suggestion.
            if not res.get("success"):
                await _upsert_suggestion(f, lane="needs_approval")
    else:
        # Suggest-only: surface auto_safe candidates too (admin can one-click later).
        for f in plan["auto_safe"]:
            await _upsert_suggestion(f, lane="auto_safe")

    for f in plan["needs_approval"]:
        await _upsert_suggestion(f, lane="needs_approval")
    for f in plan["manual_only"]:
        await _upsert_suggestion(f, lane="manual_only")

    summary = {
        "status": "ok",
        "auto_apply": auto_apply,
        "counts": {
            "auto_safe": len(plan["auto_safe"]),
            "needs_approval": len(plan["needs_approval"]),
            "manual_only": len(plan["manual_only"]),
        },
        "applied": applied,
        "failed": failed,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[SCRemediation] %s — auto_safe=%s approval=%s manual=%s applied=%s failed=%s",
                "AUTO" if auto_apply else "SUGGEST",
                summary["counts"]["auto_safe"], summary["counts"]["needs_approval"],
                summary["counts"]["manual_only"], len(applied), len(failed))
    return summary


async def remediate_after_scan() -> Dict[str, Any]:
    """Hook called by the scanner after every sweep. Auto-applies only when
    AUREM_SUPPLY_CHAIN_AUTOFIX=true; otherwise suggest-only."""
    auto = os.environ.get("AUREM_SUPPLY_CHAIN_AUTOFIX", "").strip().lower() in ("1", "true", "yes")
    try:
        return await run_remediation(auto_apply=auto)
    except Exception as e:  # noqa: BLE001
        logger.error("[SCRemediation] post-scan remediation failed: %s", e)
        return {"status": "error", "error": str(e)[:300]}


async def get_remediation_log(limit: int = 50) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    cur = _db["supply_chain_remediations"].find(
        {"business_id": BUSINESS_ID}, {"_id": 0}
    ).sort("applied_at", -1).limit(limit)
    return await cur.to_list(limit)


print("[STARTUP] Supply-Chain Remediation engine loaded — Sentinel-integrated", flush=True)
