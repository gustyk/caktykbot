"""Database schemas and Pydantic models for CakTykBot.

This module defines the data models for MongoDB collections with
comprehensive cross-field validation as defined in Phase 2 and Phase 3 analysis.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarketCapCategory(str, Enum):
    """Market capitalization categories for Indonesian stocks."""

    LARGE = "large"  # Blue chip
    MID = "mid"
    SMALL = "small"


class StockBase(BaseModel):
    """Base schema for stock information."""

    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$", description="Ticker symbol (e.g. BBCA.JK)")
    name: str = Field(..., min_length=1, description="Company name")
    sector: Optional[str] = Field(None, description="Industrial sector")
    market_cap: MarketCapCategory = Field(default=MarketCapCategory.SMALL)
    is_active: bool = Field(default=True)


class StockCreate(StockBase):
    """Schema for creating a new stock in watchlist."""

    pass


class StockUpdate(BaseModel):
    """Schema for updating an existing stock."""

    name: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[MarketCapCategory] = None
    is_active: Optional[bool] = None


class StockInDB(StockBase):
    """Schema for stock as stored in database."""

    model_config = ConfigDict(from_attributes=True)

    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DailyPriceBase(BaseModel):
    """Base schema for daily price data (OHLCV)."""

    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$")
    date: datetime = Field(..., description="Trading date")
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    adjusted_close: float = Field(..., gt=0)

    @field_validator("date")
    @classmethod
    def validate_not_future(cls, v: datetime) -> datetime:
        """Ensure date is not in the future."""
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        
        if v > datetime.now(timezone.utc):
            raise ValueError("Price date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_ohlc_relationships(self) -> "DailyPriceBase":
        """Validate relationships between price points.
        
        Rules:
        - High must be the highest point of the day
        - Low must be the lowest point of the day
        """
        # High checks
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be lower than Low ({self.low})")
        if self.high < self.open:
            raise ValueError(f"High ({self.high}) cannot be lower than Open ({self.open})")
        if self.high < self.close:
            raise ValueError(f"High ({self.high}) cannot be lower than Close ({self.close})")
        
        # Low checks
        if self.low > self.open:
            raise ValueError(f"Low ({self.low}) cannot be higher than Open ({self.open})")
        if self.low > self.close:
            raise ValueError(f"Low ({self.low}) cannot be higher than Close ({self.close})")
            
        return self


class TechnicalIndicators(BaseModel):
    """Schema for technical indicators."""

    ema_8: Optional[float] = None
    ema_21: Optional[float] = None
    ema_50: Optional[float] = None
    ema_150: Optional[float] = None
    ema_200: Optional[float] = None
    atr_14: Optional[float] = None
    vol_ma_20: Optional[float] = None


class DailyPriceInDB(DailyPriceBase, TechnicalIndicators):
    """Schema for daily price as stored in database."""

    model_config = ConfigDict(from_attributes=True)

    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineRun(BaseModel):
    """Schema for tracking pipeline execution results."""

    date: datetime = Field(..., description="Date of the run")
    duration: float = Field(..., ge=0, description="Duration in seconds")
    total_stocks: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    fail_count: int = Field(..., ge=0)
    errors: list[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def validate_run_not_future(cls, v: datetime) -> datetime:
        """Ensure run date is not in the future."""
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
            
        if v > datetime.now(timezone.utc):
            raise ValueError("Pipeline run date cannot be in the future")
        return v
    
    @model_validator(mode="after")
    def validate_counts(self) -> "PipelineRun":
        """Ensure success + fail == total."""
        if self.success_count + self.fail_count != self.total_stocks:
            raise ValueError(
                f"Sum of success ({self.success_count}) and fail ({self.fail_count}) "
                f"must equal total stocks ({self.total_stocks})"
            )
        return self


class SignalBase(BaseModel):
    """Base schema for trading signals."""
    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$")
    date: datetime
    verdict: str  # BUY, SELL, HOLD
    strategy_source: str
    strategy_sources: list[str]
    entry_price: float
    sl_price: float
    tp_price: float
    rr_ratio: float
    tech_score: float
    confidence: str
    reasoning: str



class CircuitBreakerTriggerType(str, Enum):
    """Types of triggers for circuit breaker."""
    
    DRAWDOWN_10PCT = "drawdown_10pct"
    CONSECUTIVE_LOSS_5 = "consecutive_loss_5"


class CircuitBreakerEvent(BaseModel):
    """Record of a circuit breaker activation."""
    
    trigger_type: CircuitBreakerTriggerType
    trigger_value: float = Field(..., description="Value that triggered the CB (e.g. drawdown % or loss count)")
    suspended_from: datetime
    suspended_until: datetime
    risk_override: float = Field(..., description="Reduced risk level during suspension")
    resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(from_attributes=True)


class SectorMap(BaseModel):
    """Mapping of stock symbol to sector and category."""
    
    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$")
    sector: str
    market_cap_category: MarketCapCategory
    avg_daily_volume: Optional[int] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalInDB(SignalBase):
    """Signal stored in DB."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Risk Management Fields (Sprint 4)
    lot_size: Optional[int] = None
    exposure_pct: Optional[float] = None
    heat_before: Optional[float] = None
    heat_after: Optional[float] = None
    risk_warnings: list[str] = Field(default_factory=list)
    risk_blocked: bool = Field(default=False)
    block_reason: Optional[str] = None
    
    # Adaptive & Bandarmologi Fields (Sprint 5)
    personal_score: Optional[float] = None
    final_score: Optional[float] = None
    adaptive_weight: Optional[float] = None
    bias_warnings: list[str] = Field(default_factory=list)
    bandar_detail: Optional[BandarmologiDetail] = None


