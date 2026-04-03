"""
AUREM Growth Engine API Routes
GitHub Listener + Lead Mining + Automated Outreach
"""

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/growth", tags=["Growth Engine"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectRepoRequest(BaseModel):
    owner: str
    repo_name: str
    business_id: str
    access_token: Optional[str] = None


class CreateCampaignRequest(BaseModel):
    name: str
    business_id: str
    outreach_type: str  # cart_recovery, onboarding, etc.
    channels: List[str]  # whatsapp, email, voice
    message_template: str
    target_lead_score: int = 50


# ═══════════════════════════════════════════════════════════════════════════════
# GITHUB ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/github/connect")
async def connect_github_repo(
    request: ConnectRepoRequest,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user)
):
    """
    Connect GitHub repository
    
    This triggers:
    1. Schema detection
    2. Lead extraction
    3. Business model classification
    4. Customer 360 sync
    """
    from services.github_data_miner import get_github_miner
    
    miner = get_github_miner(db)
    
    repo = await miner.connect_repository(
        owner=request.owner,
        repo_name=request.repo_name,
        business_id=request.business_id,
        access_token=request.access_token
    )
    
    return {
        "success": True,
        "repo_id": repo.repo_id,
        "message": "Repository connected. Syncing data in background...",
        "repo": repo.dict()
    }


@router.post("/github/sync/{repo_id}")
async def sync_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user)
):
    """Manually trigger repository sync"""
    from services.github_data_miner import get_github_miner
    
    miner = get_github_miner(db)
    
    # Run sync in background
    background_tasks.add_task(miner.sync_repository, repo_id)
    
    return {
        "success": True,
        "message": "Sync started in background",
        "repo_id": repo_id
    }


@router.get("/github/repos")
async def list_connected_repos(user = Depends(get_current_user)):
    """List all connected repositories"""
    if db is None:
        return {"repos": []}
    
    repos = await db.aurem_github_repos.find(
        {},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "count": len(repos),
        "repos": repos
    }


@router.get("/leads/{business_id}")
async def get_business_leads(
    business_id: str,
    min_score: int = 50,
    user = Depends(get_current_user)
):
    """
    Get high-value leads for a business
    
    Extracted from GitHub data mine
    """
    from services.github_data_miner import get_github_miner
    
    miner = get_github_miner(db)
    leads = await miner.get_business_leads(business_id, min_score)
    
    return {
        "business_id": business_id,
        "min_score": min_score,
        "count": len(leads),
        "leads": leads[:50]  # Top 50
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OUTREACH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/outreach/campaign/create")
async def create_campaign(
    request: CreateCampaignRequest,
    user = Depends(get_current_user)
):
    """Create automated outreach campaign"""
    from services.outreach_scheduler import get_outreach_scheduler, OutreachType, OutreachChannel
    
    scheduler = get_outreach_scheduler(db)
    
    try:
        outreach_type = OutreachType(request.outreach_type)
        channels = [OutreachChannel(ch) for ch in request.channels]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e}")
    
    campaign = await scheduler.create_campaign(
        business_id=request.business_id,
        name=request.name,
        outreach_type=outreach_type,
        channels=channels,
        message_template=request.message_template,
        target_lead_score=request.target_lead_score
    )
    
    return {
        "success": True,
        "campaign": campaign.dict()
    }


@router.post("/outreach/campaign/{campaign_id}/run")
async def run_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user)
):
    """
    Execute outreach campaign
    
    Sends personalized messages to high-score leads
    via WhatsApp, Email, or Voice
    """
    from services.outreach_scheduler import get_outreach_scheduler
    
    scheduler = get_outreach_scheduler(db)
    
    # Run in background
    background_tasks.add_task(scheduler.run_campaign, campaign_id)
    
    return {
        "success": True,
        "message": "Campaign execution started",
        "campaign_id": campaign_id
    }


@router.get("/outreach/campaigns")
async def list_campaigns(
    business_id: str = None,
    user = Depends(get_current_user)
):
    """List all outreach campaigns"""
    if db is None:
        return {"campaigns": []}
    
    query = {}
    if business_id:
        query["business_id"] = business_id
    
    campaigns = await db.aurem_outreach_campaigns.find(
        query,
        {"_id": 0}
    ).to_list(100)
    
    return {
        "count": len(campaigns),
        "campaigns": campaigns
    }


@router.get("/outreach/stats/{business_id}")
async def get_outreach_stats(
    business_id: str,
    days: int = 30,
    user = Depends(get_current_user)
):
    """Get outreach performance statistics"""
    from datetime import datetime, timezone, timedelta
    
    if db is None:
        return {"error": "Database not available"}
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Aggregate campaign stats
    pipeline = [
        {
            "$match": {
                "business_id": business_id,
                "created_at": {"$gte": start_date}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_campaigns": {"$sum": 1},
                "total_leads_targeted": {"$sum": "$leads_targeted"},
                "total_leads_contacted": {"$sum": "$leads_contacted"},
                "avg_conversion_rate": {"$avg": "$conversion_rate"}
            }
        }
    ]
    
    results = await db.aurem_outreach_campaigns.aggregate(pipeline).to_list(1)
    
    if results:
        stats = results[0]
        stats.pop("_id", None)
    else:
        stats = {
            "total_campaigns": 0,
            "total_leads_targeted": 0,
            "total_leads_contacted": 0,
            "avg_conversion_rate": 0.0
        }
    
    return {
        "business_id": business_id,
        "period_days": days,
        "stats": stats
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/github/webhook")
async def github_webhook(payload: Dict[str, Any]):
    """
    GitHub webhook handler
    
    Triggered on:
    - Push events (code changes)
    - Pull request merges
    - Schema changes
    """
    event_type = payload.get("action", "unknown")
    repo = payload.get("repository", {})
    
    logger.info(f"GitHub webhook: {event_type} on {repo.get('full_name')}")
    
    # TODO: Trigger sync on relevant events
    
    return {"received": True}


print("[STARTUP] Growth Engine Routes loaded (GitHub + Outreach)")
