"""
AUREM GitHub Deploy Service — Hybrid Fix Deployment
====================================================
When AUREM generates a fix:
1. Create a branch in customer's GitHub repo
2. Commit the fix with description
3. Open a Pull Request automatically
4. Customer just clicks 'Merge' — GitHub Actions deploys

Per-tenant GitHub token storage via nexus_credentials.
"""
import os
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict
import httpx

logger = logging.getLogger(__name__)

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
            return _db
    except Exception:
        pass
    return None


GITHUB_API = "https://api.github.com"


async def _get_tenant_github_token(tenant_id: str) -> Optional[str]:
    """Retrieve stored GitHub token for a tenant."""
    db = _get_db()
    if db is None:
        return None
    doc = await db.github_connections.find_one(
        {"tenant_id": tenant_id, "status": "connected"},
        {"_id": 0, "token": 1},
    )
    if doc and doc.get("token"):
        return doc["token"]
    # Fallback: check nexus_credentials
    cred = await db.nexus_credentials.find_one(
        {"tenant_id": tenant_id, "connector_id": "github", "status": "connected"},
        {"_id": 0, "token": 1},
    )
    return cred.get("token") if cred else None


async def connect_github(tenant_id: str, token: str) -> Dict:
    """Store customer GitHub token securely per tenant."""
    db = _get_db()
    if db is None:
        return {"connected": False, "error": "no_db"}

    # Verify token works
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{GITHUB_API}/user", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        if resp.status_code != 200:
            return {"connected": False, "error": f"GitHub auth failed: {resp.status_code}"}
        user_data = resp.json()

    now = datetime.now(timezone.utc).isoformat()
    await db.github_connections.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "tenant_id": tenant_id,
            "token": token,
            "github_username": user_data.get("login", ""),
            "github_name": user_data.get("name", ""),
            "status": "connected",
            "connected_at": now,
            "updated_at": now,
        }},
        upsert=True,
    )
    logger.info(f"[GitHub] Connected for tenant {tenant_id} as {user_data.get('login')}")
    return {"connected": True, "username": user_data.get("login"), "name": user_data.get("name")}


async def push_fix(
    tenant_id: str,
    repo: str,
    fix_title: str,
    fix_description: str,
    file_path: str,
    file_content: str,
    base_branch: str = "main",
) -> Dict:
    """
    Create branch → commit fix → open PR in customer's repo.
    Returns PR URL on success.
    """
    token = await _get_tenant_github_token(tenant_id)
    if not token:
        return {"success": False, "error": "No GitHub token for this tenant. Connect GitHub first."}

    branch_name = f"aurem/fix-{secrets.token_hex(6)}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get base branch SHA
        ref_resp = await client.get(f"{GITHUB_API}/repos/{repo}/git/ref/heads/{base_branch}", headers=headers)
        if ref_resp.status_code != 200:
            return {"success": False, "error": f"Cannot access repo {repo} branch {base_branch}: {ref_resp.status_code}"}
        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create new branch
        branch_resp = await client.post(
            f"{GITHUB_API}/repos/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if branch_resp.status_code not in (200, 201):
            return {"success": False, "error": f"Failed to create branch: {branch_resp.status_code}"}

        # 3. Create/update file with fix content
        import base64
        encoded = base64.b64encode(file_content.encode()).decode()

        # Check if file exists
        existing = await client.get(f"{GITHUB_API}/repos/{repo}/contents/{file_path}?ref={branch_name}", headers=headers)
        payload = {
            "message": f"[AUREM] {fix_title}",
            "content": encoded,
            "branch": branch_name,
        }
        if existing.status_code == 200:
            payload["sha"] = existing.json().get("sha")

        file_resp = await client.put(
            f"{GITHUB_API}/repos/{repo}/contents/{file_path}",
            headers=headers,
            json=payload,
        )
        if file_resp.status_code not in (200, 201):
            return {"success": False, "error": f"Failed to commit file: {file_resp.status_code}"}

        # 4. Create Pull Request
        pr_body = f"## AUREM Automated Fix\n\n{fix_description}\n\n---\n*Generated by AUREM AI Repair Engine*"
        pr_resp = await client.post(
            f"{GITHUB_API}/repos/{repo}/pulls",
            headers=headers,
            json={
                "title": f"[AUREM] {fix_title}",
                "body": pr_body,
                "head": branch_name,
                "base": base_branch,
            },
        )
        if pr_resp.status_code not in (200, 201):
            err = pr_resp.json().get("message", str(pr_resp.status_code))
            return {"success": False, "error": f"Failed to create PR: {err}"}

        pr_data = pr_resp.json()
        pr_url = pr_data.get("html_url", "")

        # 5. Log deployment
        db = _get_db()
        if db:
            await db.github_deployments.insert_one({
                "tenant_id": tenant_id,
                "repo": repo,
                "branch": branch_name,
                "pr_url": pr_url,
                "pr_number": pr_data.get("number"),
                "fix_title": fix_title,
                "file_path": file_path,
                "status": "pr_created",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(f"[GitHub] PR created: {pr_url}")
        return {"success": True, "pr_url": pr_url, "pr_number": pr_data.get("number"), "branch": branch_name}


async def get_pr_status(tenant_id: str, pr_number: int = None, repo: str = None) -> Dict:
    """Check if PR has been merged."""
    token = await _get_tenant_github_token(tenant_id)
    if not token:
        return {"error": "No GitHub token"}

    db = _get_db()
    if not repo or not pr_number:
        if db:
            latest = await db.github_deployments.find_one(
                {"tenant_id": tenant_id}, {"_id": 0}, sort=[("created_at", -1)]
            )
            if latest:
                repo = latest.get("repo", repo)
                pr_number = latest.get("pr_number", pr_number)

    if not repo or not pr_number:
        return {"error": "No PR found"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        if resp.status_code != 200:
            return {"error": f"Cannot fetch PR: {resp.status_code}"}
        pr = resp.json()
        return {
            "pr_number": pr_number,
            "repo": repo,
            "state": pr.get("state"),
            "merged": pr.get("merged", False),
            "mergeable": pr.get("mergeable"),
            "title": pr.get("title"),
            "url": pr.get("html_url"),
            "created_at": pr.get("created_at"),
            "merged_at": pr.get("merged_at"),
        }


async def get_connection_status(tenant_id: str) -> Dict:
    """Check if tenant has GitHub connected."""
    db = _get_db()
    if db is None:
        return {"connected": False}
    doc = await db.github_connections.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "status": 1, "github_username": 1, "connected_at": 1}
    )
    if doc and doc.get("status") == "connected":
        return {"connected": True, "username": doc.get("github_username", ""), "connected_at": doc.get("connected_at")}
    return {"connected": False}