class PortfolioConfig(BaseModel):
    """User portfolio configuration."""
    user: str = Field(default="nesa", description="Username (single user mode)")
    total_capital: float = Field(..., gt=0, description="Total trading capital")
    risk_per_trade: float = Field(..., gt=0.0, le=0.05, description="Risk per trade in decimal (e.g. 0.01 for 1%)")
    
    # Risk Management Settings (Sprint 4)
    max_heat: float = Field(default=0.08, ge=0.0, le=0.5, description="Max total portfolio risk exposure")
    heat_warning_threshold: float = Field(default=0.06, ge=0.0, le=0.5, description="Heat level to trigger warning")
    max_exposure_pct: float = Field(default=0.25, ge=0.01, le=1.0, description="Max exposure per stock")
    max_small_cap_exposure: float = Field(default=0.15, ge=0.01, le=1.0, description="Max exposure for small cap stocks")
    max_stocks_per_sector: int = Field(default=2, ge=1, le=10, description="Max open positions per sector")
    
    cash_reserve_target: float = Field(default=0.30, ge=0.0, le=1.0, description="Target cash reserve ratio")
    correlation_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Correlation threshold for size reduction")
    circuit_breaker_enabled: bool = Field(default=True, description="Enable/disable circuit breaker")
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class TradeLeg(BaseModel):
    """Partial exit leg details."""
    exit_date: datetime
    exit_price: float
    qty: int
    fees: float = 0.0
    pnl_rupiah: float
    pnl_percent: float
    emotion_tag: Optional[str] = None


class Trade(BaseModel):
    """Trade record for journal."""
    user: str = Field(default="nesa")
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime] = None
    qty: int
    qty_remaining: int
    entry_price: float
    exit_price: Optional[float] = None
    fees: float = 0.0
    strategy: str
    setup_tag: Optional[str] = None
    emotion_tag: Optional[str] = None
    risk_percent: float
    notes: Optional[str] = None
    status: str = Field(..., pattern="^(draft|open|closed)$")
    
    # Analytics fields (calculated)
    pnl_rupiah: Optional[float] = None
    pnl_percent: Optional[float] = None
    holding_days: Optional[int] = None
    rr_actual: Optional[float] = None
    win_loss: Optional[str] = None
    
    signal_ref: Optional[str] = None  # ObjectId string if linked to signal
    legs: list[TradeLeg] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # ID handling
    id: Optional[str] = Field(None, alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, v):
        if v:
            return str(v)
        return None


class BrokerSummaryBase(BaseModel):
    """Base schema for Broker Summary data."""
    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$")
    date: datetime
    broker_code: str
    broker_name: str
    buy_value: float
    sell_value: float
    net_value: float
    buy_lot: int
    sell_lot: int

    @field_validator("date")
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class BrokerSummaryInDB(BrokerSummaryBase):
    """Broker Summary as stored in database."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(from_attributes=True)


class ForeignFlowBase(BaseModel):
    """Base schema for Foreign Flow data."""
    symbol: str = Field(..., pattern=r"^[A-Z0-9-]+\.JK$")
    date: datetime
    foreign_buy: float
    foreign_sell: float
    foreign_net: float
    foreign_ratio: float

    @field_validator("date")
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class ForeignFlowInDB(ForeignFlowBase):
    """Foreign Flow as stored in database."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(from_attributes=True)


class BandarmologiDetail(BaseModel):
    """Detailed Bandarmologi analysis data."""
    accumulation_days: int
    top_brokers: list[str]
    foreign_net_7d: float
    base_support: float
    base_resistance: float
    distribution_risk: bool


# Update SignalInDB is complex due to inheritance, we will redefine or patch it if possible. 
# But since we can't redefine existing class easily without potentially duplications if we append, 
# I will actually start the replacement earlier to modify SignalInDB directly.


class BacktestRun(BaseModel):
    """Schema for a backtest run record."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = Field(None, alias="_id")
    strategy: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    risk_per_trade: float
    total_trades: int
    metrics: dict
    duration_seconds: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, v):
        if v:
            return str(v)
        return None


class BacktestTrade(BaseModel):
    """Schema for a trade generated during backtest."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = Field(None, alias="_id")
    run_id: str 
    strategy: str
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: datetime
    exit_price: float
    qty: int
    pnl_rupiah: float
    pnl_percent: float
    hold_days: int
    exit_reason: str
    
    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, v):
        if v:
            return str(v)
        return None


class AuditLog(BaseModel):
    """Schema for security audit logs."""
    
    event: str
    user: str
    ip_address: Optional[str] = None
    details: dict = Field(default_factory=dict)
    severity: str = Field(default="INFO")  # INFO, WARNING, CRITICAL
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(from_attributes=True)



