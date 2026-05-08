"""
AUREM PentAGI Integration Service
===================================
Connects to PentAGI (vxcontrol/pentagi) running on Legion via Cloudflare Tunnel.
Enterprise-only feature — full autonomous penetration testing.

PentAGI exposes a GraphQL API at https://{host}:8443/query
Auth: Bearer token (API_TOKEN env in PentAGI)

Flow:
  1. Create a flow (pentest session) via GraphQL
  2. Create a task within the flow
  3. PentAGI agents execute autonomously
  4. Poll for results → return findings to AUREM
"""
import os
import logging
import httpx
import asyncio
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# PentAGI runs on Legion, exposed via Cloudflare Tunnel.
# NOTE: verify=False is intentional on all httpx clients below — Legion uses
# a self-signed cert behind the tunnel. The tunnel itself provides TLS.
PENTAGI_URL = os.environ.get("PENTAGI_URL", "https://pentagi.aurem.live")

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _get_pentagi_url() -> str:
    return os.environ.get("PENTAGI_URL", PENTAGI_URL)


async def check_pentagi_health() -> Dict:
    """Check if PentAGI is reachable on Legion."""
    url = _get_pentagi_url()
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(f"{url}/api/health")
            if resp.is_success:
                return {"online": True, "url": url, "status": resp.json()}
            return {"online": True, "url": url, "status_code": resp.status_code}
    except httpx.ConnectError:
        return {"online": False, "url": url, "error": "Connection refused — PentAGI not running on Legion"}
    except Exception as e:
        return {"online": False, "url": url, "error": str(e)}


