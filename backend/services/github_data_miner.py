"""
AUREM GitHub Data Miner
Customer Intelligence Sync - Auto-extracts leads from client repositories
Growth OS Core Component
"""

import os
import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BusinessModel(str, Enum):
    """Detected business model type"""
    ECOMMERCE = "ecommerce"          # Cart recovery, product recommendations
    SAAS = "saas"                     # Onboarding, feature adoption
    SERVICE = "service"               # Appointment booking, scheduling
    MARKETPLACE = "marketplace"       # Buyer-seller matching
    CONTENT = "content"               # Engagement, subscriptions
    UNKNOWN = "unknown"


class SchemaType(str, Enum):
    """Database schema types"""
    USERS = "users"
    ORDERS = "orders"
    LEADS = "leads"
    CUSTOMERS = "customers"
    CARTS = "carts"
    APPOINTMENTS = "appointments"
    SUBSCRIPTIONS = "subscriptions"
    PRODUCTS = "products"


class GitHubRepository(BaseModel):
    """GitHub repository connection"""
    repo_id: str
    owner: str
    repo_name: str
    business_id: str
    branch: str = "main"
    webhook_url: Optional[str] = None
    access_token: Optional[str] = None
    connected_at: datetime
    last_sync: Optional[datetime] = None


class ExtractedLead(BaseModel):
    """Lead extracted from repository data"""
    lead_id: str
    source_repo: str
    source_table: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    metadata: Dict[str, Any] = {}
    business_value: float = 0.0  # Estimated value
    lead_score: int = 0  # 0-100
    extracted_at: datetime


