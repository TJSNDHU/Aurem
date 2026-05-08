"""
Service Catalog Models — AUREM Hybrid Storefront (Option C)
============================================================
Pydantic models for the 16-service catalog + 3 CRM tiers + trial subsystem.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ServiceCatalogItem(BaseModel):
    """One sellable service in the AUREM catalog."""
    service_id: str                               # e.g. "website_repair"
    name: str
    cluster: str                                  # repair | security | crm | marketing | power
    description: str
    cost_monthly: float                           # our delivery cost
    price_monthly: float                          # retail price (tax-inclusive)
    currency: str = "cad"
    billing_type: str = "recurring"               # recurring | one_time
    margin_pct: float = 0.0                       # calculated
    status: str = "live"                          # live | beta | disabled
    backend_service: Optional[str] = None         # python file name for delivery
    dependencies: List[str] = Field(default_factory=list)  # primitive service_ids
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    cluster_order: int = 0
    # For CRM tiers only — volume caps
    limits: Optional[Dict[str, int]] = None       # {calls, sms, emails}
    # For one-off services (Genetic Repair)
    unit_label: Optional[str] = None              # "per repair" | "per month"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BundleRule(BaseModel):
    """Auto-discount rule when N+ services active."""
    min_services: int
    discount_pct: float
    label: str


class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cost_monthly: Optional[float] = None
    price_monthly: Optional[float] = None
    status: Optional[str] = None
    limits: Optional[Dict[str, int]] = None


class CustomerSubscription(BaseModel):
    """One active add-on subscription per customer."""
    sub_id: str
    tenant_bin: str
    email: str
    service_id: str
    service_name: str
    price_monthly: float
    status: str = "active"                        # active | cancelled | paused
    started_at: str
    ends_at: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    # Usage tracking for CRM tiers
    usage: Optional[Dict[str, int]] = None


class TrialSession(BaseModel):
    """7-day Power Trial state machine per customer."""
    tenant_bin: str
    email: str
    started_at: str
    ends_at: str
    days_remaining: int = 7
    state: str = "active"                         # active | expired | downgraded
    # Trial unlocks
    scanner_used: int = 0
    scanner_quota: int = 1
    friend_scans_used: int = 0
    friend_scans_quota: int = 5
    ora_msgs_used: int = 0
    ora_msgs_quota: int = 50
    free_reel_generated: bool = False
    # Downgrade target
    downgrades_to: str = "forever_free"


class FriendScanRequest(BaseModel):
    friend_website: str
    friend_email: Optional[str] = None
    friend_name: Optional[str] = None
    share_via: Optional[str] = None               # whatsapp | email | copy


class HardcodedReport(BaseModel):
    """Locked report shown to trial users until they subscribe."""
    report_id: str
    tenant_bin: str
    website: str
    score: int
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    locked: bool = True
    generated_at: str
    unlock_required_service: str = "website_repair"
