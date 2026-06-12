"""
AUREM Supply-Chain & Secret Security Scanner
=============================================
Fully autonomous, REAL (no-mock) security sweep of AUREM's own codebase.
Closes the gaps identified against the 15-category scanning taxonomy:

  • SECRET SCANNING (Cat 2)  → detect-secrets  (+ trufflehog if binary present)
  • SCA / Python deps (Cat 2) → pip-audit
  • SCA / JS deps (Cat 2)     → yarn audit
  • SAST / Python (Cat 1)     → bandit

Every scanner shells out to the REAL tool, parses its REAL JSON output, and
normalises findings into a single schema. Results are stored per-tenant
(business_id == "aurem_self" — we dog-food our own platform) in
`supply_chain_scans` (history) + `supply_chain_latest` (current snapshot).

The loop runs every 6h inside the Pillar-3 worker (same isolation as
self_repair_loop). When critical/high findings increase vs the previous
snapshot, an alert row is written to `notifications`.

Toggle off with env  AUREM_SUPPLY_CHAIN_DISABLED=1.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# The backend runs under supervisor whose PATH often omits the venv bin dir
# where pip-installed CLIs (bandit, detect-secrets, pip-audit) live. Build an
# augmented PATH so async subprocesses can always resolve them.
_VENV_BIN = os.path.dirname(sys.executable)
_AUG_PATH = os.pathsep.join([
    _VENV_BIN, "/usr/local/bin", "/usr/bin", "/bin",
    os.environ.get("PATH", ""),
])
_SUBPROC_ENV = {**os.environ, "PATH": _AUG_PATH}

# ── Self-tenant identity — AUREM scans itself ─────────────────────────────
BUSINESS_ID = "aurem_self"
TENANT_ID = "aurem_self"

REPO_ROOT = "/app"
BACKEND_DIR = "/app/backend"
FRONTEND_DIR = "/app/frontend"

SCAN_INTERVAL_HOURS = 6
INITIAL_DELAY_S = 2100  # 35 min — after self_repair (30m) so we don't pile up at boot
PER_TOOL_TIMEOUT_S = 200
MAX_STORED_FINDINGS = 250  # keep doc well under Mongo's 16MB ceiling

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ══════════════════════════════════════════════════════════════════════════
# Low-level: run a tool as an async subprocess and return (rc, stdout, stderr)
# ══════════════════════════════════════════════════════════════════════════
async def _run(cmd: List[str], cwd: str, timeout: int = PER_TOOL_TIMEOUT_S) -> Dict[str, Any]:
    """Run a command without blocking the event loop. Never raises."""
    # Resolve the binary against the augmented PATH (venv + system dirs).
    resolved = shutil.which(cmd[0], path=_AUG_PATH)
    if not resolved:
        return {"ok": False, "rc": -1, "stdout": "", "stderr": f"{cmd[0]} not found on PATH", "missing": True}
    cmd = [resolved, *cmd[1:]]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=_SUBPROC_ENV,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"ok": False, "rc": -1, "stdout": "", "stderr": "binary not found", "missing": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)[:300], "missing": False}

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"ok": False, "rc": -1, "stdout": "", "stderr": f"timeout after {timeout}s", "missing": False}

    return {
        "ok": True,
        "rc": proc.returncode,
        "stdout": (out or b"").decode("utf-8", "replace"),
        "stderr": (err or b"").decode("utf-8", "replace")[:500],
        "missing": False,
    }


def _finding(tool: str, category: str, severity: str, title: str,
             location: str = "", identifier: str = "", fix: str = "") -> Dict[str, Any]:
    return {
        "tool": tool,
        "category": category,            # SAST | SCA | SECRET
        "severity": (severity or "medium").lower(),
        "title": title[:400],
        "location": location[:300],
        "identifier": identifier[:120],
        "fix": fix[:300],
    }


# ══════════════════════════════════════════════════════════════════════════
# Scanner 1 — bandit (Python SAST)
# ══════════════════════════════════════════════════════════════════════════
async def scan_bandit() -> Dict[str, Any]:
    cmd = [
        "bandit", "-r", BACKEND_DIR,
        "-x", f"{BACKEND_DIR}/tests,{BACKEND_DIR}/graphify-out,{BACKEND_DIR}/.venv",
        "--severity-level", "medium",
        "--confidence-level", "medium",
        "-f", "json", "-q",
    ]
    res = await _run(cmd, cwd=BACKEND_DIR)
    if not res["ok"] or not res["stdout"].strip():
        return {"tool": "bandit", "category": "SAST", "status": "error",
                "error": res["stderr"] or "no output", "findings": []}
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        return {"tool": "bandit", "category": "SAST", "status": "error",
                "error": "unparseable JSON", "findings": []}

    findings: List[Dict[str, Any]] = []
    for r in data.get("results", []):
        sev = (r.get("issue_severity") or "MEDIUM").lower()
        loc = f"{r.get('filename','').replace(BACKEND_DIR, 'backend')}:{r.get('line_number','')}"
        findings.append(_finding(
            "bandit", "SAST", sev,
            r.get("issue_text", "Security smell"),
            location=loc,
            identifier=r.get("test_id", ""),
            fix=r.get("more_info", ""),
        ))
    return {"tool": "bandit", "category": "SAST", "status": "ok", "findings": findings}


# ══════════════════════════════════════════════════════════════════════════
# Scanner 2 — detect-secrets (secret scanning)
# ══════════════════════════════════════════════════════════════════════════
async def scan_detect_secrets() -> Dict[str, Any]:
    cmd = [
        "detect-secrets", "scan",
        f"{BACKEND_DIR}", f"{FRONTEND_DIR}/src",
        "--exclude-files", r"\.lock$|node_modules|\.venv|graphify-out|test_",
    ]
    res = await _run(cmd, cwd=REPO_ROOT)
    if not res["ok"] or not res["stdout"].strip():
        return {"tool": "detect-secrets", "category": "SECRET", "status": "error",
                "error": res["stderr"] or "no output", "findings": []}
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        return {"tool": "detect-secrets", "category": "SECRET", "status": "error",
                "error": "unparseable JSON", "findings": []}

    findings: List[Dict[str, Any]] = []
    for fname, secrets in (data.get("results") or {}).items():
        for s in secrets:
            findings.append(_finding(
                "detect-secrets", "SECRET", "high",
                f"Potential {s.get('type', 'secret')} committed in code",
                location=f"{fname}:{s.get('line_number', '')}",
                identifier=s.get("type", ""),
                fix="Rotate the credential and move it to an env var / secret store.",
            ))
    return {"tool": "detect-secrets", "category": "SECRET", "status": "ok", "findings": findings}


# ══════════════════════════════════════════════════════════════════════════
# Scanner 3 — trufflehog (verified secret scanning, best-effort)
# ══════════════════════════════════════════════════════════════════════════
async def scan_trufflehog() -> Dict[str, Any]:
    if not shutil.which("trufflehog", path=_AUG_PATH):
        return {"tool": "trufflehog", "category": "SECRET", "status": "skipped",
                "error": "binary not installed", "findings": []}
    cmd = [
        "trufflehog", "filesystem", BACKEND_DIR, f"{FRONTEND_DIR}/src",
        "--json", "--no-update", "--no-verification",
    ]
    res = await _run(cmd, cwd=REPO_ROOT, timeout=150)
    if not res["ok"]:
        return {"tool": "trufflehog", "category": "SECRET", "status": "error",
                "error": res["stderr"] or "run failed", "findings": []}

    findings: List[Dict[str, Any]] = []
    for line in res["stdout"].splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        det = o.get("DetectorName") or o.get("DetectorType") or "secret"
        verified = bool(o.get("Verified"))
        meta = (o.get("SourceMetadata") or {}).get("Data", {}) or {}
        fs = (meta.get("Filesystem") or {})
        loc = fs.get("file", "")
        findings.append(_finding(
            "trufflehog", "SECRET", "critical" if verified else "high",
            f"{'VERIFIED live' if verified else 'Unverified'} {det} secret",
            location=loc,
            identifier=det,
            fix="Rotate immediately; purge from git history.",
        ))
    return {"tool": "trufflehog", "category": "SECRET", "status": "ok", "findings": findings}


# ══════════════════════════════════════════════════════════════════════════
# Scanner 4 — pip-audit (Python dependency SCA)
# ══════════════════════════════════════════════════════════════════════════
async def scan_pip_audit() -> Dict[str, Any]:
    res = await _run(["pip-audit", "--format", "json"], cwd=BACKEND_DIR)
    if not res["ok"] or not res["stdout"].strip():
        return {"tool": "pip-audit", "category": "SCA", "status": "error",
                "error": res["stderr"] or "no output", "findings": []}
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        return {"tool": "pip-audit", "category": "SCA", "status": "error",
                "error": "unparseable JSON", "findings": []}

    findings: List[Dict[str, Any]] = []
    for dep in data.get("dependencies", []):
        name, ver = dep.get("name", "?"), dep.get("version", "?")
        for v in dep.get("vulns", []):
            fix_vers = ", ".join(v.get("fix_versions", []) or [])
            findings.append(_finding(
                "pip-audit", "SCA", "high",
                f"{name} {ver} — {v.get('id', 'CVE')}",
                location=f"backend/requirements.txt → {name}=={ver}",
                identifier=v.get("id", ""),
                fix=f"Upgrade to {fix_vers}" if fix_vers else "No fix released yet",
            ))
    return {"tool": "pip-audit", "category": "SCA", "status": "ok", "findings": findings}


# ══════════════════════════════════════════════════════════════════════════
# Scanner 5 — yarn audit (JS dependency SCA)
# ══════════════════════════════════════════════════════════════════════════
async def scan_yarn_audit() -> Dict[str, Any]:
    # yarn classic emits NDJSON; non-zero rc is normal when vulns exist.
    res = await _run(["yarn", "audit", "--json"], cwd=FRONTEND_DIR)
    if not res["ok"] or not res["stdout"].strip():
        return {"tool": "yarn-audit", "category": "SCA", "status": "error",
                "error": res["stderr"] or "no output", "findings": []}

    sev_map = {"critical": "critical", "high": "high", "moderate": "medium", "low": "low", "info": "info"}
    findings: List[Dict[str, Any]] = []
    seen = set()
    for line in res["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("type") != "auditAdvisory":
            continue
        adv = (o.get("data") or {}).get("advisory") or {}
        module = adv.get("module_name", "?")
        sev = sev_map.get((adv.get("severity") or "low").lower(), "low")
        key = (module, adv.get("id"))
        if key in seen:
            continue
        seen.add(key)
        findings.append(_finding(
            "yarn-audit", "SCA", sev,
            f"{module} — {adv.get('title', 'vulnerability')}",
            location=f"frontend/package.json → {module}",
            identifier=str(adv.get("github_advisory_id") or adv.get("cves") or adv.get("id") or ""),
            fix=(adv.get("recommendation") or "")[:300],
        ))
    return {"tool": "yarn-audit", "category": "SCA", "status": "ok", "findings": findings}


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════
def _summarise(tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    by_cat = {"SAST": 0, "SCA": 0, "SECRET": 0}
    by_tool: Dict[str, Dict[str, Any]] = {}
    all_findings: List[Dict[str, Any]] = []

    for tr in tool_results:
        f = tr.get("findings", [])
        by_tool[tr["tool"]] = {
            "status": tr.get("status"),
            "count": len(f),
            "category": tr.get("category"),
            "error": tr.get("error"),
        }
        for item in f:
            by_sev[item["severity"]] = by_sev.get(item["severity"], 0) + 1
            by_cat[item["category"]] = by_cat.get(item["category"], 0) + 1
            all_findings.append(item)

    all_findings.sort(key=lambda x: _SEVERITY_RANK.get(x["severity"], 0), reverse=True)
    total = len(all_findings)
    # Posture score: 100 minus weighted penalties, floored at 0.
    penalty = by_sev["critical"] * 25 + by_sev["high"] * 8 + by_sev["medium"] * 2 + by_sev["low"] * 0.5
    score = max(0, round(100 - penalty))
    return {
        "by_severity": by_sev,
        "by_category": by_cat,
        "by_tool": by_tool,
        "total_findings": total,
        "posture_score": score,
        "findings": all_findings,
    }


async def run_supply_chain_scan(trigger: str = "scheduled") -> Dict[str, Any]:
    """Run all scanners concurrently, persist results, alert on regression."""
    started = datetime.now(timezone.utc)
    logger.info("[SupplyChain] scan started (trigger=%s)", trigger)

    tool_results = await asyncio.gather(
        scan_bandit(),
        scan_detect_secrets(),
        scan_trufflehog(),
        scan_pip_audit(),
        scan_yarn_audit(),
        return_exceptions=True,
    )
    # Normalise any gather exception into an error result
    clean: List[Dict[str, Any]] = []
    names = ["bandit", "detect-secrets", "trufflehog", "pip-audit", "yarn-audit"]
    cats = ["SAST", "SECRET", "SECRET", "SCA", "SCA"]
    for i, tr in enumerate(tool_results):
        if isinstance(tr, Exception):
            clean.append({"tool": names[i], "category": cats[i], "status": "error",
                          "error": str(tr)[:300], "findings": []})
        else:
            clean.append(tr)

    summary = _summarise(clean)
    finished = datetime.now(timezone.utc)
    doc = {
        "business_id": BUSINESS_ID,
        "tenant_id": TENANT_ID,
        "trigger": trigger,
        "scanned_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 1),
        "posture_score": summary["posture_score"],
        "total_findings": summary["total_findings"],
        "by_severity": summary["by_severity"],
        "by_category": summary["by_category"],
        "by_tool": summary["by_tool"],
        "findings": summary["findings"][:MAX_STORED_FINDINGS],
        "findings_truncated": summary["total_findings"] > MAX_STORED_FINDINGS,
    }

    if _db is not None:
        try:
            prev = await _db["supply_chain_latest"].find_one(
                {"business_id": BUSINESS_ID}, {"_id": 0, "by_severity": 1}
            )
            await _db["supply_chain_scans"].insert_one({**doc})
            await _db["supply_chain_latest"].replace_one(
                {"business_id": BUSINESS_ID}, {**doc}, upsert=True
            )
            await _maybe_alert(prev, summary["by_severity"])
        except Exception as e:  # noqa: BLE001
            logger.warning("[SupplyChain] persist failed: %s", e)

    # ── Sentinel-integrated remediation: plan + queue + (opt) auto-apply ──
    try:
        from services.supply_chain_remediation import remediate_after_scan, set_db as _set_rem_db
        _set_rem_db(_db)
        rem = await remediate_after_scan()
        logger.info("[SupplyChain] remediation: %s", rem.get("counts") or rem.get("status"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[SupplyChain] remediation hook failed: %s", e)

    logger.info(
        "[SupplyChain] done in %.1fs — score=%s crit=%s high=%s med=%s total=%s",
        doc["duration_s"], summary["posture_score"],
        summary["by_severity"]["critical"], summary["by_severity"]["high"],
        summary["by_severity"]["medium"], summary["total_findings"],
    )
    # Drop the heavy findings list from the returned summary for callers that log it
    return {k: v for k, v in doc.items() if k != "findings"} | {"findings_count": len(doc["findings"])}


async def _maybe_alert(prev: Optional[Dict[str, Any]], current: Dict[str, int]) -> None:
    """Write a notification row when critical/high findings regress."""
    if _db is None:
        return
    prev_sev = (prev or {}).get("by_severity", {}) if prev else {}
    prev_hi = (prev_sev.get("critical", 0) + prev_sev.get("high", 0)) if prev else -1
    cur_hi = current.get("critical", 0) + current.get("high", 0)
    if prev is not None and cur_hi <= prev_hi:
        return
    if cur_hi == 0:
        return
    try:
        await _db["notifications"].insert_one({
            "business_id": BUSINESS_ID,
            "tenant_id": TENANT_ID,
            "type": "supply_chain_alert",
            "severity": "critical" if current.get("critical", 0) else "high",
            "title": "Supply-chain / secret findings increased",
            "message": (
                f"Security sweep found {current.get('critical',0)} critical and "
                f"{current.get('high',0)} high issues in AUREM's own codebase/deps."
            ),
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.warning("[SupplyChain] ALERT raised — crit/high rose to %s", cur_hi)
    except Exception as e:  # noqa: BLE001
        logger.warning("[SupplyChain] alert write failed: %s", e)


async def get_latest() -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    return await _db["supply_chain_latest"].find_one({"business_id": BUSINESS_ID}, {"_id": 0})


async def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    cursor = _db["supply_chain_scans"].find(
        {"business_id": BUSINESS_ID},
        {"_id": 0, "findings": 0},
    ).sort("scanned_at", -1).limit(limit)
    return await cursor.to_list(limit)


# ══════════════════════════════════════════════════════════════════════════
# Autonomous loop — wired into the Pillar-3 worker
# ══════════════════════════════════════════════════════════════════════════
async def supply_chain_loop() -> None:
    if os.environ.get("AUREM_SUPPLY_CHAIN_DISABLED", "").strip() in ("1", "true", "yes"):
        logger.info("[SupplyChain] loop disabled via AUREM_SUPPLY_CHAIN_DISABLED")
        return

    await asyncio.sleep(INITIAL_DELAY_S)
    try:
        await run_supply_chain_scan(trigger="boot")
    except Exception as e:  # noqa: BLE001
        logger.error("[SupplyChain] initial scan failed: %s", e)

    while True:
        try:
            await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
            await run_supply_chain_scan(trigger="scheduled")
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            logger.error("[SupplyChain] loop error: %s", e)
            await asyncio.sleep(300)


print("[STARTUP] Supply-Chain Scanner loaded — bandit+detect-secrets+pip-audit+yarn-audit every 6h", flush=True)
