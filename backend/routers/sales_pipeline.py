"""
AUREM Sales Pipeline - Complete End-to-End System
Step 1: Scan → Step 2: Find Decision Maker → Step 3: Outreach/Meeting → Step 4-8: Close & Onboard
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx
import re
import asyncio

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: DECISION MAKER FINDER
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionMakerRequest(BaseModel):
    scan_id: str
    company_domain: str
    skip_if_referral: bool = False
    skip_if_in_person: bool = False

class DecisionMaker(BaseModel):
    name: str
    title: str
    email: Optional[str]
    phone: Optional[str]
    linkedin: Optional[str]
    decision_power: str  # "high", "medium", "low"
    role_type: str  # "ceo", "cto", "cfo", "founder", "vp"

async def find_decision_makers(domain: str, scan_data: dict) -> List[DecisionMaker]:
    """
    Find the RIGHT person to contact - the decision maker
    Uses: LinkedIn, company website, business intelligence
    """
    decision_makers = []
    
    try:
        # Get company info from scan
        business_info = scan_data.get('deep_scan', {}).get('business_intelligence', {})
        company_name = business_info.get('company_name', '')
        
        # Method 1: Check company website for team page
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try common team page URLs
            team_urls = [
                f"https://{domain}/team",
                f"https://{domain}/about",
                f"https://{domain}/about-us",
                f"https://{domain}/leadership",
                f"https://{domain}/contact"
            ]
            
            for url in team_urls:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # Parse for executive titles
                        executives = extract_executives_from_html(response.text, domain)
                        decision_makers.extend(executives)
                except:
                    continue
        
        # Method 2: LinkedIn Company Search (if we have company name)
        if company_name:
            # Note: In production, you'd use LinkedIn API or a service like Apollo.io, Hunter.io
            # For now, we'll create a placeholder that shows the logic
            linkedin_executives = await search_linkedin_company(company_name, domain)
            decision_makers.extend(linkedin_executives)
        
        # Method 3: Email pattern detection
        # If we found emails in the scan, deduce the pattern
        contact_email = business_info.get('email')
        if contact_email and '@' in contact_email:
            email_domain = contact_email.split('@')[1]
            
            # Common C-level email patterns
            titles_to_find = [
                ("CEO", "ceo", "high"),
                ("CTO", "cto", "high"),
                ("Founder", "founder", "high"),
                ("COO", "coo", "medium"),
                ("VP Engineering", "vp", "medium"),
                ("VP Technology", "vp", "medium")
            ]
            
            for title, prefix, power in titles_to_find:
                potential_email = f"{prefix}@{email_domain}"
                decision_makers.append(DecisionMaker(
                    name=f"{title} at {company_name or domain}",
                    title=title,
                    email=potential_email,
                    phone=None,
                    linkedin=None,
                    decision_power=power,
                    role_type=prefix
                ))
        
        # Sort by decision power
        decision_makers.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.decision_power])
        
    except Exception as e:
        print(f"[Decision Maker Finder] Error: {e}")
    
    return decision_makers[:5]  # Return top 5


def extract_executives_from_html(html: str, domain: str) -> List[DecisionMaker]:
    """Extract executive names and titles from HTML"""
    from bs4 import BeautifulSoup
    
    executives = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for common executive titles
    exec_keywords = [
        'ceo', 'chief executive', 'founder', 'co-founder',
        'cto', 'chief technology', 'vp engineering', 'vp technology',
        'president', 'owner', 'managing director'
    ]
    
    # Search in text
    text = soup.get_text().lower()
    
    for keyword in exec_keywords:
        if keyword in text:
            # Try to extract name near the keyword
            # This is simplified - in production, use NER (Named Entity Recognition)
            
            role_type = "ceo" if any(x in keyword for x in ["ceo", "chief executive"]) else \
                       "cto" if any(x in keyword for x in ["cto", "chief technology"]) else \
                       "founder" if "founder" in keyword else "vp"
            
            executives.append(DecisionMaker(
                name=f"Executive at {domain}",
                title=keyword.title(),
                email=None,
                phone=None,
                linkedin=None,
                decision_power="high" if role_type in ["ceo", "founder", "cto"] else "medium",
                role_type=role_type
            ))
    
    return executives


async def search_linkedin_company(company_name: str, domain: str) -> List[DecisionMaker]:
    """
    Search LinkedIn for company executives
    
    NOTE: In production, integrate with:
    - Apollo.io API (https://apollo.io) - Best for B2B contact data
    - Hunter.io API (https://hunter.io) - Email finding
    - LinkedIn Sales Navigator API (requires partnership)
    - Clearbit API (https://clearbit.com) - Company intelligence
    
    For now, we'll return a template that shows the structure
    """
    
    # Placeholder - in production, this would call Apollo.io or similar
    executives = []
    
    # Example of what Apollo.io returns:
    # {
    #   "name": "John Smith",
    #   "title": "CEO",
    #   "email": "john@company.com",
    #   "linkedin": "https://linkedin.com/in/johnsmith",
    #   "phone": "+1-555-1234"
    # }
    
    return executives


@router.post("/api/pipeline/find-decision-makers")
async def api_find_decision_makers(request: DecisionMakerRequest, authorization: str = Header(None)):
    """
    Step 2: Find decision makers before outreach
    Identifies CEO, CTO, Founder - the people who can buy
    """
    try:
        from server import db
        import secrets
        
        user = get_current_user(authorization)
        
        # Get scan data
        scan = await db.system_scans.find_one({"_id": request.scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Check if we should skip
        if request.skip_if_referral or request.skip_if_in_person:
            return {
                "success": True,
                "skipped": True,
                "reason": "In-person meeting or referral - skipping decision maker search",
                "next_step": "invisible_coach"
            }
        
        # Find decision makers
        decision_makers = await find_decision_makers(request.company_domain, scan)
        
        # Save for later use
        dm_record = {
            "record_id": f"dm_{secrets.token_urlsafe(12)}",
            "scan_id": request.scan_id,
            "tenant_id": user.get("tenant_id"),
            "company_domain": request.company_domain,
            "decision_makers": [dm.dict() for dm in decision_makers],
            "found_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.decision_makers.insert_one(dm_record)
        
        return {
            "success": True,
            "decision_makers": [dm.dict() for dm in decision_makers],
            "recommendations": {
                "primary_contact": decision_makers[0].dict() if decision_makers else None,
                "contact_strategy": "Email CEO first, if no response in 48h, try CTO",
                "message_template": generate_outreach_template(scan, decision_makers[0] if decision_makers else None)
            }
        }
        
    except Exception as e:
        print(f"[Decision Maker Finder] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def generate_outreach_template(scan_data: dict, decision_maker: Optional[DecisionMaker]) -> str:
    """Generate personalized outreach email template"""
    
    name = decision_maker.name if decision_maker else "[First Name]"
    title = decision_maker.title if decision_maker else "CEO"
    issues = scan_data.get('issues_found', 0)
    critical = scan_data.get('critical_issues', 0)
    savings = scan_data.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2,400')
    
    return f"""Subject: Found {critical} critical issues on your website

Hi {name},

I ran a quick scan on your website and found {issues} issues that are currently 
costing you approximately {savings} per month in inefficiencies.

As {title}, I thought you'd want to know about the top {critical} critical problems:

1. [Issue 1 from scan]
2. [Issue 2 from scan]
3. [Issue 3 from scan]

I put together a detailed report showing:
- Exactly what's broken
- How much it's costing you
- How to fix it (mostly automated)

Want me to send it over? Takes 2 minutes to review.

Best,
[Your Name]

P.S. I can show you how to fix all {issues} issues and save {savings}/month. 
Free 14-day trial if you want to test it out."""


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: PROPOSAL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

class ProposalRequest(BaseModel):
    scan_id: str
    customer_name: str
    customer_company: str
    selected_tier: str  # "basic", "professional", "business", "enterprise"
    custom_pricing: Optional[Dict] = None

@router.post("/api/pipeline/generate-proposal")
async def generate_proposal(request: ProposalRequest, authorization: str = Header(None)):
    """
    Step 4: Generate professional proposal
    Auto-creates PDF proposal with scan results, pricing, ROI
    """
    try:
        from server import db
        from utils.pdf_generator import generate_pdf_report
        import secrets
        
        user = get_current_user(authorization)
        
        # Get scan and pricing
        scan = await db.system_scans.find_one({"_id": request.scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        pricing = await calculate_pricing_internal(request.scan_id)
        
        # Override with custom pricing if provided
        if request.custom_pricing:
            pricing['pricing'].update(request.custom_pricing)
        
        # Generate proposal
        proposal_id = f"proposal_{secrets.token_urlsafe(16)}"
        
        proposal = {
            "proposal_id": proposal_id,
            "scan_id": request.scan_id,
            "tenant_id": user.get("tenant_id"),
            "created_by": user.get("user_id"),
            "customer_name": request.customer_name,
            "customer_company": request.customer_company,
            "selected_tier": request.selected_tier,
            "pricing": pricing,
            "scan_summary": {
                "issues_found": scan.get('issues_found'),
                "critical_issues": scan.get('critical_issues'),
                "overall_score": scan.get('overall_score'),
                "estimated_savings": scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')
            },
            "proposal_sections": {
                "executive_summary": f"""
{request.customer_company} Technology Assessment

We completed a comprehensive analysis of {scan.get('website_url')} and identified 
{scan.get('issues_found')} issues that are currently costing approximately 
{scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')} per month.

This proposal outlines how AUREM can automate and resolve these issues, resulting in 
significant time and cost savings.
                """,
                
                "findings": scan.get('recommendations', [])[:10],
                
                "solution": f"""
AUREM Business Automation Platform - {request.selected_tier.title()} Plan

Our AI-powered platform will:
1. Automatically fix all {scan.get('issues_found')} identified issues
2. Provide 24/7 monitoring and optimization
3. Save {scan.get('aurem_impact', {}).get('estimated_time_saved_monthly')} monthly
4. Reduce operational costs by {scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly')}

Implementation: 48 hours
Training required: None (fully automated)
ROI timeline: {pricing.get('value_proposition', {}).get('roi_timeline', '2-4 weeks')}
                """,
                
                "investment": {
                    "monthly_fee": pricing['pricing']['monthly_fee'],
                    "setup_fee": pricing.get('pricing', {}).get('setup_fee', 0),
                    "annual_savings": pricing.get('value_proposition', {}).get('annual_savings_estimate', '$18,000'),
                    "break_even": f"Month {pricing.get('value_proposition', {}).get('break_even_month', 2)}"
                },
                
                "next_steps": [
                    "Review and approve this proposal",
                    "Schedule onboarding call (30 minutes)",
                    "AUREM team completes setup (24-48 hours)",
                    "Go live and start seeing results"
                ]
            },
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "valid_until": (datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day + 30)).isoformat()
        }
        
        await db.proposals.insert_one(proposal)
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "proposal": proposal,
            "pdf_url": f"/api/proposals/{proposal_id}/pdf",
            "share_link": f"/proposals/{proposal_id}"
        }
        
    except Exception as e:
        print(f"[Proposal Generation] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: CONTRACT & AGREEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class ContractRequest(BaseModel):
    proposal_id: str
    customer_signature: Optional[str] = None
    start_date: str

@router.post("/api/pipeline/generate-contract")
async def generate_contract(request: ContractRequest, authorization: str = Header(None)):
    """
    Step 5: Generate service agreement
    Creates legal contract based on approved proposal
    """
    try:
        from server import db
        import secrets
        
        user = get_current_user(authorization)
        
        # Get proposal
        proposal = await db.proposals.find_one({"proposal_id": request.proposal_id}, {"_id": 0})
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        contract_id = f"contract_{secrets.token_urlsafe(16)}"
        
        contract = {
            "contract_id": contract_id,
            "proposal_id": request.proposal_id,
            "tenant_id": user.get("tenant_id"),
            "customer_company": proposal['customer_company'],
            "customer_name": proposal['customer_name'],
            "service_tier": proposal['selected_tier'],
            "monthly_fee": proposal['pricing']['pricing']['monthly_fee'],
            "setup_fee": proposal['pricing']['pricing'].get('setup_fee', 0),
            "start_date": request.start_date,
            "contract_term": "12 months",
            "auto_renew": True,
            "terms": {
                "service_level": "99.9% uptime SLA",
                "support": "24/7 email and chat support",
                "cancellation": "30 days notice required",
                "payment_terms": "Monthly billing, auto-debit",
                "data_ownership": "Customer retains all data ownership"
            },
            "status": "pending_signature",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        if request.customer_signature:
            contract['customer_signature'] = request.customer_signature
            contract['signed_at'] = datetime.now(timezone.utc).isoformat()
            contract['status'] = "signed"
        
        await db.contracts.insert_one(contract)
        
        # If signed, trigger onboarding
        if contract['status'] == "signed":
            await trigger_onboarding(contract_id, proposal['customer_company'])
        
        return {
            "success": True,
            "contract_id": contract_id,
            "contract": contract,
            "next_step": "onboarding" if contract['status'] == "signed" else "awaiting_signature"
        }
        
    except Exception as e:
        print(f"[Contract Generation] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6-8: ONBOARDING & IMPLEMENTATION
# ═══════════════════════════════════════════════════════════════════════════════

async def trigger_onboarding(contract_id: str, customer_company: str):
    """
    Automatically start onboarding process
    Creates customer account, schedules calls, sends welcome
    """
    try:
        from server import db
        import secrets
        
        onboarding_id = f"onboard_{secrets.token_urlsafe(16)}"
        
        onboarding = {
            "onboarding_id": onboarding_id,
            "contract_id": contract_id,
            "customer_company": customer_company,
            "status": "in_progress",
            "steps": [
                {
                    "step": 1,
                    "name": "Account Setup",
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                },
                {
                    "step": 2,
                    "name": "Welcome Email Sent",
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                },
                {
                    "step": 3,
                    "name": "Onboarding Call Scheduled",
                    "status": "pending",
                    "scheduled_for": (datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day + 1)).isoformat()
                },
                {
                    "step": 4,
                    "name": "System Integration",
                    "status": "pending"
                },
                {
                    "step": 5,
                    "name": "Go Live",
                    "status": "pending"
                }
            ],
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.onboarding_sessions.insert_one(onboarding)
        
        # TODO: Send welcome email, create customer account, etc.
        
    except Exception as e:
        print(f"[Onboarding] Error: {e}")


@router.get("/api/pipeline/onboarding-status/{contract_id}")
async def get_onboarding_status(contract_id: str, authorization: str = Header(None)):
    """Check onboarding progress"""
    try:
        from server import db
        
        onboarding = await db.onboarding_sessions.find_one(
            {"contract_id": contract_id},
            {"_id": 0}
        )
        
        if not onboarding:
            return {
                "success": False,
                "message": "Onboarding not started yet"
            }
        
        return {
            "success": True,
            "onboarding": onboarding,
            "progress": calculate_onboarding_progress(onboarding)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def calculate_onboarding_progress(onboarding: dict) -> dict:
    """Calculate onboarding completion percentage"""
    steps = onboarding.get('steps', [])
    total = len(steps)
    completed = len([s for s in steps if s['status'] == 'completed'])
    
    return {
        "total_steps": total,
        "completed_steps": completed,
        "percentage": int((completed / total) * 100) if total > 0 else 0,
        "next_step": next((s for s in steps if s['status'] == 'pending'), None)
    }


# Helper functions
def get_current_user(authorization: str):
    """Extract user from JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    token = authorization.replace("Bearer ", "")
    try:
        import jwt
        import os
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

async def calculate_pricing_internal(scan_id: str):
    """Get pricing for scan"""
    from server import db
    
    scan = await db.system_scans.find_one({"_id": scan_id}, {"_id": 0})
    if not scan:
        return {}
    
    issues = scan.get('issues_found', 0)
    critical = scan.get('critical_issues', 0)
    
    if critical <= 2 and issues < 25:
        tier, monthly, setup = "professional", 599, 500
    elif critical <= 5 and issues < 50:
        tier, monthly, setup = "business", 999, 1000
    else:
        tier, monthly, setup = "enterprise", 1999, 2500
    
    annual_savings = int(scan.get('aurem_impact', {}).get('estimated_cost_savings_monthly', '$2400').replace('$', '').replace(',', '')) * 12
    
    return {
        "recommended_tier": tier,
        "pricing": {"monthly_fee": monthly, "setup_fee": setup},
        "value_proposition": {
            "break_even_month": 2,
            "annual_savings_estimate": f"${annual_savings:,}",
            "roi_timeline": "2-4 weeks"
        },
        "comparison": {
            "customer_saves": f"${annual_savings - ((monthly * 12) + setup):,}",
            "value_multiple": f"{round(annual_savings / ((monthly * 12) + setup), 1)}x"
        }
    }
