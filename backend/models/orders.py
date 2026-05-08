"""
Order Models for the orders module.
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid


class CartItem(BaseModel):
    product_id: str
    quantity: int = 1


class Cart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    session_id: str
    items: List[Dict] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShippingAddress(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    province: str
    postal_code: str
    country: str = "Canada"


class OrderCreate(BaseModel):
    shipping_address: ShippingAddress
    payment_method: str
    session_id: str
    shipping_method: Optional[str] = "standard"
    discount_code: Optional[str] = None
    discount_codes: Optional[List[str]] = None
    discount_percent: Optional[float] = 0
    points_to_redeem: Optional[int] = 0
    redemption_token: Optional[str] = None


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    product_image: str
    quantity: int
    price: float
    is_preorder: bool = False


class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_number: str
    user_id: Optional[str] = None
    items: List[OrderItem]
    shipping_address: ShippingAddress
    subtotal: float
    discount_code: Optional[str] = None
    discount_percent: float = 0.0
    discount_amount: float = 0.0
    points_discount: float = 0.0
    points_redeemed: int = 0
    shipping: float = 0.0
    shipping_cost_paid: float = 0.0
    tax: float = 0.0
    duty: float = 0.0
    landed_cost: float = 0.0
    total: float
    status: str = "pending"
    payment_method: str
    payment_details: Dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    tracking_number: Optional[str] = None
    courier: Optional[str] = None
    shipped_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    refund_status: Optional[str] = None
    refund_amount: Optional[float] = None
    is_gift: bool = False
    gift_message: Optional[str] = None
    gift_recipient_email: Optional[str] = None
    points_awarded: bool = False
    points_pending: bool = False
    tags: List[str] = []