async def create_pentest_flow(target: str, description: str = "") -> Dict:
    """
    Create a new PentAGI penetration testing flow via GraphQL.
    Returns flow_id for tracking.
    """
    url = _get_pentagi_url()
    mutation = """
    mutation CreateFlow($input: CreateFlowInput!) {
        createFlow(input: $input) {
            id
            name
            status
            createdAt
        }
    }
    """
    variables = {
        "input": {
            "name": f"AUREM Pentest: {target}",
            "description": description or f"Autonomous penetration test of {target} triggered by AUREM platform"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                f"{url}/query",
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            if resp.is_success:
                data = resp.json()
                if data.get("data", {}).get("createFlow"):
                    return {"success": True, "flow": data["data"]["createFlow"]}
                return {"success": False, "error": data.get("errors", [{}])[0].get("message", "Unknown GraphQL error")}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def create_pentest_task(flow_id: str, target: str, scan_type: str = "full") -> Dict:
    """Create a penetration testing task within a flow."""
    url = _get_pentagi_url()

    task_prompts = {
        "full": f"Perform a comprehensive penetration test on {target}. Start with reconnaissance (nmap, whois), then proceed to vulnerability scanning, exploitation attempts, and generate a detailed report of all findings.",
        "recon": f"Perform thorough reconnaissance on {target}. Use nmap for port scanning, identify services and versions, check for common misconfigurations. Report all findings.",
        "vuln_scan": f"Scan {target} for known vulnerabilities. Check CVEs, test for common web vulnerabilities (XSS, SQLi, SSRF), check SSL/TLS configuration. Report severity-ranked findings.",
        "web_app": f"Perform a web application security test on {target}. Test for OWASP Top 10 vulnerabilities, check authentication mechanisms, test API endpoints, check for information disclosure.",
    }

    prompt = task_prompts.get(scan_type, task_prompts["full"])

    mutation = """
    mutation CreateTask($input: CreateTaskInput!) {
        createTask(input: $input) {
            id
            status
            createdAt
        }
    }
    """
    variables = {
        "input": {
            "flowId": flow_id,
            "prompt": prompt,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                f"{url}/query",
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            if resp.is_success:
                data = resp.json()
                if data.get("data", {}).get("createTask"):
                    return {"success": True, "task": data["data"]["createTask"]}
                return {"success": False, "error": data.get("errors", [{}])[0].get("message", "Unknown error")}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_flow_status(flow_id: str) -> Dict:
    """Get the status and results of a PentAGI flow."""
    url = _get_pentagi_url()
    query = """
    query GetFlow($id: ID!) {
        flow(id: $id) {
            id
            name
            status
            tasks {
                id
                status
                result
                subtasks {
                    id
                    status
                    agentType
                    actions {
                        type
                        status
                        result
                    }
                }
            }
            createdAt
            updatedAt
        }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                f"{url}/query",
                json={"query": query, "variables": {"id": flow_id}},
                headers={"Content-Type": "application/json"},
            )
            if resp.is_success:
                data = resp.json()
                flow = data.get("data", {}).get("flow")
                if flow:
                    return {"success": True, "flow": flow}
                return {"success": False, "error": "Flow not found"}
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def run_pentest(
    target: str,
    scan_type: str = "full",
    description: str = "",
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Full pentest orchestration:
    1. Check PentAGI is online
    2. Create flow + task
    3. Return pentest_id for polling
    4. Save to DB
    """
    pentest_id = f"pt_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)

    # Check health
    health = await check_pentagi_health()
    if not health.get("online"):
        return {
            "pentest_id": pentest_id,
            "status": "pentagi_offline",
            "error": health.get("error", "PentAGI not reachable on Legion"),
            "help": "Start PentAGI on Legion: cd /opt/aurem/legion && docker compose up -d pentagi",
        }

    # Create flow
    flow_result = await create_pentest_flow(target, description)
    if not flow_result.get("success"):
        return {"pentest_id": pentest_id, "status": "error", "error": flow_result.get("error")}

    flow_id = flow_result["flow"]["id"]

    # Create task
    task_result = await create_pentest_task(flow_id, target, scan_type)
    if not task_result.get("success"):
        return {"pentest_id": pentest_id, "status": "error", "flow_id": flow_id, "error": task_result.get("error")}

    task_id = task_result["task"]["id"]

    # Save to DB
    db = _get_db()
    record = {
        "pentest_id": pentest_id,
        "tenant_id": tenant_id,
        "target": target,
        "scan_type": scan_type,
        "description": description,
        "flow_id": flow_id,
        "task_id": task_id,
        "status": "running",
        "created_at": now.isoformat(),
        "results": None,
    }
    if db:
        await db.pentagi_pentests.insert_one({**record})

    return {
        "pentest_id": pentest_id,
        "flow_id": flow_id,
        "task_id": task_id,
        "status": "running",
        "target": target,
        "scan_type": scan_type,
        "message": f"PentAGI autonomous pentest started on {target}",
    }


async def get_pentest_results(pentest_id: str, tenant_id: str = None) -> Dict:
    """Get results of a running/completed pentest."""
    db = _get_db()
    if not db:
        return {"error": "no_db"}

    record = await db.pentagi_pentests.find_one(
        {"pentest_id": pentest_id}, {"_id": 0}
    )
    if not record:
        return {"error": "pentest_not_found"}

    # If still running, poll PentAGI for updates
    if record.get("status") == "running" and record.get("flow_id"):
        flow_status = await get_flow_status(record["flow_id"])
        if flow_status.get("success"):
            flow = flow_status["flow"]
            record["flow_status"] = flow.get("status")
            record["tasks"] = flow.get("tasks", [])

            # Check if completed
            if flow.get("status") in ("completed", "failed"):
                record["status"] = flow["status"]
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                await db.pentagi_pentests.update_one(
                    {"pentest_id": pentest_id},
                    {"$set": {"status": record["status"], "completed_at": record["completed_at"],
                              "results": flow}},
                )

    return record


async def get_pentest_history(tenant_id: str = None, limit: int = 20) -> list:
    db = _get_db()
    if not db:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.pentagi_pentests.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
