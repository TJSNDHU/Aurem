"""
Custom Subscription Models
For A-la-carte / Build-Your-Own subscription plans
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class CustomSubscriptionRequest(BaseModel):
    """Request to create a custom subscription"""
    user_id: str
    selected_services: List[str]  # List of service_ids: ["gpt-4o", "voxtral-tts", etc.]
    billing_cycle: str = "monthly"  # "monthly" or "annual"
    custom_limits: Optional[Dict[str, int]] = None  # Optional: {"ai_tokens": 100000}
    

class CustomSubscriptionPricing(BaseModel):
    """Pricing breakdown for custom subscription"""
    base_fee: float = Field(default=0.0, description="Base platform fee")
    service_fees: Dict[str, float] = Field(default_factory=dict, description="Per-service fees")
    total_monthly: float = Field(description="Total monthly cost")
    total_annual: float = Field(description="Total annual cost (with discount)")
    annual_savings: float = Field(default=0.0, description="Savings if paying annually")
    selected_services: List[str] = Field(description="List of selected service IDs")
    

class CustomSubscriptionPlan(BaseModel):
    """Complete custom subscription plan"""
    plan_id: str
    user_id: str
    plan_type: str = "custom"
    selected_services: List[str]
    pricing: CustomSubscriptionPricing
    billing_cycle: str
    status: str = "active"
    created_at: datetime
    current_period_end: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
