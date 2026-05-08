"""
AUREM Platform — Pydantic Models
Extracted from server.py during modularization.
80 models covering: Users, Products, Orders, Payments, Roles,
Currencies, Payroll, Site Content, Store Settings, Influencer/Referral,
Rewards/Loyalty, Chat, Typography, Subscriptions.
"""

import uuid
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


# ============= MODELS =============


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str


class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TokenResponse(BaseModel):
    token: str
    user: dict


class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None


class ProductBase(BaseModel):
    name: str
    slug: str
    description: str
    short_description: Optional[str] = None
    price: float
    cost_price: Optional[float] = None  # Your actual cost for the product (COGS)
    compare_price: Optional[float] = None
    discount_percent: Optional[float] = None  # Individual product discount percentage
    category_id: str
    images: List[str] = []
    ingredients: Optional[str] = None
    how_to_use: Optional[str] = None
    stock: int = 100
    is_featured: bool = False
    is_active: bool = True
    # Pre-order settings
    allow_preorder: bool = False
    preorder_message: Optional[str] = "Available for pre-order. Ships in 2-3 weeks."
    preorder_release_date: Optional[str] = None
    # Shipping weight
    weight_grams: int = 200  # Default weight in grams
    # INCI Ingredients (International Nomenclature Cosmetic Ingredient)
    inci_ingredients: Optional[str] = (
        None  # e.g., "Aqua/Water/Eau, Glycerin, Niacinamide, Sodium Hyaluronate..."
    )
    ingredients_common: Optional[str] = (
        None  # Common names: "Water, Glycerin, Vitamin B3..."
    )
    hs_code: Optional[str] = (
        "3304.99"  # Harmonized System code for customs (3304.99 = Beauty/Skincare)
    )
    country_of_origin: str = "Canada"
    # SEO & Google Merchant Fields
    gtin: Optional[str] = None  # Global Trade Item Number (UPC, EAN, ISBN)
    mpn: Optional[str] = None  # Manufacturer Part Number
    brand: str = "ReRoots"
    seo_title: Optional[str] = None  # Custom SEO title
    seo_description: Optional[str] = None  # Custom meta description
    google_product_category: Optional[str] = (
        "Health & Beauty > Skin Care"  # Google taxonomy
    )
    condition: str = "new"  # new, used, refurbished
    age_group: Optional[str] = "adult"  # adult, kids, toddler, infant, newborn
    gender: Optional[str] = "unisex"  # male, female, unisex


