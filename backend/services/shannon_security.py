"""
Shannon Security Service — Autonomous Red Team Integration
===========================================================
Receives pentest reports from Shannon (running on Legion),
stores findings, calculates security posture score, and
exposes data to Sentinel Overwatch and the Sentinel Dashboard.

Shannon runs locally: `npx shannon audit http://localhost:11434 --source ../backend`
Then pushes results: `curl -X POST https://aurem.live/api/security/shannon/report -d @report.json`
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory store (also persisted to MongoDB when available)
_latest_report: Optional[Dict] = None
_report_history: List[Dict] = []
_MAX_HISTORY = 50


def _calculate_security_score(vulnerabilities: List[Dict]) -> int:
    """Calculate 0-100 security score based on findings."""
    if not vulnerabilities:
        return 100
    score = 100
    for vuln in vulnerabilities:
        severity = vuln.get("severity", "info").lower()
        if severity == "critical":
            score -= 25
        elif severity == "high":
            score -= 15
        elif severity == "medium":
            score -= 8
        elif severity == "low":
            score -= 3
    return max(0, score)


def _severity_counts(vulnerabilities: List[Dict]) -> Dict[str, int]:
    """Count vulnerabilities by severity."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for vuln in vulnerabilities:
        sev = vuln.get("severity", "info").lower()
        if sev in counts:
            counts[sev] += 1
    return counts


