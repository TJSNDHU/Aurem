"""
AUREM n8n Workflow Connector — 400+ Integrations via n8n
=========================================================
Connects to user's n8n instance for workflow automation.
Wire to Envoy Agent as additional execution channel.
Needs: N8N_API_URL + N8N_API_KEY in .env
"""
import os
import logging
import httpx
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_config() -> Dict:
    url = os.environ.get("N8N_API_URL", "")
    key = os.environ.get("N8N_API_KEY", "")
    return {"url": url.rstrip("/"), "key": key, "configured": bool(url and key)}


async def check_connection() -> Dict:
    """Check if n8n instance is reachable."""
    cfg = _get_config()
    if not cfg["configured"]:
        return {"connected": False, "reason": "N8N_API_URL and N8N_API_KEY not set in .env",
                "setup": "Get from your n8n instance: Settings → API → Create API Key"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{cfg['url']}/api/v1/workflows", headers={"X-N8N-API-KEY": cfg["key"]}, params={"limit": 1})
            if r.status_code == 200:
                return {"connected": True, "url": cfg["url"], "workflows": r.json().get("count", 0)}
            return {"connected": False, "status": r.status_code, "error": r.text[:200]}
    except Exception as e:
        return {"connected": False, "error": str(e)}


async def list_workflows(limit: int = 20, active_only: bool = False) -> List[Dict]:
    """List workflows from n8n instance."""
    cfg = _get_config()
    if not cfg["configured"]:
        return []
    try:
        params = {"limit": limit}
        if active_only:
            params["active"] = "true"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{cfg['url']}/api/v1/workflows", headers={"X-N8N-API-KEY": cfg["key"]}, params=params)
            if r.status_code == 200:
                data = r.json().get("data", [])
                return [{"id": w["id"], "name": w.get("name", ""), "active": w.get("active", False),
                         "nodes": len(w.get("nodes", [])), "tags": [t.get("name", "") for t in w.get("tags", [])]}
                        for w in data]
    except Exception as e:
        logger.warning(f"[N8N] List workflows failed: {e}")
    return []


async def trigger_workflow(workflow_id: str, data: Dict = None) -> Dict:
    """Trigger an n8n workflow execution."""
    cfg = _get_config()
    if not cfg["configured"]:
        return {"triggered": False, "reason": "n8n not configured"}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            # Try webhook trigger first
            r = await c.post(
                f"{cfg['url']}/api/v1/workflows/{workflow_id}/activate",
                headers={"X-N8N-API-KEY": cfg["key"]},
            )
            # Then execute
            r = await c.post(
                f"{cfg['url']}/api/v1/executions",
                headers={"X-N8N-API-KEY": cfg["key"]}, json={"workflowId": workflow_id, "data": data or {}},
            )
            if r.status_code in (200, 201):
                return {"triggered": True, "execution": r.json(), "workflow_id": workflow_id}
            return {"triggered": False, "status": r.status_code, "error": r.text[:200]}
    except Exception as e:
        return {"triggered": False, "error": str(e)}


async def get_workflow(workflow_id: str) -> Dict:
    """Get workflow details from n8n."""
    cfg = _get_config()
    if not cfg["configured"]:
        return {"error": "n8n not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{cfg['url']}/api/v1/workflows/{workflow_id}", headers={"X-N8N-API-KEY": cfg["key"]})
            if r.status_code == 200:
                w = r.json()
                return {"id": w["id"], "name": w.get("name", ""), "active": w.get("active", False),
                        "nodes": [{"type": n.get("type", ""), "name": n.get("name", "")} for n in w.get("nodes", [])],
                        "connections": len(w.get("connections", {}))}
    except Exception as e:
        logger.warning(f"[N8N] Get workflow failed: {e}")
    return {"error": "failed"}
