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
import uuid
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


async def connect_github(tenant_id: str, token: str, repo: Optional[str] = None) -> Dict:
    """Store customer GitHub token securely per tenant.

    Bug-fix #86 — the optional `repo` arg lets the tenant declare which
    repository AUREM is authorized to push to. push_fix() will reject any
    repo that doesn't match this declaration (or the list under
    `authorized_repos` for multi-repo tenants).
    """
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
    update: Dict = {
        "tenant_id": tenant_id,
        "token": token,
        "github_username": user_data.get("login", ""),
        "github_name": user_data.get("name", ""),
        "status": "connected",
        "connected_at": now,
        "updated_at": now,
    }
    if repo:
        update["authorized_repo"] = repo
    await db.github_connections.update_one(
        {"tenant_id": tenant_id},
        {"$set": update,
         "$addToSet": {"authorized_repos": repo} if repo else {}},
        upsert=True,
    )
    logger.info(f"[GitHub] Connected for tenant {tenant_id} as {user_data.get('login')}")
    return {"connected": True, "username": user_data.get("login"), "name": user_data.get("name")}


async def _is_repo_authorized(tenant_id: str, repo: str) -> bool:
    """Bug-fix #86 — verify `repo` is in the tenant's authorized list.
    Without this, an attacker with a valid JWT could connect their own
    low-privilege GitHub token and then call push_fix with repo set to a
    victim's repository — if the token has any collaborator access,
    AUREM would commit malicious CI YAML on the attacker's behalf.
    """
    db = _get_db()
    if db is None:
        return False
    doc = await db.github_connections.find_one(
        {"tenant_id": tenant_id, "status": "connected"},
        {"_id": 0, "authorized_repo": 1, "authorized_repos": 1},
    )
    if not doc:
        return False
    authorized = set()
    if doc.get("authorized_repo"):
        authorized.add(doc["authorized_repo"])
    for r in (doc.get("authorized_repos") or []):
        authorized.add(r)
    return repo in authorized


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

    # Bug-fix #86 — verify the requested repo is in the tenant's
    # authorized list before pushing. Without this an attacker with a
    # valid JWT could pass arbitrary `repo` and have AUREM commit
    # malicious code to any repository their token has access to.
    if not await _is_repo_authorized(tenant_id, repo):
        return {"success": False, "error": f"Repo {repo!r} not in tenant's authorized list. Re-connect GitHub with this repo."}

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


# ─────────────────────────────────────────────────────────────────
# iter 326j Gap 2 — Ship `.github/workflows/auto_deploy.yml` into
# the customer's repo on first GitHub connect. Without this the
# workflow file from iter 326i-2 doesn't exist in customer repos
# and the auto-fix product loop dies on the first merged PR.
# ─────────────────────────────────────────────────────────────────
# iter 326j Gap 2 — Ship `.github/workflows/auto_deploy.yml` into
# the customer's repo on first GitHub connect. Without this the
# workflow file from iter 326i-2 doesn't exist in customer repos
# and the auto-fix product loop dies on the first merged PR.
# ─────────────────────────────────────────────────────────────────
_AUREM_WORKFLOW_TEMPLATE_PATH = "/app/.github/workflows/auto_deploy.yml"
_AUREM_WORKFLOW_DEST_PATH     = ".github/workflows/aurem_auto_deploy.yml"


