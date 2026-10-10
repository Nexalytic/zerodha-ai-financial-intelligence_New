from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class QuoteStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"

class Quote(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g. RELIANCE, TCS)")
    exchange: str = Field(default="NSE", description="Exchange identifier (e.g. NSE, BSE)")
    current_price: Optional[Decimal] = Field(
        default=None,
        description="Simulated quote price. Strictly null if unavailable or error."
    )
    change: Optional[Decimal] = Field(default=None, description="Price change from reference baseline")
    change_percent: Optional[Decimal] = Field(default=None, description="Percentage change from reference baseline")
    status: QuoteStatus = Field(
        default=QuoteStatus.AVAILABLE,
        description="Quote status: AVAILABLE, UNAVAILABLE, or ERROR"
    )
    is_simulated: bool = Field(
        default=True,
        description="Explicit flag indicating simulated data. Never real or live prices."
    )
    source: str = Field(
        default="SIMULATED_DEMO_PROVIDER",
        description="Provider identifier"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this simulated record was generated"
    )
    market_as_of: Optional[datetime] = Field(
        default=None,
        description="Real market observation timestamp. Strictly null for simulated data."
    )
    cached_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when this entry was written to cache"
    )
    cache_hit: bool = Field(
        default=False,
        description="True if served fresh from cache, False if computed or retrieved from provider"
    )
    ttl_remaining_seconds: Optional[float] = Field(
        default=None,
        description="Remaining TTL in seconds when served from cache"
    )
    is_stale: bool = Field(
        default=False,
        description="True if served as emergency stale fallback during provider failure"
    )
    disclaimer: str = Field(
        default="Simulated market quote for demonstration purposes only. Not real or live market data.",
        description="Legal and informational disclaimer"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Explanation when quote is UNAVAILABLE or in ERROR state"
    )

    model_config = ConfigDict(from_attributes=True)

class BatchQuotesResponse(BaseModel):
    quotes: dict[str, Quote] = Field(..., description="Dictionary of requested symbols to Quote objects")
    total_symbols: int = Field(..., description="Total symbols requested")
    cache_hits_count: int = Field(..., description="Count of quotes served fresh from cache")
    cache_misses_count: int = Field(..., description="Count of quotes fetched fresh or failed")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the batch response was assembled"
    )

class NewsArticle(BaseModel):
    id: str = Field(..., description="Unique article identifier")
    title: str = Field(..., description="Article headline")
    summary: str = Field(..., description="Article summary text")
    source: str = Field(
        default="Simulated Demo Financial News Engine",
        description="Attribution source (clearly fictional demo engine)"
    )
    published_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC publish timestamp"
    )
    url: Optional[str] = Field(default=None, description="Optional article reference URL")
    related_symbols: List[str] = Field(
        default_factory=list,
        description="List of related stock symbols"
    )
    sentiment: str = Field(default="NEUTRAL", description="Estimated sentiment: POSITIVE, NEGATIVE, or NEUTRAL")
    is_simulated: bool = Field(
        default=True,
        description="Explicit flag indicating simulated educational news"
    )
    disclaimer: str = Field(
        default="Simulated financial news generated for testing and demonstration only. Not verified or real news.",
        description="Informational disclaimer"
    )

    model_config = ConfigDict(from_attributes=True)

class NewsResponse(BaseModel):
    articles: List[NewsArticle] = Field(..., description="List of simulated news articles")
    total_count: int = Field(..., description="Total articles returned")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when response was generated"
    )
    cache_hit: bool = Field(default=False, description="True if response was served from cache")
    is_simulated: bool = Field(default=True, description="Explicit simulated response flag")
    disclaimer: str = Field(
        default="Simulated financial news response for testing and demonstration only.",
        description="Informational disclaimer"
    )