class Product(ProductBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    average_rating: float = 0.0
    review_count: int = 0


class CartItem(BaseModel):
    product_id: str
    quantity: int = 1
    combo_id: Optional[str] = None  # Track if item is part of a combo
    combo_price: Optional[float] = None  # Discounted price for combo items


class ComboCartRequest(BaseModel):
    combo_id: str
    quantity: int = 1


class Cart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    session_id: str
    items: List[Dict] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewCreate(BaseModel):
    product_id: str
    rating: int = Field(ge=1, le=5)
    title: str
    comment: str
    images: List[str] = []  # Customer uploaded images


class Review(ReviewCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_approved: bool = False
    # Google Business Review fields
    google_status: str = "not_selected"  # not_selected, approved, request_sent, posted
    google_approved_at: Optional[str] = None
    google_approved_by: Optional[str] = None
    google_request_sent_at: Optional[str] = None
    google_posted_at: Optional[str] = None
    google_notes: Optional[str] = None


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
    payment_method: str  # 'stripe' or 'paypal'
    session_id: str
    shipping_method: Optional[str] = "standard"
    discount_code: Optional[str] = None
    discount_codes: Optional[List[str]] = None  # Support multiple codes for stacking
    discount_percent: Optional[float] = 0
    points_to_redeem: Optional[int] = 0  # Loyalty points to apply
    redemption_token: Optional[str] = None  # Token from points redemption
    whatsapp_opted_in: Optional[bool] = False  # WhatsApp updates opt-in
    storefront: Optional[str] = "reroots"  # 'reroots' or 'dark_store'


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
    points_discount: float = 0.0  # Discount from loyalty points redemption
    points_redeemed: int = 0  # Number of points used
    shipping: float = 0.0
    shipping_cost_paid: float = 0.0  # Actual shipping cost you paid to courier
    tax: float = 0.0  # Tax calculated on ORIGINAL price (before discounts)
    duty: float = 0.0  # Import duty for international orders
    landed_cost: float = 0.0  # Total landed cost (subtotal + tax + duty + shipping)
    total: float
    cost_of_goods: float = 0.0  # Total cost price of products in this order
    payment_method: str
    payment_status: str = "pending"
    order_status: str = "pending"
    stripe_session_id: Optional[str] = None
    has_preorder_items: bool = False
    receipt_sent: bool = False
    receipt_sent_at: Optional[str] = None
    shipping_method: str = "standard"
    total_weight_grams: int = 0
    # International shipping fields
    is_international: bool = False
    destination_country: str = "Canada"
    currency_code: str = "CAD"
    # FlagShip Shipping fields
    tracking_number: Optional[str] = None
    shipping_carrier: Optional[str] = None  # FlagShip courier name
    shipping_label_url: Optional[str] = None
    shipment_id: Optional[str] = None  # FlagShip shipment ID
    shipping_cost_paid: float = 0.0  # Actual cost paid via FlagShip
    tracking_status: str = "pending"  # pending, shipped, in_transit, delivered
    shipped_at: Optional[str] = None
    delivered_at: Optional[str] = None
    storefront: str = "reroots"  # 'reroots' or 'dark_store' - which store the order came from
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# COURIER_COMPANIES removed - Now using FlagShip API for all shipping


class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    session_id: str
    amount: float
    currency: str = "cad"
    payment_method: str
    payment_status: str = "pending"
    metadata: Dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= ROLE-BASED ACCESS CONTROL MODELS =============

# Default permissions structure for all features
DEFAULT_PERMISSIONS = {
    "overview": {"view": True, "create": False, "edit": False, "delete": False},
    "products": {"view": False, "create": False, "edit": False, "delete": False},
    "categories": {"view": False, "create": False, "edit": False, "delete": False},
    "orders": {"view": False, "create": False, "edit": False, "delete": False},
    "financials": {"view": False, "create": False, "edit": False, "delete": False},
    "payroll": {"view": False, "create": False, "edit": False, "delete": False},
    "customers": {"view": False, "create": False, "edit": False, "delete": False},
    "offers": {"view": False, "create": False, "edit": False, "delete": False},
    "reviews": {"view": False, "create": False, "edit": False, "delete": False},
    "sections": {"view": False, "create": False, "edit": False, "delete": False},
    "website": {"view": False, "create": False, "edit": False, "delete": False},
    "ads": {"view": False, "create": False, "edit": False, "delete": False},
    "typography": {"view": False, "create": False, "edit": False, "delete": False},
    "subscriptions": {"view": False, "create": False, "edit": False, "delete": False},
    "settings": {"view": False, "create": False, "edit": False, "delete": False},
    "ai_chat": {"view": False, "create": False, "edit": False, "delete": False},
    "team": {"view": False, "create": False, "edit": False, "delete": False},
}

# Accountant role - only view financials and orders
ACCOUNTANT_PERMISSIONS = {
    "overview": {"view": True, "create": False, "edit": False, "delete": False},
    "products": {"view": False, "create": False, "edit": False, "delete": False},
    "categories": {"view": False, "create": False, "edit": False, "delete": False},
    "orders": {"view": True, "create": False, "edit": False, "delete": False},
    "financials": {"view": True, "create": False, "edit": False, "delete": False},
    "payroll": {"view": True, "create": False, "edit": False, "delete": False},
    "customers": {"view": False, "create": False, "edit": False, "delete": False},
    "offers": {"view": False, "create": False, "edit": False, "delete": False},
    "reviews": {"view": False, "create": False, "edit": False, "delete": False},
    "sections": {"view": False, "create": False, "edit": False, "delete": False},
    "website": {"view": False, "create": False, "edit": False, "delete": False},
    "ads": {"view": False, "create": False, "edit": False, "delete": False},
    "typography": {"view": False, "create": False, "edit": False, "delete": False},
    "subscriptions": {"view": False, "create": False, "edit": False, "delete": False},
    "settings": {"view": False, "create": False, "edit": False, "delete": False},
    "ai_chat": {"view": False, "create": False, "edit": False, "delete": False},
    "team": {"view": False, "create": False, "edit": False, "delete": False},
}

# Super admin has all permissions
SUPER_ADMIN_PERMISSIONS = {
    k: {"view": True, "create": True, "edit": True, "delete": True}
    for k in DEFAULT_PERMISSIONS.keys()
}


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    permissions: Dict[str, Dict[str, bool]] = Field(
        default_factory=lambda: DEFAULT_PERMISSIONS.copy()
    )


class Role(RoleCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""  # Admin user ID who created this role
    is_active: bool = True


class TeamMemberCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role_id: str
    password: Optional[str] = None  # Optional password for direct creation


# Business Expense Categories
EXPENSE_CATEGORIES = [
    "Inventory/Products",
    "Shipping/Courier",
    "Marketing/Advertising",
    "Software/Subscriptions",
    "Office Supplies",
    "Equipment",
    "Professional Services",
    "Rent/Utilities",
    "Travel",
    "Packaging",
    "Bank Fees",
    "Insurance",
    "Taxes/Licenses",
    "Other",
]


class ExpenseCreate(BaseModel):
    category: str
    description: str
    amount: float
    date: str  # YYYY-MM-DD format
    vendor: Optional[str] = ""
    receipt_url: Optional[str] = None
    notes: Optional[str] = ""
    is_recurring: bool = False
    recurring_frequency: Optional[str] = None  # monthly, weekly, yearly


class Expense(ExpenseCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    password: Optional[str] = None  # Optional - can be set via invite link


class TeamMemberInvite(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role_id: str
    send_email: bool = True  # If true, send invitation email


class TeamMember(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    first_name: str
    last_name: str
    password_hash: str = ""
    role_id: str
    invited_by: str = ""  # Admin user ID who invited
    status: str = "pending"  # pending, active, disabled
    invite_token: Optional[str] = None
    invite_expires: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[str] = None
    is_team_member: bool = True  # To distinguish from regular users


class ShippingRate(BaseModel):
    method: str
    name: str
    description: str
    price: float
    estimated_days: str


class ShippingCalculatorRequest(BaseModel):
    weight_grams: int
    province: str
    postal_code: str


class CheckoutRequest(BaseModel):
    order_id: str
    origin_url: str


# ============= AD CAMPAIGN MODELS =============

AD_PLATFORMS = [
    {"id": "facebook", "name": "Facebook", "icon": "facebook", "color": "#1877F2"},
    {"id": "instagram", "name": "Instagram", "icon": "instagram", "color": "#E4405F"},
    {"id": "google", "name": "Google Ads", "icon": "google", "color": "#4285F4"},
    {"id": "tiktok", "name": "TikTok", "icon": "tiktok", "color": "#000000"},
    {"id": "youtube", "name": "YouTube", "icon": "youtube", "color": "#FF0000"},
    {"id": "twitter", "name": "Twitter/X", "icon": "twitter", "color": "#1DA1F2"},
    {"id": "linkedin", "name": "LinkedIn", "icon": "linkedin", "color": "#0A66C2"},
    {"id": "pinterest", "name": "Pinterest", "icon": "pinterest", "color": "#E60023"},
    {"id": "snapchat", "name": "Snapchat", "icon": "snapchat", "color": "#FFFC00"},
    {"id": "other", "name": "Other", "icon": "globe", "color": "#6B7280"},
]


class AdCampaignCreate(BaseModel):
    name: str
    platform: str  # facebook, instagram, google, tiktok, youtube, twitter, linkedin, pinterest, other
    objective: str = "awareness"  # awareness, traffic, engagement, leads, sales
    budget: float = 0.0
    budget_type: str = "daily"  # daily, lifetime
    currency: str = "CAD"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_audience: Optional[str] = None
    ad_creative_url: Optional[str] = None  # Link to ad creative/image
    landing_page_url: Optional[str] = None
    notes: Optional[str] = None


class AdCampaign(AdCampaignCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "draft"  # draft, active, paused, completed, cancelled
    # Performance metrics (manually entered)
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    # Calculated metrics
    ctr: float = 0.0  # Click-through rate
    cpc: float = 0.0  # Cost per click
    cpa: float = 0.0  # Cost per acquisition
    roas: float = 0.0  # Return on ad spend
    revenue: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    last_updated: Optional[str] = None


# ============= MULTI-CURRENCY MODELS =============

# Supported currencies with their details
SUPPORTED_CURRENCIES = {
    "CAD": {"name": "Canadian Dollar", "symbol": "$", "flag": "🇨🇦", "locale": "en-CA"},
    "USD": {"name": "US Dollar", "symbol": "$", "flag": "🇺🇸", "locale": "en-US"},
    "GBP": {"name": "British Pound", "symbol": "£", "flag": "🇬🇧", "locale": "en-GB"},
    "EUR": {"name": "Euro", "symbol": "€", "flag": "🇪🇺", "locale": "en-EU"},
    "AUD": {
        "name": "Australian Dollar",
        "symbol": "$",
        "flag": "🇦🇺",
        "locale": "en-AU",
    },
    "INR": {"name": "Indian Rupee", "symbol": "₹", "flag": "🇮🇳", "locale": "en-IN"},
}

# Country to currency mapping for auto-detection
COUNTRY_TO_CURRENCY = {
    "CA": "CAD",
    "US": "USD",
    "GB": "GBP",
    "UK": "GBP",
    "AU": "AUD",
    "IN": "INR",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "AT": "EUR",
    "IE": "EUR",
    "PT": "EUR",
    "FI": "EUR",
}

# Cache for exchange rates (refresh every hour)
exchange_rate_cache = {"rates": {}, "last_updated": None}


class CurrencyRates(BaseModel):
    base: str = "CAD"
    rates: Dict[str, float] = {}
    last_updated: Optional[str] = None


class WishlistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    product_id: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BackInStockAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    email: str
    notified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GiftWrapOption(BaseModel):
    enabled: bool = False
    message: Optional[str] = None
    price: float = 5.99  # Gift wrap price


# ============= PAYROLL MODELS =============


class Employee(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "Staff"
    hourly_rate: float = 0.0
    salary: Optional[float] = None  # If salaried employee
    employment_type: str = "hourly"  # "hourly" or "salary"
    tax_rate: float = 15.0  # Default tax percentage
    start_date: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PayrollEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    employee_name: str
    pay_period_start: str  # ISO date string
    pay_period_end: str  # ISO date string
    hours_worked: float = 0.0
    hourly_rate: float = 0.0
    gross_pay: float = 0.0
    tax_deduction: float = 0.0
    other_deductions: float = 0.0
    deduction_notes: Optional[str] = None
    net_pay: float = 0.0
    pay_type: str = "weekly"  # "weekly", "biweekly", "monthly"
    status: str = "pending"  # "pending", "paid", "cancelled"
    paid_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None


# ============= SITE CONTENT MODELS =============


class HeroSection(BaseModel):
    badge_text: str = "BIOTECH SKINCARE"
    title_line1: str = "Science Meets"
    title_line2: str = "Nature"
    description: str = (
        "Advanced formulas featuring PDRN, peptides, and botanical extracts. Scientifically formulated ingredients for visible results."
    )
    primary_button_text: str = "Shop Collection"
    primary_button_link: str = "/products"
    secondary_button_text: str = "Our Science"
    secondary_button_link: str = "/about"
    hero_image: str = (
        "https://images.unsplash.com/photo-1677735476292-0fc57ab097b2?w=800"
    )


class FeatureItem(BaseModel):
    icon: str = "Beaker"
    title: str = ""
    description: str = ""


class TestimonialItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    review: str = ""
    rating: int = 5


# Callback Request Model
class CallbackRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    phone: str
    email: Optional[str] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None
    status: str = "pending"  # pending, contacted, completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class ScienceSection(BaseModel):
    badge_text: str = "OUR SCIENCE"
    title_line1: str = "PDRN Technology"
    title_line2: str = "Cellular Vitality"
    description: str = (
        "Our flagship ingredient PDRN (Polydeoxyribonucleotide) is derived from salmon DNA and has been scientifically formulated to support skin vitality and renewal at the cellular level."
    )
    benefits: List[str] = [
        "Supports collagen production",
        "Helps reduce the appearance of redness",
        "Promotes a revitalized complexion",
        "Improves skin texture & tone",
    ]
    image: str = "https://images.unsplash.com/photo-1714844437236-de8ef1a7286f?w=800"
    button_text: str = "Learn More"
    button_link: str = "/about"


class NewsletterSection(BaseModel):
    title: str = "Join the ReRoots Community"
    description: str = (
        "Get exclusive access to new products, skincare tips, and special offers."
    )
    button_text: str = "Subscribe"


class FooterContent(BaseModel):
    brand_description: str = (
        "Biotech skincare rooted in science. We combine cutting-edge ingredients like PDRN with natural extracts for visible results."
    )
    instagram_url: str = "https://instagram.com/reroots.ca"
    facebook_url: str = "https://facebook.com"
    support_email: str = "support@reroots.ca"


class SiteContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "site_content"
    hero: HeroSection = Field(default_factory=HeroSection)
    features: List[FeatureItem] = Field(
        default_factory=lambda: [
            FeatureItem(
                icon="Beaker",
                title="Lab Tested",
                description="Dermatologist-tested formulas",
            ),
            FeatureItem(
                icon="Leaf", title="Clean Beauty", description="No harmful ingredients"
            ),
            FeatureItem(
                icon="Sparkles", title="Visible Results", description="In 4-6 weeks"
            ),
            FeatureItem(
                icon="Shield",
                title="Dermatologist",
                description="Approved & recommended",
            ),
        ]
    )
    testimonials: List[TestimonialItem] = Field(
        default_factory=lambda: [
            TestimonialItem(
                name="Sarah M.",
                review="The AURA-GEN serum has completely transformed my skin. The dark spots I've had for years are finally fading!",
                rating=5,
            ),
            TestimonialItem(
                name="Jessica L.",
                review="I was skeptical about PDRN but after 6 weeks of use, my skin has never looked better. Worth every penny.",
                rating=5,
            ),
            TestimonialItem(
                name="Michelle K.",
                review="Finally, a skincare brand that backs up their claims with real science. My esthetician noticed the difference!",
                rating=5,
            ),
        ]
    )
    science: ScienceSection = Field(default_factory=ScienceSection)
    newsletter: NewsletterSection = Field(default_factory=NewsletterSection)
    footer: FooterContent = Field(default_factory=FooterContent)
    featured_products_title: str = "Featured Products"
    featured_products_badge: str = "BESTSELLERS"
    # Store Policies - persisted to database
    shipping_policy: str = ""
    return_policy: str = ""
    privacy_policy: str = ""
    terms_of_service: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Global Shipping & Returns Policy Content
class ShippingPolicyContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "shipping_policy"
    # Hero Section
    hero_title: str = "Global Shipping & Returns"
    hero_subtitle: str = (
        "We ship worldwide from Canada with full customs support and transparent pricing"
    )

    # Shipping Times Section
    shipping_intro: str = (
        "ReRoots ships premium skincare products from our facility in Canada to customers worldwide. All orders are carefully packaged to ensure your products arrive in perfect condition."
    )

    # Regional Shipping Times
    shipping_times: List[Dict] = Field(
        default_factory=lambda: [
            {
                "region": "Canada",
                "standard": "3-5 business days",
                "express": "1-2 business days",
                "cost_note": "Free standard shipping over $75 CAD",
            },
            {
                "region": "United States",
                "standard": "5-10 business days",
                "express": "3-5 business days",
                "cost_note": "Starting from $15 CAD",
            },
            {
                "region": "United Kingdom",
                "standard": "10-15 business days",
                "express": "5-7 business days",
                "cost_note": "Starting from £20 GBP",
            },
            {
                "region": "European Union",
                "standard": "10-15 business days",
                "express": "5-7 business days",
                "cost_note": "Starting from €22 EUR",
            },
            {
                "region": "Australia & NZ",
                "standard": "12-18 business days",
                "express": "6-8 business days",
                "cost_note": "Starting from $30 AUD",
            },
            {
                "region": "Asia Pacific",
                "standard": "12-20 business days",
                "express": "5-8 business days",
                "cost_note": "Starting from $28 CAD",
            },
            {
                "region": "Rest of World",
                "standard": "15-30 business days",
                "express": "7-12 business days",
                "cost_note": "Starting from $40 CAD",
            },
        ]
    )

    # Customs & Duties Section
    customs_title: str = "Customs, Duties & Taxes"
    customs_content: str = """When shipping internationally, your order may be subject to import duties, taxes, and customs fees. These charges are determined by your country's customs authority and are the responsibility of the recipient.

**What's Included at Checkout:**
- Product cost
- Estimated import duty (for applicable countries)
- Estimated VAT/GST/Sales tax
- International shipping fee

**Landed Cost Calculator:**
Our checkout displays the estimated "Landed Cost" - the total amount including all estimated duties and taxes. This ensures no surprise fees upon delivery.

**De Minimis Thresholds:**
Many countries offer duty-free import below certain values. Our system automatically applies these thresholds where applicable."""

    # Returns Policy Section
    returns_title: str = "Returns & Refunds Policy"
    returns_intro: str = (
        "Due to the personal care nature of skincare products and hygiene regulations, we have specific return policies:"
    )

    returns_policy: List[Dict] = Field(
        default_factory=lambda: [
            {
                "title": "Unopened Products",
                "policy": "Unopened, sealed products may be returned within 30 days of delivery for a full refund. Products must be in original packaging and condition.",
                "icon": "Package",
            },
            {
                "title": "Opened Products",
                "policy": "For hygiene and safety reasons, opened skincare products cannot be returned or exchanged. This policy is in compliance with health regulations in Canada and internationally.",
                "icon": "ShieldX",
            },
            {
                "title": "Damaged or Defective Items",
                "policy": "If your product arrives damaged or defective, please contact us within 48 hours of delivery with photos. We will arrange a replacement or full refund.",
                "icon": "AlertTriangle",
            },
            {
                "title": "Wrong Item Received",
                "policy": "If you received the wrong item, contact us immediately. We will send the correct item and provide a prepaid return label for the incorrect item.",
                "icon": "RefreshCw",
            },
        ]
    )

    # International Returns
    intl_returns_title: str = "International Returns"
    intl_returns_content: str = """For international orders:

- **Return Shipping:** The customer is responsible for return shipping costs to our Canadian facility.
- **Customs Fees:** Any duties or taxes paid on the original order are non-refundable as these are collected by your country's government.
- **Refund Processing:** Refunds will be processed within 5-7 business days of receiving the returned item.
- **Currency:** Refunds are issued in the original currency of purchase."""

    # Contact Section
    contact_title: str = "Need Help?"
    contact_content: str = (
        "Our customer service team is available to assist with any shipping or returns questions."
    )
    contact_email: str = "support@reroots.ca"
    contact_phone: str = "+1 (226) 501-7777"
    contact_hours: str = "Monday - Friday: 9AM - 6PM EST"

    # INCI Information Section
    inci_title: str = "International Ingredient Compliance"
    inci_content: str = """All ReRoots products are labeled with INCI (International Nomenclature Cosmetic Ingredient) names to comply with global cosmetic regulations.

**What is INCI?**
INCI is a standardized international naming system for cosmetic ingredients, recognized by regulatory bodies worldwide including Health Canada, the FDA (USA), and EU Cosmetics Regulation.

**Reading Our Labels:**
- Ingredients are listed in descending order of concentration
- INCI names appear alongside common names for clarity
- Example: "Aqua/Water/Eau" = Water

**Allergen Information:**
Please review the full ingredient list before purchase if you have known sensitivities. All potential allergens are clearly listed on our product pages."""

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= STORE SETTINGS MODEL =============


class BankAccountSettings(BaseModel):
    enabled: bool = True
    bank_name: str = ""
    account_holder_name: str = ""
    account_number: str = ""
    routing_number: str = ""
    swift_code: str = ""
    instructions: str = "Please include your order number in the transfer reference."


class DirectCardSettings(BaseModel):
    enabled: bool = True
    card_processor_name: str = ""  # e.g., "Square", "Interac", etc.
    instructions: str = "Contact us for card payment processing."


# Paytm Settings (India)
class PaytmSettings(BaseModel):
    enabled: bool = False
    merchant_id: str = ""
    merchant_key: str = ""
    website: str = "WEBSTAGING"  # WEBSTAGING for test, DEFAULT for production
    industry_type: str = "Retail"
    channel_id: str = "WEB"
    instructions: str = (
        "Pay securely via Paytm. You will be redirected to Paytm payment page."
    )


# UPI Settings (India)
class UPISettings(BaseModel):
    enabled: bool = False
    upi_id: str = ""  # e.g., "business@paytm" or "business@upi"
    merchant_name: str = ""
    instructions: str = (
        "Scan QR code or use UPI ID to pay. Include order number in remarks."
    )


# PayPal Settings
class PayPalSettings(BaseModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    mode: str = "sandbox"  # sandbox or live
    instructions: str = "Pay securely with PayPal. You will be redirected to PayPal."


# Credit/Debit Card Settings
class CardPaymentSettings(BaseModel):
    enabled: bool = False
    processor: str = "manual"  # manual, stripe, square, etc.
    stripe_public_key: str = ""
    stripe_secret_key: str = ""
    instructions: str = "We accept Visa, Mastercard, and American Express."


class PaymentSettings(BaseModel):
    # Bambora/TD Bank Card Payments
    bambora_enabled: bool = True
    # Direct Bank Transfer
    bank_transfer_enabled: bool = True
    bank_account: BankAccountSettings = Field(default_factory=BankAccountSettings)
    # Direct Card Payment (Legacy)
    direct_card_enabled: bool = True
    direct_card: DirectCardSettings = Field(default_factory=DirectCardSettings)
    # E-Transfer (Canada)
    etransfer_enabled: bool = True
    etransfer_email: str = "admin@reroots.ca"
    etransfer_phone: str = ""
    etransfer_instructions: str = (
        "Send e-Transfer to our email. Include order number in message."
    )
    # PayPal Manual Payment
    paypal_manual_enabled: bool = False
    paypal_email: str = "admin@reroots.ca"
    paypal_link_url: str = ""  # PayPal.me or NCP payment link for direct redirect
    paypal_instructions: str = "Send as 'Friends & Family' to avoid fees. Include order number."
    # Paytm (India)
    paytm: PaytmSettings = Field(default_factory=PaytmSettings)
    # UPI (India)
    upi: UPISettings = Field(default_factory=UPISettings)
    # PayPal (Global)
    paypal: PayPalSettings = Field(default_factory=PayPalSettings)
    # Credit/Debit Card
    card_payment: CardPaymentSettings = Field(default_factory=CardPaymentSettings)
    # General Settings
    currency: str = "CAD"
    supported_currencies: List[str] = Field(
        default_factory=lambda: ["CAD", "USD", "EUR", "GBP", "INR", "AUD"]
    )
    tax_rate: float = 13.0
    free_shipping_threshold: float = 75.0
    shipping_cost: float = 10.0
    # Legacy (for backward compatibility)
    stripe_enabled: bool = False
    stripe_public_key: str = ""
    stripe_secret_key: str = ""
    paypal_enabled: bool = False
    paypal_client_id: str = ""
    paypal_secret: str = ""


# PayPal Price-Based Links Model
class PayPalLink(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amount: float  # The price/amount this link is for
    link_url: str  # The PayPal NCP or PayPal.me link
    label: str = ""  # Optional label like "Standard Product", "Premium Bundle"
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PayPalLinkCreate(BaseModel):
    amount: float
    link_url: str
    label: str = ""
    is_active: bool = True


class LiveChatSettings(BaseModel):
    enabled: bool = True
    chat_mode: str = "ai_first"  # ai_first, manual, or hybrid
    ai_model: str = "gpt-4o"  # AI model for auto-responses
    ai_enabled: bool = True  # Enable AI auto-responses
    notification_email: str = "admin@reroots.ca"  # Where to send chat notifications
    welcome_message: str = "Hi! Welcome to ReRoots. How can we help you today?"
    ai_greeting: str = (
        "Hello! I'm your ReRoots assistant. I can help you with product questions, orders, and more. How can I assist you?"
    )
    business_hours: str = "Mon-Fri 9AM-6PM EST"
    offline_message: str = (
        "Thanks for reaching out! We'll get back to you as soon as possible."
    )
    escalation_keywords: List[str] = Field(
        default_factory=lambda: ["human", "agent", "speak to someone", "real person"]
    )


class GoogleBusinessSettings(BaseModel):
    enabled: bool = True
    business_name: str = "ReRoots"
    place_id: str = ""
    review_url: str = ""
    maps_url: str = ""


class NotificationSettings(BaseModel):
    order_email_enabled: bool = True
    admin_email: str = "admin@reroots.ca"
    sms_notifications: bool = False
    notification_phone: str = "+12265017777"


# Language/Localization Settings
class LanguageSettings(BaseModel):
    default_language: str = "en"
    supported_languages: List[str] = Field(
        default_factory=lambda: ["en", "fr", "hi", "es", "zh", "ar", "pt"]
    )
    auto_detect: bool = True  # Auto-detect user's browser language


# ============= INFLUENCER & AFFILIATE MARKETING SETTINGS =============


class InfluencerProgramSettings(BaseModel):
    """Admin-configurable influencer program settings"""

    enabled: bool = True
    program_name: str = "ReRoots Partner Program"

    # Commission Settings (what influencers earn)
    commission_type: str = "percentage"  # percentage, flat, tiered
    commission_rate: float = 10.0  # Default 10% of founder's price
    commission_flat_amount: float = 10.0  # $10 per sale if flat
    tiered_rates: List[Dict] = Field(
        default_factory=lambda: [
            {"min_sales": 0, "max_sales": 50, "rate": 10.0},
            {"min_sales": 51, "max_sales": 100, "rate": 15.0},
            {"min_sales": 101, "max_sales": 999999, "rate": 20.0},
        ]
    )

    # Customer Discount Settings (what customers get)
    customer_discount_type: str = (
        "percentage"  # percentage, fixed_amount, free_shipping
    )
    customer_discount_value: float = 20.0  # 20% off or $20 off
    customer_discount_label: str = "Partner Exclusive"

    # Anti-Stacking Protection
    allow_coupon_stacking: bool = True  # Enable stacking - allows multiple discounts
    stacking_message: str = (
        "Partner discount already applied. Additional coupons cannot be combined."
    )

    # Minimum Requirements
    min_followers: int = 1000
    min_engagement_rate: float = 2.0  # 2%
    accepted_platforms: List[str] = Field(
        default_factory=lambda: ["instagram", "tiktok", "youtube", "twitter", "blog"]
    )

    # Payout Settings
    min_payout_threshold: float = 50.0  # Minimum $50 to request payout
    payout_methods: List[str] = Field(
        default_factory=lambda: ["paypal", "bank_transfer", "etransfer"]
    )
    payout_frequency: str = "monthly"  # weekly, biweekly, monthly

    # Landing Page Customization
    landing_page_headline: str = "Exclusive Partner Access"
    landing_page_subheadline: str = (
        "Get {discount} off with {influencer_name}'s special link"
    )
    landing_page_cta: str = "Shop Now & Save"
    show_influencer_photo: bool = True
    show_discount_banner: bool = True


class ReferralProgramSettings(BaseModel):
    """Admin-configurable refer-a-friend settings"""

    enabled: bool = True
    program_name: str = "Share the Glow"

    # Referrer Rewards (person who refers)
    referrer_reward_type: str = (
        "fixed_amount"  # percentage, fixed_amount, free_product, points
    )
    referrer_reward_value: float = 10.0  # $10 credit
    referrer_reward_label: str = "$10 Store Credit"

    # Referee Rewards (new customer)
    referee_reward_type: str = "fixed_amount"
    referee_reward_value: float = 10.0  # $10 off first order
    referee_reward_label: str = "$10 Off Your First Order"

    # Milestone Rewards (refer X friends)
    milestone_enabled: bool = True
    milestones: List[Dict] = Field(
        default_factory=lambda: [
            {"referrals": 5, "reward": "Free Sample Kit", "reward_value": 25.0},
            {
                "referrals": 10,
                "reward": "50% Off Discount Code",
                "reward_value": 50.0,
                "reward_type": "percentage",
            },
            {
                "referrals": 25,
                "reward": "VIP Lifetime Discount (25% off)",
                "reward_value": 0.0,
            },
        ]
    )

    # Widget Customization
    widget_enabled: bool = True
    widget_position: str = (
        "bottom-right"  # bottom-right, bottom-left, side-right, side-left
    )
    widget_button_text: str = "Get ReRoots FREE"
    widget_button_color: str = "#D4AF37"  # Gold color
    widget_popup_title: str = "Share the Glow ✨"
    widget_popup_subtitle: str = "Invite friends & earn rewards"
    widget_share_message: str = (
        "I love ReRoots skincare! Use my link for $10 off your first order:"
    )

    # Limits
    max_referrals_per_month: int = 50
    referral_expiry_days: int = 30  # How long referee has to use the referral


# Quiz Program Settings
class QuizProgramSettings(BaseModel):
    """Admin-configurable quiz program settings"""

    enabled: bool = True
    quiz_name: str = "Skin Health Quiz"
    completion_reward_type: str = "discount"  # discount, points, none
    completion_reward_value: float = 10.0
    show_product_recommendations: bool = True
    collect_email: bool = True
    collect_phone: bool = False


# Bio-Age Scan Settings
class BioAgeScanSettings(BaseModel):
    """Admin-configurable bio-age scan settings"""

    enabled: bool = True
    scan_name: str = "Bio-Age Skin Analysis"
    show_age_estimate: bool = True
    show_recommendations: bool = True
    collect_email: bool = True
    email_results: bool = True
    offer_discount: bool = True
    discount_code: str = "BIOSCAN10"
    discount_value: float = 10.0


# Comparison Tool Settings
class ComparisonToolSettings(BaseModel):
    """Admin-configurable product comparison tool settings"""

    enabled: bool = True
    tool_name: str = "Product Comparison Tool"
    max_products: int = 4
    show_pricing: bool = True
    show_ingredients: bool = True
    highlight_differences: bool = True


# Biomarker Benchmark Model for Comparison Tool
class BiomarkerBenchmark(BaseModel):
    """Biomarker benchmark data for comparison tool"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # e.g., "Collagen Density", "Skin Hydration", "UV Damage Index"
    category: str = "general"  # skin_age, hydration, elasticity, pigmentation, etc.
    unit: str = ""  # e.g., "%", "score", "mg/ml"
    
    # Benchmark ranges
    low_threshold: float  # Below this is "low/poor"
    optimal_min: float  # Optimal range minimum
    optimal_max: float  # Optimal range maximum
    high_threshold: float  # Above this is "high/excessive"
    
    # Display settings
    low_label: str = "Low"
    optimal_label: str = "Optimal"
    high_label: str = "High"
    
    # Advice text for different ranges
    low_advice: str = ""
    optimal_advice: str = ""
    high_advice: str = ""
    
    # Product recommendations for different ranges
    low_recommendations: List[str] = Field(default_factory=list)  # Product IDs
    high_recommendations: List[str] = Field(default_factory=list)
    
    # Visual settings
    color_low: str = "#EF4444"  # Red
    color_optimal: str = "#22C55E"  # Green
    color_high: str = "#F59E0B"  # Amber
    
    # Status
    is_active: bool = True
    display_order: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None


# Influencer Application Model
class InfluencerApplication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Personal Info
    full_name: str
    email: EmailStr
    phone: str = ""
    country: str = "Canada"

    # Social Media
    primary_platform: str  # instagram, tiktok, youtube, etc.
    social_handle: str
    follower_count: int
    engagement_rate: float = 0.0
    content_niche: str  # beauty, skincare, lifestyle, etc.
    profile_url: str

    # Additional Platforms (optional)
    secondary_platforms: List[Dict] = Field(
        default_factory=list
    )  # [{platform, handle, followers}]

    # Application Details
    why_partner: str  # Why they want to partner
    content_ideas: str  # How they plan to promote
    previous_brands: str = ""  # Previous brand partnerships

    # Status
    status: str = "pending"  # pending, approved, rejected, active, paused
    applied_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None

    # If Approved
    partner_code: Optional[str] = None  # Unique discount code
    partner_link: Optional[str] = None  # Unique referral link
    custom_discount: Optional[float] = None  # Override default discount
    custom_commission: Optional[float] = None  # Override default commission

    # Stats (updated automatically)
    total_clicks: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    total_commission: float = 0.0
    pending_payout: float = 0.0


# Referral Model (for tracking referrals)
class Referral(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referrer_id: str  # User who referred
    referrer_email: str
    referee_email: str  # New customer email
    referee_id: Optional[str] = None  # Set when they sign up
    referral_code: str
    status: str = "pending"  # pending, signed_up, purchased, rewarded
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    signed_up_at: Optional[str] = None
    purchased_at: Optional[str] = None
    order_id: Optional[str] = None
    order_total: float = 0.0
    referrer_reward_given: bool = False
    referee_reward_given: bool = False


# ============= REWARDS & LOYALTY SYSTEM MODELS =============


class UserRewardsProfile(BaseModel):
    """Extended user profile for rewards/loyalty tracking"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    email: str

    # Points balance
    points_balance: int = 0
    lifetime_points_earned: int = 0
    lifetime_points_redeemed: int = 0

    # Daily login tracking
    login_streak: int = 0
    last_login_date: Optional[str] = None  # YYYY-MM-DD format
    total_logins: int = 0

    # Referral tracking
    referral_code: str = Field(
        default_factory=lambda: "".join(
            random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8)
        )
    )
    total_referrals: int = 0
    successful_referrals: int = 0  # Referrals that resulted in purchases

    # Milestones achieved
    milestones_achieved: List[str] = []  # ["10_logins", "10_referrals", etc.]

    # Timestamps
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ReferralClick(BaseModel):
    """Track referral link clicks"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referral_code: str
    referrer_user_id: str
    program_type: str = "general"  # influencer, quiz, bioAgeScan, founder, etc.
    clicked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ip_hash: Optional[str] = None  # Hashed IP for deduplication
    user_agent: Optional[str] = None
    converted: bool = False
    conversion_order_id: Optional[str] = None


class ReferralConversion(BaseModel):
    """Track successful referral conversions (purchases)"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referral_code: str
    referrer_user_id: str
    referee_email: str
    order_id: str
    order_total: float
    points_awarded: int = 0
    commission_earned: float = 0.0
    program_type: str = "general"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PointsTransaction(BaseModel):
    """Individual points transaction record"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    action: str  # daily_login, referral_conversion, quiz_completion, bio_scan, redemption, etc.
    points: int  # Positive for earned, negative for redeemed
    description: str
    reference_id: Optional[str] = None  # Order ID, referral ID, etc.
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RewardsMilestone(BaseModel):
    """Milestone configuration"""

    id: str
    name: str
    description: str
    trigger_type: str  # login_count, referral_count, points_earned
    trigger_value: int
    reward_type: str  # discount_percent, discount_fixed, points, badge
    reward_value: float
    is_active: bool = True


# ============= REWARDS SYSTEM CONSTANTS =============
POINTS_PER_LOGIN = 10  # 10 points per daily login
POINTS_PER_REFERRAL = 60  # 60 points per successful referral
POINTS_TO_DOLLARS = 100  # 100 points = $5 (0.05 per point)
LOGIN_MILESTONE = 10  # 10 logins = $5 discount milestone
REFERRAL_MILESTONE = 10  # 10 referrals = 30% discount milestone


# About Page Content Model
class AboutPageContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "about_page"
    # Hero Section
    hero_badge: str = "OUR STORY"
    hero_title: str = "Rooted in Science"
    hero_subtitle: str = (
        "ReRoots was founded with a simple belief: skincare should be backed by science, not marketing hype."
    )
    # Mission Section
    mission_title: str = "Our Mission"
    mission_image: str = (
        "https://images.unsplash.com/photo-1670444010821-e63091bddf1f?w=800"
    )
    mission_text_1: str = (
        "We combine cutting-edge biotechnology with time-tested natural ingredients to create skincare that delivers real, visible results."
    )
    mission_text_2: str = (
        "Our flagship ingredient, PDRN (Polydeoxyribonucleotide), has been used in professional skincare settings for decades. We've harnessed this powerful bioactive compound and formulated it for daily cosmetic use."
    )
    mission_text_3: str = (
        "Every product is developed in partnership with dermatologists and undergoes rigorous testing to ensure safety and efficacy."
    )
    # Values Section
    values_title: str = "Our Values"
    value_1_title: str = "Science-First"
    value_1_description: str = (
        "Every ingredient is selected based on scientific evidence, not trends."
    )
    value_2_title: str = "Transparency"
    value_2_description: str = (
        "We share our full ingredient lists and the science behind our formulations."
    )
    value_3_title: str = "Sustainability"
    value_3_description: str = (
        "Eco-conscious packaging and responsibly sourced ingredients."
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoreSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "store_settings"
    store_name: str = "ReRoots"
    store_email: str = "admin@reroots.ca"
    store_phone: str = "+12265017777"
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    live_chat: LiveChatSettings = Field(default_factory=LiveChatSettings)
    google_business: GoogleBusinessSettings = Field(
        default_factory=GoogleBusinessSettings
    )
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    language: LanguageSettings = Field(default_factory=LanguageSettings)
    # Influencer & Referral Programs
    influencer_program: InfluencerProgramSettings = Field(
        default_factory=InfluencerProgramSettings
    )
    referral_program: ReferralProgramSettings = Field(
        default_factory=ReferralProgramSettings
    )
    # Quiz, Bio-Age Scan, Comparison Programs
    quiz_program: QuizProgramSettings = Field(default_factory=QuizProgramSettings)
    bio_age_scan: BioAgeScanSettings = Field(default_factory=BioAgeScanSettings)
    comparison_tool: ComparisonToolSettings = Field(
        default_factory=ComparisonToolSettings
    )
    # Logo customization
    logo_url: Optional[str] = None  # Custom logo URL
    logo_size: str = "medium"  # small, medium, large, xlarge
    logo_bg_opacity: float = 0.9  # Logo background transparency (0.0 to 1.0)
    # Login page customization
    login_background_image: Optional[str] = None  # URL or uploaded image path
    admin_login_background_image: Optional[str] = None
    # Global site background - applies to ALL pages
    global_site_background: Optional[str] = None  # URL or uploaded image path
    global_background_enabled: bool = (
        False  # Toggle to enable/disable global background
    )
    global_background_opacity: float = 0.15  # Overlay opacity (0.0 to 1.0)
    global_background_overlay_color: str = "#FFFFFF"  # Overlay color for readability
    # Live/Animated Background Settings
    live_background_type: str = "none"  # none, video, gradient, particles
    live_background_video_url: Optional[str] = None
    live_gradient_colors: List[str] = Field(
        default_factory=lambda: ["#F8A5B8", "#C9A86C", "#FDF9F9"]
    )
    live_gradient_speed: int = 10  # seconds for animation cycle
    live_particles_enabled: bool = False
    live_particles_color: str = "#F8A5B8"
    live_particles_count: int = 50
    # First Purchase Discount - Auto-applied for new customers
    first_purchase_discount_enabled: bool = True
    first_purchase_discount_percent: float = 10.0  # Default 10%
    # First Purchase CODE - Special code only works for first-time buyers
    first_purchase_code_enabled: bool = True
    first_purchase_code: str = "SIGNUP25"  # The actual code
    first_purchase_code_percent: float = 25.0  # Discount percentage
    # Site-Wide Promo Banner - Shows on homepage
    promo_banner_enabled: bool = False
    promo_banner_text: str = (
        "🎉 Welcome! Use code WELCOME10 for 10% off your first order!"
    )
    promo_banner_code: Optional[str] = "WELCOME10"
    promo_banner_discount_percent: Optional[float] = 10.0
    promo_banner_bg_color: str = "#F8A5B8"  # Pink background
    promo_banner_text_color: str = "#FFFFFF"  # White text
    promo_banner_link: Optional[str] = "/shop"  # Where banner clicks go
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= CHAT MESSAGE MODELS =============


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: str = (
        "gpt-4o"  # Options: gpt-4o, gpt-4o-mini, claude-sonnet-4-5-20250929, gemini-2.5-flash
    )


# ============= CUSTOMER CHAT MODELS =============


class CustomerChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender: str  # "customer", "ai", "admin"
    customer_name: Optional[str] = "Guest"
    customer_email: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerConversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str = "Guest"
    customer_email: Optional[str] = None
    status: str = "active"  # active, resolved, escalated
    ai_handled: bool = True
    needs_attention: bool = False
    last_message: Optional[str] = None
    message_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    customer_name: Optional[str] = "Guest"
    customer_email: Optional[str] = None


# ============= TYPOGRAPHY SETTINGS MODEL =============


class FontSettings(BaseModel):
    family: str = "Inter"
    heading_family: str = "Playfair Display"
    base_size: int = 16
    h1_size: int = 48
    h2_size: int = 36
    h3_size: int = 24
    h4_size: int = 20
    body_size: int = 16
    small_size: int = 14
    heading_weight: int = 700
    body_weight: int = 400
    primary_color: str = "#2D2A2E"
    secondary_color: str = "#5A5A5A"
    accent_color: str = "#F8A5B8"
    heading_color: str = "#2D2A2E"
    link_color: str = "#F8A5B8"


class TypographySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "typography_settings"
    fonts: FontSettings = Field(default_factory=FontSettings)
    google_fonts_url: str = (
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= HOMEPAGE CUSTOM SECTIONS MODEL =============


class HomepageSection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    subtitle: Optional[str] = None
    content: str
    image_url: Optional[str] = None
    image_position: str = "right"  # left, right, background, none
    background_color: str = "#FFFFFF"
    text_color: str = "#2D2A2E"
    button_text: Optional[str] = None
    button_link: Optional[str] = None
    order: int = 0
    is_active: bool = True
    section_type: str = "custom"  # our_story, our_mission, custom
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= SUBSCRIPTION MODELS =============


class SubscriptionPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    price: float
    interval_type: str = "months"  # days, weeks, months
    interval_value: int = 1  # e.g., 1 month, 2 weeks, 30 days
    discount_percent: int = 10
    features: List[str] = Field(default_factory=list)
    is_active: bool = True
    min_commitment_months: int = 0  # 0 = no minimum
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "subscription_settings"
    enabled: bool = True
    allow_cancel_anytime: bool = True
    default_discount_percent: int = 15
    show_savings_badge: bool = True
    subscribe_button_text: str = "Subscribe & Save"
    subscription_description: str = (
        "Get your favorite products delivered automatically and save!"
    )


class CustomerSubscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    user_name: str = ""
    plan_id: Optional[str] = None
    product_id: Optional[str] = None  # For product-specific subscriptions
    product_name: Optional[str] = None
    quantity: int = 1
    status: str = "active"  # active, paused, cancelled, expired
    discount_percent: int = 15
    price: float
    interval_type: str = "months"  # days, weeks, months
    interval_value: int = 1
    next_delivery_date: Optional[str] = None
    delivery_address: Optional[dict] = None
    payment_method: str = "manual"  # manual, stripe, paypal
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cancelled_at: Optional[datetime] = None