async def ship_auto_deploy_workflow(
    tenant_id: str,
    repo: str,
    base_branch: str = "main",
) -> Dict:
    """Idempotently install AUREM's customer-facing auto-deploy workflow
    into the customer repo.

    Behaviour:
      • If `.github/workflows/aurem_auto_deploy.yml` already exists on
        the base branch → no-op, return {already_installed: True}.
      • Otherwise → create branch `aurem/install-auto-deploy-<hex>`,
        commit the canonical template (read from /app/.github/workflows/
        auto_deploy.yml in this repo), open PR titled
        `[AUREM] Install auto-deploy workflow` with label `aurem-autofix`.

    Returns: {success, pr_url, pr_number} on success, {already_installed: True}
    when the workflow is already present, or {success: False, error} otherwise.
    """
    token = await _get_tenant_github_token(tenant_id)
    if not token:
        return {"success": False, "error": "No GitHub token. Connect GitHub first."}
    if not await _is_repo_authorized(tenant_id, repo):
        return {"success": False, "error": f"Repo {repo} not authorized for this tenant"}

    if not os.path.isfile(_AUREM_WORKFLOW_TEMPLATE_PATH):
        return {"success": False,
                "error": f"workflow template missing at {_AUREM_WORKFLOW_TEMPLATE_PATH}"}
    with open(_AUREM_WORKFLOW_TEMPLATE_PATH, encoding="utf-8") as f:
        workflow_yaml = f.read()

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Check if the destination file already exists on base_branch.
        check_url = (
            f"https://api.github.com/repos/{repo}/contents/"
            f"{_AUREM_WORKFLOW_DEST_PATH}?ref={base_branch}"
        )
        check_resp = await client.get(check_url, headers=headers)
        if check_resp.status_code == 200:
            # Already installed — record it idempotently and return.
            db = _get_db()
            if db is not None:
                await db.github_connections.update_one(
                    {"tenant_id": tenant_id},
                    {"$set": {
                        "auto_deploy_workflow_installed":     True,
                        "auto_deploy_workflow_installed_at":  datetime.now(timezone.utc).isoformat(),
                        "auto_deploy_workflow_repo":          repo,
                    }},
                )
            logger.info(f"[GitHub] auto-deploy workflow already present in {repo}")
            return {"success": True, "already_installed": True, "repo": repo}

        # 2. Use push_fix to create the branch + PR. Reuses existing flow.
        result = await push_fix(
            tenant_id=tenant_id,
            repo=repo,
            fix_title="Install auto-deploy workflow",
            fix_description=(
                "AUREM ships fixes to your repo as Pull Requests. "
                "This workflow validates each AUREM PR's CI before merge "
                "and triggers your production deploy after merge.\n\n"
                "Required repo secrets (Settings → Secrets → Actions):\n"
                "• AUREM_DEPLOY_HOOK_URL  — your deploy provider webhook\n"
                "• AUREM_API_KEY          — your AUREM API key\n"
                "• AUREM_DEPLOY_TARGET    — vercel | render | fly | hetzner | custom\n"
                "• AUREM_NOTIFY_EMAIL     — recipient for deploy notifications\n\n"
                "PR opened automatically by AUREM. Safe to merge — the workflow "
                "only fires on PRs labeled `aurem-autofix`."
            ),
            file_path=_AUREM_WORKFLOW_DEST_PATH,
            file_content=workflow_yaml,
            base_branch=base_branch,
        )

        if result.get("success"):
            db = _get_db()
            if db is not None:
                await db.github_connections.update_one(
                    {"tenant_id": tenant_id},
                    {"$set": {
                        "auto_deploy_workflow_install_pr":    result.get("pr_url"),
                        "auto_deploy_workflow_install_pr_at": datetime.now(timezone.utc).isoformat(),
                        "auto_deploy_workflow_repo":          repo,
                    }},
                )
        return result


# ─────────────────────────────────────────────────────────────────
# iter 326j Gap 2 — Receive deploy result from customer workflow.
# The workflow in iter 326i-2 POSTs here after `deploy` job completes.
# ─────────────────────────────────────────────────────────────────
async def record_customer_deploy_report(
    *,
    api_key:       str,
    commit:        str,
    status:        str,
    repo:          str,
    deployed_at:   str | None = None,
) -> Dict:
    """Persist a customer-side deploy outcome.

    Args:
      api_key  — Bearer token from workflow's `AUREM_API_KEY` secret
      commit   — sha that was deployed
      status   — 'success' | 'failure' | 'cancelled'
      repo     — owner/repo string

    Returns: {ok, deployment_id, tenant_id} or {ok: False, error}.

    Auth model: the customer sets `AUREM_API_KEY` in their repo secrets
    when they connect GitHub. We look up the tenant by api_key.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db not ready"}
    if not api_key or not commit or not repo:
        return {"ok": False, "error": "api_key, commit, repo required"}

    # Look up tenant by api_key. The api_key is stored alongside the
    # github_connection when the customer connects.
    conn = await db.github_connections.find_one(
        {"customer_api_key": api_key, "status": "connected"},
        {"_id": 0, "tenant_id": 1},
    )
    if not conn:
        # Soft-record so the customer's deploy isn't silently dropped —
        # founder can reconcile later. Mark `unauth=True`.
        await db.github_deployments.insert_one({
            "deployment_id":  uuid.uuid4().hex[:16],
            "tenant_id":      None,
            "repo":           repo,
            "commit":         commit,
            "status":         status,
            "deployed_at":    deployed_at or datetime.now(timezone.utc).isoformat(),
            "unauth":         True,
            "received_at":    datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": False, "error": "api_key not recognised", "soft_recorded": True}

    deployment_id = uuid.uuid4().hex[:16]
    doc = {
        "deployment_id":  deployment_id,
        "tenant_id":      conn["tenant_id"],
        "repo":           repo,
        "commit":         commit,
        "status":         status,
        "deployed_at":    deployed_at or datetime.now(timezone.utc).isoformat(),
        "received_at":    datetime.now(timezone.utc).isoformat(),
    }
    await db.github_deployments.insert_one(doc)
    logger.info(
        f"[GitHub] customer deploy report: tenant={conn['tenant_id']} "
        f"repo={repo} commit={commit[:7]} status={status}"
    )
    return {"ok": True, "deployment_id": deployment_id, "tenant_id": conn["tenant_id"]}