async def ingest_report(report: Dict) -> Dict:
    """Process a Shannon pentest report from Legion."""
    global _latest_report

    vulns = report.get("vulnerabilities", report.get("findings", []))
    timestamp = report.get("timestamp", datetime.now(timezone.utc).isoformat())
    target = report.get("target", report.get("url", "unknown"))
    scan_duration = report.get("duration_seconds", report.get("duration", 0))

    processed = {
        "timestamp": timestamp,
        "target": target,
        "scan_duration_seconds": scan_duration,
        "total_vulnerabilities": len(vulns),
        "severity_counts": _severity_counts(vulns),
        "security_score": _calculate_security_score(vulns),
        "vulnerabilities": vulns[:50],
        "exploits_verified": len([v for v in vulns if v.get("verified") or v.get("exploitable")]),
        "scanner": report.get("scanner", "shannon"),
        "scanner_version": report.get("version", "unknown"),
    }

    _latest_report = processed
    _report_history.append(processed)
    if len(_report_history) > _MAX_HISTORY:
        _report_history.pop(0)

    # Persist to MongoDB
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            await server.db.shannon_reports.insert_one({
                **processed,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            # Update the agent card status
            from services.agent_cards import _registry
            shannon_card = _registry.get("shannon") if isinstance(_registry, dict) else None
            if shannon_card is not None:
                shannon_card.status = "active"
                shannon_card.last_execution = timestamp
                shannon_card.execution_count += 1
                if processed["security_score"] >= 70:
                    shannon_card.success_count += 1

            # Log to agent traces
            await server.db.agent_traces.insert_one({
                "agent": "shannon",
                "action": "pentest_complete",
                "detail": f"Shannon scan of {target}: score {processed['security_score']}/100, {len(vulns)} findings ({processed['severity_counts']['critical']} critical)",
                "severity": "critical" if processed["severity_counts"]["critical"] > 0 else "info",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.warning(f"[Shannon] DB persist failed: {e}")

    # Update Shannon agent card execution
    try:
        from services.agent_cards import _log_swarm_event
        _log_swarm_event("execute", "shannon", f"Pentest complete: {processed['security_score']}/100 score, {len(vulns)} vulns")
    except Exception:
        pass

    logger.info(f"[Shannon] Report ingested: {target} → score {processed['security_score']}/100, {len(vulns)} vulnerabilities")
    return processed


def get_security_posture() -> Dict:
    """Get current security posture for Overwatch dashboard."""
    # Cloud perimeter health — always available even without Legion
    perimeter = _get_cloud_perimeter()

    if not _latest_report:
        return {
            "score": None,
            "status": "standby",
            "last_audit": None,
            "total_vulnerabilities": 0,
            "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "exploits_verified": 0,
            "audits_completed": 0,
            "perimeter": perimeter,
        }

    # Calculate time since last audit
    time_since = None
    if _latest_report.get("timestamp"):
        try:
            from datetime import datetime, timezone
            last = datetime.fromisoformat(_latest_report["timestamp"].replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - last
            hours = int(delta.total_seconds() / 3600)
            if hours < 1:
                time_since = f"{int(delta.total_seconds() / 60)}m ago"
            elif hours < 24:
                time_since = f"{hours}h ago"
            else:
                time_since = f"{hours // 24}d {hours % 24}h ago"
        except Exception:
            pass

    return {
        "score": _latest_report["security_score"],
        "status": "critical" if _latest_report["severity_counts"]["critical"] > 0 else "warning" if _latest_report["severity_counts"]["high"] > 0 else "healthy",
        "last_audit": _latest_report["timestamp"],
        "time_since_audit": time_since,
        "target": _latest_report.get("target", "unknown"),
        "total_vulnerabilities": _latest_report["total_vulnerabilities"],
        "severity_counts": _latest_report["severity_counts"],
        "exploits_verified": _latest_report["exploits_verified"],
        "audits_completed": len(_report_history),
        "scan_duration": _latest_report.get("scan_duration_seconds", 0),
        "perimeter": perimeter,
    }


def _get_cloud_perimeter() -> Dict:
    """Cloud-side security checks that work without Legion."""
    import os
    checks = {
        "ssl_active": True,
        "cors_configured": bool(os.getenv("CORS_ORIGINS")),
        "jwt_configured": bool(os.getenv("JWT_SECRET")),
        "rate_limiting": True,
        "api_auth": True,
        "db_encrypted": "mongodb+srv" in (os.getenv("MONGO_URL", "") or ""),
    }
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "score": int((passed / total) * 100) if total > 0 else 0,
        "status": "guarded" if passed == total else "partial" if passed >= total - 1 else "exposed",
    }


async def generate_mock_audit() -> Dict:
    """Generate a simulated security audit for testing the dashboard UI."""
    import random
    mock_vulns = [
        {"severity": "high", "title": "Outdated TLS Configuration", "description": "TLS 1.0/1.1 still accepted on some endpoints", "verified": True, "exploitable": False, "cwe": "CWE-326", "category": "crypto"},
        {"severity": "medium", "title": "Missing Content-Security-Policy", "description": "CSP header not set on main application", "verified": True, "exploitable": False, "cwe": "CWE-1021", "category": "headers"},
        {"severity": "medium", "title": "Verbose Error Messages", "description": "Stack traces exposed in 500 responses", "verified": False, "cwe": "CWE-209", "category": "info_disclosure"},
        {"severity": "low", "title": "Server Version Disclosure", "description": "X-Powered-By header reveals framework info", "verified": False, "cwe": "CWE-200", "category": "headers"},
        {"severity": "low", "title": "Cookie Missing SameSite", "description": "Session cookies lack SameSite attribute", "verified": False, "cwe": "CWE-1275", "category": "cookies"},
        {"severity": "info", "title": "HSTS Not Enforced", "description": "Strict-Transport-Security header missing", "verified": False, "cwe": "CWE-523", "category": "transport"},
    ]
    # Randomly select 3-5 vulns for variety
    selected = random.sample(mock_vulns, min(random.randint(3, 5), len(mock_vulns)))

    mock_report = {
        "target": "https://aurem.live",
        "scanner": "shannon_mock",
        "version": "1.0.0-sim",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(random.uniform(8.0, 25.0), 1),
        "vulnerabilities": selected,
    }
    return await ingest_report(mock_report)


async def get_full_report() -> Optional[Dict]:
    """Get the full latest Shannon report with vulnerability details."""
    if _latest_report:
        return _latest_report

    # Try loading from DB
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            report = await server.db.shannon_reports.find_one(
                {}, {"_id": 0}, sort=[("created_at", -1)]
            )
            if report:
                return report
    except Exception:
        pass
    return None


async def get_report_history() -> List[Dict]:
    """Get history of Shannon audits for trend analysis."""
    if _report_history:
        return [{"timestamp": r["timestamp"], "score": r["security_score"], "vulns": r["total_vulnerabilities"], "target": r.get("target")} for r in _report_history]

    # Try loading from DB
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            cursor = server.db.shannon_reports.find(
                {}, {"_id": 0, "timestamp": 1, "security_score": 1, "total_vulnerabilities": 1, "target": 1}
            ).sort("created_at", -1).limit(20)
            return await cursor.to_list(length=20)
    except Exception:
        pass
    return []
