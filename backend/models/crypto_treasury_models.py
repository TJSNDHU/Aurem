"""
Crypto Treasury Models
Pydantic models for crypto treasury management
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ConversionStatus(str, Enum):
    """Status of USD to USDT conversion"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, Enum):
    """Type of treasury transaction"""
    REVENUE = "revenue"  # Money coming in (Stripe)
    EXPENSE = "expense"  # Bills/costs going out
    CONVERSION = "conversion"  # USD to USDT conversion
    TRANSFER = "transfer"  # USDT transfer to wallet


class BlockchainNetwork(str, Enum):
    """Supported blockchain networks"""
    POLYGON = "polygon"
    ETHEREUM = "ethereum"
    BASE = "base"


class TreasuryTransaction(BaseModel):
    """Model for treasury transaction record"""
    transaction_id: str
    transaction_type: TransactionType
    amount_usd: float
    amount_usdt: Optional[float] = None
    description: str
    stripe_payment_id: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None
    status: ConversionStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversionRequest(BaseModel):
    """Request to convert USD to USDT"""
    amount_usd: float = Field(..., gt=0, description="Amount in USD to convert")
    auto_send: bool = Field(default=True, description="Automatically send to treasury wallet")
    
    @validator("amount_usd")
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError("Minimum conversion amount is $10 USD")
        return v


class WalletInfo(BaseModel):
    """Wallet information model"""
    wallet_address: str
    network: BlockchainNetwork
    balance_usdt: float = 0.0
    balance_native: float = 0.0  # MATIC for Polygon
    is_primary: bool = False
    created_at: datetime
    last_updated: datetime


class TreasuryConfig(BaseModel):
    """Treasury system configuration"""
    expense_reserve_usd: float = Field(
        default=5000.0,
        description="Amount of USD to keep for bills/expenses"
    )
    auto_conversion_enabled: bool = Field(
        default=True,
        description="Enable automatic conversions"
    )
    conversion_threshold_usd: float = Field(
        default=1000.0,
        description="Trigger auto-conversion when profit exceeds this"
    )
    conversion_frequency: str = Field(
        default="daily",
        description="How often to check for conversions: hourly, daily, weekly"
    )
    treasury_wallet_address: Optional[str] = Field(
        default=None,
        description="Primary treasury wallet for USDT storage"
    )
    blockchain_network: BlockchainNetwork = Field(
        default=BlockchainNetwork.POLYGON,
        description="Blockchain network for USDT"
    )


class ExpenseRecord(BaseModel):
    """Record of business expense"""
    expense_id: str
    description: str
    amount_usd: float
    category: str  # hosting, software, salaries, etc.
    paid: bool = False
    payment_method: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None


class TreasuryStats(BaseModel):
    """Treasury statistics summary"""
    total_revenue_usd: float
    total_expenses_usd: float
    current_profit_usd: float
    total_converted_usdt: float
    treasury_wallet_balance_usdt: float
    pending_conversions: int
    last_conversion_date: Optional[datetime] = None
    auto_conversion_enabled: bool
    next_conversion_eligible: bool


class ManualConversionTrigger(BaseModel):
    """Manually trigger a conversion"""
    amount_usd: Optional[float] = Field(
        default=None,
        description="Specific amount to convert, or None to convert all available profit"
    )
    reason: str = Field(
        default="Manual trigger",
        description="Reason for manual conversion"
    )
