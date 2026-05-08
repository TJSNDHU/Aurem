"""
Website Edit Fulfillment Worker — P1 #7
=========================================
Processes customer_edit_requests queued by the tokens-spend flow.
- LLM generates the requested page/section HTML+CSS
- Creates a GitHub PR in the tenant's connected repo via github_deploy_service
- Notifies the customer via WhatsApp

Runs every 5 min as a background cron.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


PROMPT_TEMPLATES = {
    "new_page": (
        "You are AUREM's senior web developer. Generate a clean, modern HTML5 page "
        "for a {industry} business called {business_name} in {city}. "
        "Requested page: {memo}. Return only the page content between <body></body> tags, "
        "with inline minimal CSS matching a gold-on-dark aesthetic."
    ),
    "new_section": (
        "You are AUREM's senior web developer. Generate one self-contained HTML section "
        "(no full page) for {business_name}'s website. Section request: {memo}. "
        "Match existing brand tone (professional, modern). Include semantic HTML + inline style."
    ),
    "design_change": (
        "You are AUREM's senior web designer. Produce a CSS-only refresh for {business_name}'s "
        "existing site. Focus: {memo}. Keep layout intact; adjust colors, typography, spacing."
    ),
    "full_redesign": (
        "You are AUREM's senior web designer. Produce a full single-page redesign for "
        "{business_name} ({industry}, {city}). Brief: {memo}. Use modern CSS, responsive, "
        "fast-loading, accessible."
    ),
}


async def _generate_content(action: str, context: Dict) -> str:
    """Call Claude via emergentintegrations to generate the requested content."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            return ""
        prompt_template = PROMPT_TEMPLATES.get(action, PROMPT_TEMPLATES["new_section"])
        prompt = prompt_template.format(
            industry=context.get("industry", "business"),
            business_name=context.get("business_name", "the business"),
            city=context.get("city", ""),
            memo=context.get("memo", ""),
        )
        chat = LlmChat(api_key=key, session_id=f"edit-{context.get('email','')}-{datetime.now(timezone.utc).timestamp()}",
                       system_message="You generate production-ready HTML/CSS. Return code only, no commentary.")
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
        response = await chat.send_message(UserMessage(text=prompt))
        return response or ""
    except Exception as e:
        logger.error(f"[EDIT-WORKER] LLM generation failed: {e}")
        return ""


async def process_queue(limit: int = 5) -> Dict:
    """Pick up to N queued edit requests and fulfill them."""
    if _db is None:
        return {"processed": 0, "reason": "db_unset"}

    processed = 0
    failed = 0
    cursor = _db.customer_edit_requests.find({"status": "queued"}, {"_id": 0}).sort("created_at", 1).limit(limit)
    requests = [r async for r in cursor]

    for req in requests:
        email = req.get("email", "")
        action = req.get("action", "")
        memo = req.get("memo", "")
        if not email or not action:
            continue

        # Mark as processing
        await _db.customer_edit_requests.update_one(
            {"email": email, "action": action, "status": "queued", "created_at": req.get("created_at")},
            {"$set": {"status": "processing", "processing_at": datetime.now(timezone.utc).isoformat()}},
        )

        user = await _db.platform_users.find_one({"email": email}, {"_id": 0}) \
            or await _db.users.find_one({"email": email}, {"_id": 0})
        ws = await _db.aurem_workspaces.find_one({"owner_email": email}, {"_id": 0}) or {}

        context = {
            "email": email,
            "business_name": (user or {}).get("company_name") or ws.get("business_name") or "Your Business",
            "industry": ws.get("industry", ""),
            "city": ws.get("city", ""),
            "memo": memo,
        }

        content = await _generate_content(action, context)
        if not content:
            await _mark_failed(_db, req, "llm_empty")
            failed += 1
            continue

        # Store the generated artifact
        artifact_id = f"edit_{email}_{int(datetime.now(timezone.utc).timestamp())}"
        await _db.customer_edit_artifacts.insert_one({
            "artifact_id": artifact_id,
            "email": email,
            "action": action,
            "memo": memo,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Try to open a GitHub PR via existing service
        pr_result = None
        try:
            from services.github_deploy_service import push_fix
            tenant_id = (user or {}).get("id") or (user or {}).get("tenant_id") or email
            branch = f"aurem/edit-{action}-{int(datetime.now(timezone.utc).timestamp())}"
            file_name = f"aurem-edits/{action}_{artifact_id}.html"
            pr_result = await push_fix(
                tenant_id=tenant_id,
                branch_name=branch,
                files={file_name: content},
                title=f"AUREM: {action.replace('_',' ').title()} — {memo[:60]}",
                body=f"Customer-requested {action} via AUREM token spend.\n\nMemo: {memo}\n\nReview and merge to publish.",
            )
        except Exception as e:
            logger.warning(f"[EDIT-WORKER] PR creation skipped: {e}")

        # Mark complete
        await _db.customer_edit_requests.update_one(
            {"email": email, "action": action, "processing_at": {"$exists": True}, "created_at": req.get("created_at")},
            {"$set": {
                "status": "completed" if pr_result else "manual_review",
                "artifact_id": artifact_id,
                "pr_url": (pr_result or {}).get("pr_url"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        processed += 1

        # Notify customer
        try:
            phone = (user or {}).get("phone") or ""
            if phone:
                from routers.whatsapp_alerts import send_whatsapp
                msg = (f"✅ Your {action.replace('_',' ')} request is ready!"
                       + (f" PR: {pr_result.get('pr_url')}" if pr_result and pr_result.get('pr_url') else " Review it in /my/website."))
                await send_whatsapp(phone, msg)
        except Exception as e:
            logger.debug(f"[EDIT-WORKER] Notify failed: {e}")

    return {"processed": processed, "failed": failed, "queue_pending": max(0, limit - len(requests))}


async def _mark_failed(db, req: Dict, reason: str):
    await db.customer_edit_requests.update_one(
        {"email": req.get("email"), "action": req.get("action"), "created_at": req.get("created_at")},
        {"$set": {"status": "failed", "fail_reason": reason, "failed_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Refund tokens
    cost_map = {"new_page": 2, "new_section": 3, "design_change": 5, "full_redesign": 10}
    cost = cost_map.get(req.get("action", ""), 0)
    if cost > 0:
        await db.customer_token_wallets.update_one(
            {"email": req.get("email")},
            {"$inc": {"balance": cost}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        await db.customer_token_transactions.insert_one({
            "email": req.get("email"),
            "type": "refund",
            "amount": cost,
            "memo": f"Refund: {reason}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