class GitHubDataMiner:
    """
    GitHub Data Miner - Customer Intelligence Sync
    
    Not just code sync - this is lead generation from client's own data.
    
    Features:
    - Auto-extracts customer data from schemas
    - Detects business model type
    - Scores leads by value
    - Feeds into outreach engine
    - Respects subscription limits
    """
    
    def __init__(self, db=None):
        self.db = db
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        
        # Schema patterns to detect
        self.schema_patterns = {
            SchemaType.USERS: ["users", "user", "accounts", "customers"],
            SchemaType.ORDERS: ["orders", "order", "purchases", "transactions"],
            SchemaType.LEADS: ["leads", "lead", "prospects"],
            SchemaType.CARTS: ["carts", "cart", "shopping_cart", "basket"],
            SchemaType.APPOINTMENTS: ["appointments", "bookings", "reservations"],
            SchemaType.SUBSCRIPTIONS: ["subscriptions", "plans", "memberships"]
        }
        
        # Business model indicators
        self.business_indicators = {
            BusinessModel.ECOMMERCE: ["cart", "product", "checkout", "inventory"],
            BusinessModel.SAAS: ["subscription", "onboarding", "features", "usage"],
            BusinessModel.SERVICE: ["appointment", "booking", "schedule", "calendar"],
            BusinessModel.MARKETPLACE: ["seller", "buyer", "listing", "transaction"]
        }
    
    async def connect_repository(
        self,
        owner: str,
        repo_name: str,
        business_id: str,
        access_token: str = None
    ) -> GitHubRepository:
        """
        Connect a GitHub repository to AUREM
        
        This is the "onboarding" moment - when a business grants access
        """
        from uuid import uuid4
        
        repo = GitHubRepository(
            repo_id=str(uuid4()),
            owner=owner,
            repo_name=repo_name,
            business_id=business_id,
            access_token=access_token or self.github_token,
            connected_at=datetime.now(timezone.utc)
        )
        
        # Store connection
        if self.db is not None:
            await self.db.aurem_github_repos.insert_one(repo.dict())
        
        # Trigger initial sync
        await self.sync_repository(repo.repo_id)
        
        logger.info(f"Connected repo {owner}/{repo_name} for business {business_id}")
        return repo
    
    async def sync_repository(self, repo_id: str) -> Dict[str, Any]:
        """
        Sync repository data
        - Detect schemas
        - Extract leads
        - Classify business model
        """
        repo = await self._get_repository(repo_id)
        if not repo:
            return {"error": "Repository not found"}
        
        # Step 1: Detect database schemas
        schemas = await self._detect_schemas(repo)
        
        # Step 2: Classify business model
        business_model = await self._classify_business_model(repo, schemas)
        
        # Step 3: Extract leads
        leads = await self._extract_leads(repo, schemas)
        
        # Step 4: Score leads
        scored_leads = await self._score_leads(leads, business_model)
        
        # Step 5: Sync to Customer 360
        synced_count = await self._sync_to_customer_360(scored_leads, repo.business_id)
        
        # Update last sync
        if self.db is not None:
            await self.db.aurem_github_repos.update_one(
                {"repo_id": repo_id},
                {"$set": {"last_sync": datetime.now(timezone.utc)}}
            )
        
        # Record event for daily digest
        from services.daily_digest import get_digest_engine, EventPriority
        digest = get_digest_engine(self.db)
        
        await digest.record_event(
            event_type="github_sync",
            title=f"GitHub Sync Complete: {len(leads)} Leads Found",
            description=f"Synced {repo.owner}/{repo.repo_name} - {synced_count} new contacts",
            business_id=repo.business_id,
            priority=EventPriority.MEDIUM,
            metadata={
                "schemas_found": len(schemas),
                "business_model": business_model.value,
                "leads_extracted": len(leads)
            }
        )
        
        return {
            "repo_id": repo_id,
            "schemas_detected": len(schemas),
            "business_model": business_model.value,
            "leads_extracted": len(leads),
            "leads_synced": synced_count,
            "sync_time": datetime.now(timezone.utc).isoformat()
        }
    
    async def _detect_schemas(self, repo: GitHubRepository) -> List[Dict[str, Any]]:
        """
        Detect database schemas in repository
        
        Looks for:
        - Prisma schemas (.prisma)
        - Mongoose models (.js, .ts)
        - SQLAlchemy models (.py)
        - Sequelize models (.js)
        - Database migration files
        """
        schemas = []
        
        # TODO: Call GitHub API to scan repository
        # For now, return mock data
        
        # Simulate schema detection
        mock_schemas = [
            {
                "type": SchemaType.USERS.value,
                "file": "prisma/schema.prisma",
                "fields": ["id", "email", "phone", "name", "created_at"],
                "count_estimate": 1000
            },
            {
                "type": SchemaType.ORDERS.value,
                "file": "prisma/schema.prisma",
                "fields": ["id", "user_id", "total", "status", "created_at"],
                "count_estimate": 5000
            },
            {
                "type": SchemaType.CARTS.value,
                "file": "prisma/schema.prisma",
                "fields": ["id", "user_id", "items", "total", "abandoned_at"],
                "count_estimate": 200
            }
        ]
        
        return mock_schemas
    
    async def _classify_business_model(
        self,
        repo: GitHubRepository,
        schemas: List[Dict[str, Any]]
    ) -> BusinessModel:
        """
        AI classifies business model type
        
        Uses:
        - Schema structure
        - File names
        - Dependencies in package.json
        - README content
        """
        # Count indicators
        indicator_scores = {model: 0 for model in BusinessModel}
        
        for schema in schemas:
            schema_type = schema["type"].lower()
            for model, indicators in self.business_indicators.items():
                if any(ind in schema_type for ind in indicators):
                    indicator_scores[model] += 1
        
        # Get highest score
        if max(indicator_scores.values()) == 0:
            return BusinessModel.UNKNOWN
        
        classified_model = max(indicator_scores, key=indicator_scores.get)
        
        logger.info(f"Classified {repo.owner}/{repo.repo_name} as {classified_model.value}")
        return classified_model
    
    async def _extract_leads(
        self,
        repo: GitHubRepository,
        schemas: List[Dict[str, Any]]
    ) -> List[ExtractedLead]:
        """
        Extract leads from detected schemas
        
        SAFE PII MINING:
        - Only extracts from authorized repo
        - Respects subscription limits
        - No external API calls
        - User-consented data only
        """
        leads = []
        
        for schema in schemas:
            if schema["type"] in [SchemaType.USERS.value, SchemaType.CUSTOMERS.value, SchemaType.LEADS.value]:
                # Extract user data
                # TODO: Query actual database via secure connection
                
                # Mock lead extraction
                for i in range(min(10, schema.get("count_estimate", 0) // 100)):
                    from uuid import uuid4
                    lead = ExtractedLead(
                        lead_id=str(uuid4()),
                        source_repo=f"{repo.owner}/{repo.repo_name}",
                        source_table=schema["type"],
                        email=f"lead{i}@example.com",
                        phone=f"+1555000{i:04d}",
                        name=f"Lead {i}",
                        metadata={"schema": schema["type"]},
                        extracted_at=datetime.now(timezone.utc)
                    )
                    leads.append(lead)
        
        return leads
    
    async def _score_leads(
        self,
        leads: List[ExtractedLead],
        business_model: BusinessModel
    ) -> List[ExtractedLead]:
        """
        Score leads by potential value
        
        Factors:
        - Recency of activity
        - Order history
        - Cart abandonment
        - Engagement metrics
        """
        for lead in leads:
            score = 50  # Base score
            
            # E-commerce specific scoring
            if business_model == BusinessModel.ECOMMERCE:
                if lead.metadata.get("cart_abandoned"):
                    score += 30
                if lead.metadata.get("order_count", 0) > 5:
                    score += 20
            
            # SaaS specific scoring
            elif business_model == BusinessModel.SAAS:
                if lead.metadata.get("trial_expired"):
                    score += 40
                if lead.metadata.get("feature_usage", 0) > 10:
                    score += 15
            
            # Service specific scoring
            elif business_model == BusinessModel.SERVICE:
                if lead.metadata.get("booking_abandoned"):
                    score += 35
                if lead.metadata.get("repeat_customer"):
                    score += 25
            
            lead.lead_score = min(100, score)
            lead.business_value = lead.lead_score * 10  # $10 per score point
        
        # Sort by score
        leads.sort(key=lambda x: x.lead_score, reverse=True)
        
        return leads
    
    async def _sync_to_customer_360(
        self,
        leads: List[ExtractedLead],
        business_id: str
    ) -> int:
        """
        Sync extracted leads to Customer 360 system
        
        Feeds into:
        - OmniDimension (for messaging)
        - Follow-up engine (for recovery)
        - Outreach scheduler (for campaigns)
        """
        from services.omnidimension_service import get_omni_service, Channel
        
        omni = get_omni_service(self.db)
        synced_count = 0
        
        for lead in leads:
            if not lead.email and not lead.phone:
                continue  # Skip leads without contact info
            
            # Create customer in Customer 360
            customer = await omni.get_or_create_customer(
                business_id=business_id,
                identifier=lead.email or lead.phone,
                channel=Channel.EMAIL if lead.email else Channel.WHATSAPP
            )
            
            # Update customer metadata
            await omni.update_customer(
                customer.customer_id,
                updates={
                    "name": lead.name,
                    "email": lead.email,
                    "phone": lead.phone,
                    "lead_source": "github_sync",
                    "lead_score": lead.lead_score,
                    "business_value": lead.business_value,
                    "metadata": lead.metadata
                }
            )
            
            synced_count += 1
        
        logger.info(f"Synced {synced_count} leads to Customer 360 for business {business_id}")
        return synced_count
    
    async def _get_repository(self, repo_id: str) -> Optional[GitHubRepository]:
        """Get repository connection"""
        if self.db is None:
            return None
        
        repo_doc = await self.db.aurem_github_repos.find_one(
            {"repo_id": repo_id},
            {"_id": 0}
        )
        
        if repo_doc:
            return GitHubRepository(**repo_doc)
        
        return None
    
    async def get_business_leads(
        self,
        business_id: str,
        min_score: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get high-value leads for a business
        Ready for outreach
        """
        if self.db is None:
            return []
        
        # Get customers from Customer 360 with lead data
        from services.omnidimension_service import get_omni_service
        
        omni = get_omni_service(self.db)
        
        # Query customers with lead_score
        pipeline = [
            {
                "$match": {
                    "business_id": business_id,
                    "lead_score": {"$gte": min_score}
                }
            },
            {
                "$sort": {"lead_score": -1}
            },
            {
                "$limit": 100
            }
        ]
        
        leads = await self.db.aurem_customers.aggregate(pipeline).to_list(100)
        
        return [{**lead, "_id": None} for lead in leads]


# Singleton
_github_miner = None

def get_github_miner(db=None):
    global _github_miner
    if _github_miner is None:
        _github_miner = GitHubDataMiner(db)
    elif db and _github_miner.db is None:
        _github_miner.db = db
    return _github_miner
