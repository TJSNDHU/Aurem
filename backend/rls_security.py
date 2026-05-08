"""
RLS Security Module for AUREM Platform
Row-Level Security implementation for multi-brand architecture
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# BRAND DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class BrandID(str, Enum):
    """Brand identifiers for RLS"""
    REROOTS = "reroots"
    OROE = "oroe"
    LAVELA = "lavela"
    AUREM = "aurem"  # Platform itself


class AdminRole(str, Enum):
    """Admin role levels"""
    SUPER_ADMIN = "super_admin"
    BRAND_ADMIN = "brand_admin"
    SUPPORT = "support"
    VIEWER = "viewer"


# ═══════════════════════════════════════════════════════════════════════════════
# BRAND CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

BRAND_CONFIGS: Dict[str, Dict[str, Any]] = {
    "reroots": {
        "name": "ReRoots Biotech Skincare",
        "primary_color": "#F8A5B8",
        "secondary_color": "#D4AF37",
        "collections": ["products", "orders", "customers", "reviews"],
    },
    "oroe": {
        "name": "OROÉ Premium",
        "primary_color": "#C2185B",
        "secondary_color": "#FFD700",
        "collections": ["oroe_products", "oroe_orders"],
    },
    "lavela": {
        "name": "La Vela Bianca",
        "primary_color": "#0D4D4D",
        "secondary_color": "#D4AF37",
        "collections": ["lavela_products", "lavela_orders"],
    },
    "aurem": {
        "name": "AUREM Platform",
        "primary_color": "#6366F1",
        "secondary_color": "#F59E0B",
        "collections": [],
    },
}


# Collections that require brand-level RLS filtering
RLS_PROTECTED_COLLECTIONS = [
    "products",
    "orders",
    "customers",
    "reviews",
    "bio_scans",
    "marketing_broadcasts",
    "chat_sessions",
    "aurem_missions",
    "aurem_prospects",
    "aurem_outreach",
]


def get_brand_config(brand_id: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific brand"""
    return BRAND_CONFIGS.get(brand_id)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN USER MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class AdminUser(BaseModel):
    """Admin user model for RLS"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str = ""
    role: AdminRole = AdminRole.VIEWER
    brand_ids: List[str] = []  # Brands this admin can access
    permissions: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    is_active: bool = True

    def can_access_brand(self, brand_id: str) -> bool:
        """Check if admin can access a specific brand"""
        if self.role == AdminRole.SUPER_ADMIN:
            return True
        return brand_id in self.brand_ids

    def has_permission(self, permission: str) -> bool:
        """Check if admin has a specific permission"""
        if self.role == AdminRole.SUPER_ADMIN:
            return True
        return permission in self.permissions


# ═══════════════════════════════════════════════════════════════════════════════
# RLS CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

class RLSContext:
    """
    Row-Level Security context for request handling.
    Carries admin user info and brand context for query filtering.
    """
    
    def __init__(
        self,
        admin_user: Optional[AdminUser] = None,
        brand_id: Optional[str] = None
    ):
        self.admin_user = admin_user
        self.brand_id = brand_id or "reroots"  # Default to reroots

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.admin_user is not None

    def is_super_admin(self) -> bool:
        """Check if user is super admin"""
        return (
            self.admin_user is not None 
            and self.admin_user.role == AdminRole.SUPER_ADMIN
        )

    def can_access_brand(self, brand_id: str) -> bool:
        """Check if context allows accessing a brand"""
        if not self.admin_user:
            return False
        return self.admin_user.can_access_brand(brand_id)

    def get_query_filter(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Get MongoDB query filter for RLS.
        Super admins get no filter; others filter by brand_id.
        """
        # Super admin bypasses RLS
        if self.is_super_admin():
            return {}
        
        # Collections that don't need brand filtering
        if collection_name and collection_name not in RLS_PROTECTED_COLLECTIONS:
            return {}
        
        # Apply brand filter
        if self.brand_id:
            return {"brand_id": self.brand_id}
        
        return {}

    def get_allowed_brands(self) -> List[str]:
        """Get list of brands this context can access"""
        if not self.admin_user:
            return []
        if self.is_super_admin():
            return list(BRAND_CONFIGS.keys())
        return self.admin_user.brand_ids


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE MIGRATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def migrate_add_brand_id(db, collection_name: str, default_brand: str = "reroots"):
    """
    Migration helper: Add brand_id to existing documents that don't have it.
    """
    try:
        result = await db[collection_name].update_many(
            {"brand_id": {"$exists": False}},
            {"$set": {"brand_id": default_brand}}
        )
        if result.modified_count > 0:
            logger.info(f"[RLS Migration] Added brand_id to {result.modified_count} documents in {collection_name}")
        return result.modified_count
    except Exception as e:
        logger.error(f"[RLS Migration] Error migrating {collection_name}: {e}")
        return 0


async def create_indexes_for_rls(db):
    """
    Create indexes for RLS-protected collections to optimize filtered queries.
    """
    for collection_name in RLS_PROTECTED_COLLECTIONS:
        try:
            await db[collection_name].create_index("brand_id")
            logger.info(f"[RLS] Created brand_id index on {collection_name}")
        except Exception as e:
            logger.debug(f"[RLS] Index may already exist for {collection_name}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def add_brand_to_document(doc: Dict[str, Any], brand_id: str) -> Dict[str, Any]:
    """Add brand_id to a document before insert"""
    enhanced = doc.copy()
    enhanced["brand_id"] = brand_id
    return enhanced


def validate_brand_access(rls: RLSContext, required_brand: str) -> bool:
    """Validate that RLS context has access to required brand"""
    if not rls.is_authenticated():
        return False
    return rls.can_access_brand(required_brand)
