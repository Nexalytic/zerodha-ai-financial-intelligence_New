from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ValuationStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNVALUED = "UNVALUED"
    EMPTY = "EMPTY"

class UnpricedPositionDetail(BaseModel):
    holding_id: str = Field(..., description="Holding primary key")
    symbol: str = Field(..., description="Ticker symbol")
    exchange: str = Field(..., description="Exchange identifier")
    quantity: int = Field(..., description="Quantity held")
    cost_basis: Decimal = Field(..., description="Cost basis (quantity * average buy price)")
    pricing_status: str = Field(..., description="Status from provider (UNAVAILABLE or ERROR)")
    pricing_source: Optional[str] = Field(default=None, description="Data source attribution")
    price_explanation: Optional[str] = Field(default=None, description="Explanation for missing quote")

    model_config = ConfigDict(from_attributes=True)

class HoldingAnalyticsDetail(BaseModel):
    holding_id: str = Field(..., description="Holding primary key")
    symbol: str = Field(..., description="Ticker symbol")
    exchange: str = Field(..., description="Exchange identifier")
    quantity: int = Field(..., description="Quantity held")
    average_buy_price: Decimal = Field(..., description="Acquisition price per share")
    cost_basis: Decimal = Field(..., description="Total acquisition cost")
    current_price: Optional[Decimal] = Field(default=None, description="Current quote price, null if unpriced")
    market_value: Optional[Decimal] = Field(default=None, description="Current market valuation, null if unpriced")
    unrealized_pnl: Optional[Decimal] = Field(default=None, description="Absolute unrealized profit/loss, null if unpriced")
    unrealized_pnl_percent: Optional[Decimal] = Field(default=None, description="Percentage profit/loss, null if unpriced")
    market_value_weight_percent: Optional[Decimal] = Field(
        default=None, description="Weight in total known market value, null if unpriced or total value 0"
    )
    cost_basis_weight_percent: Optional[Decimal] = Field(
        default=None, description="Weight in total portfolio cost basis"
    )
    unrealized_pnl_contribution: Optional[Decimal] = Field(
        default=None,
        description="Absolute unrealized P/L contribution in INR (market value - cost basis). Null if unpriced.",
    )
    cost_basis_weighted_return_contribution_percent: Optional[Decimal] = Field(
        default=None,
        description="Holding contribution in percentage points to portfolio unrealized return percent, weighted by priced cost basis (unrealized_pnl / priced_cost_basis * 100). Not time-weighted or money-weighted return. Null if unpriced or priced cost basis is zero.",
    )
    pricing_status: str = Field(..., description="Quote status: AVAILABLE, UNAVAILABLE, or ERROR")
    pricing_source: Optional[str] = Field(default=None, description="Quote provider attribution")
    quote_generated_at: Optional[datetime] = Field(default=None, description="Timestamp quote was produced")
    quote_cached_at: Optional[datetime] = Field(default=None, description="Timestamp quote was cached")
    market_as_of: Optional[datetime] = Field(default=None, description="Real market timestamp, strictly null for simulated")
    is_simulated: bool = Field(default=True, description="True if simulated market quote")
    is_stale: bool = Field(default=False, description="True if quote served from emergency stale cache")
    sector: Optional[str] = Field(default=None, description="Industry sector")
    asset_class: str = Field(default="EQUITY", description="Asset class")
    price_explanation: Optional[str] = Field(default=None, description="Explanation if unpriced")

    model_config = ConfigDict(from_attributes=True)

class SectorAllocation(BaseModel):
    sector: str = Field(..., description="Sector name")
    cost_basis: Decimal = Field(..., description="Total cost basis in sector")
    market_value: Decimal = Field(..., description="Total known market value in sector")
    allocation_percent: Optional[Decimal] = Field(
        default=None,
        description="Market-value allocation percent based strictly on priced holdings and total known market value. Null if total market value is zero.",
    )
    cost_basis_weight_percent: Optional[Decimal] = Field(
        default=None, description="Cost-basis weight percent in portfolio"
    )
    unrealized_pnl: Optional[Decimal] = Field(
        default=None,
        description="Absolute unrealized P/L for priced holdings in sector (market value - priced cost basis). Null if no holdings are priced.",
    )
    unrealized_pnl_percent: Optional[Decimal] = Field(
        default=None,
        description="Percentage unrealized P/L for priced holdings in sector. Null if no holdings are priced or priced cost basis is zero.",
    )
    cost_basis_weighted_return_contribution_percent: Optional[Decimal] = Field(
        default=None,
        description="Sector contribution in percentage points to portfolio unrealized return percent, weighted by portfolio priced cost basis (sector_pnl / total_priced_cost_basis * 100). Not time-weighted or money-weighted return. Null if no holdings are priced or total priced cost basis is zero.",
    )
    holdings_count: int = Field(..., description="Total holdings in sector")
    priced_count: int = Field(..., description="Priced holdings count in sector")
    unpriced_count: int = Field(..., description="Unpriced holdings count in sector")

class ConcentrationMetrics(BaseModel):
    top_holding_symbol: Optional[str] = Field(default=None, description="Ticker of largest priced holding by market value")
    top_holding_weight_percent: Optional[Decimal] = Field(
        default=None, description="Weight of top holding in total known market value"
    )
    top_3_concentration_percent: Optional[Decimal] = Field(
        default=None, description="Combined weight of top 3 priced holdings"
    )
    herfindahl_index: Optional[Decimal] = Field(
        default=None,
        description="Herfindahl-Hirschman Index on a 0.0 to 1.0 scale using normalized market weights of priced positions",
    )
    effective_holdings_count: Optional[Decimal] = Field(
        default=None,
        description="Effective number of holdings (ENH = 1 / HHI) calculated as inverse of unrounded HHI. Null if unpriced or HHI is zero.",
    )
    concentration_tier: Optional[str] = Field(
        default=None,
        description="Qualitative concentration tier: LOW (HHI < 0.1500), MODERATE (0.1500 <= HHI <= 0.2500), HIGH (HHI > 0.2500). Null if unpriced.",
    )

class PortfolioValuation(BaseModel):
    total_cost_basis: Decimal = Field(..., description="Sum of cost basis across all holdings")
    total_market_value: Decimal = Field(..., description="Sum of market value across priced holdings")
    priced_cost_basis: Decimal = Field(..., description="Cost basis of priced holdings only")
    unrealized_pnl: Optional[Decimal] = Field(
        default=None, description="Known unrealized P/L (market value - priced cost basis). Null if no holdings are priced."
    )
    unrealized_pnl_percent: Optional[Decimal] = Field(
        default=None, description="Unrealized P/L percentage of priced holdings. Null if no holdings are priced."
    )

class PortfolioCompleteness(BaseModel):
    is_complete: bool = Field(..., description="True strictly if total holdings > 0 and all holdings are priced")
    completeness_ratio: Decimal = Field(
        ..., description="Ratio of priced holdings to total holdings (0.0000 to 1.0000). 0.0000 for empty portfolio."
    )
    total_holdings_count: int = Field(..., description="Total holdings count")
    priced_holdings_count: int = Field(..., description="Count of holdings with available market prices")
    unpriced_holdings_count: int = Field(..., description="Count of holdings lacking valid prices")
    has_stale_prices: bool = Field(default=False, description="True if any holding was valued using a stale quote")
    has_simulated_prices: bool = Field(default=True, description="True if any holding was valued using a simulated quote")
    unpriced_positions: List[UnpricedPositionDetail] = Field(
        default_factory=list, description="Details of holdings without valid market prices"
    )

class HistoricalRiskMetrics(BaseModel):
    annualized_volatility_percent: Optional[Decimal] = Field(
        default=None,
        description="Annualized historical volatility based on 252 trading days. Null if insufficient history or unavailable.",
    )
    maximum_drawdown_percent: Optional[Decimal] = Field(
        default=None,
        description="Maximum peak-to-trough percentage decline over historical path. Null if unavailable.",
    )
    beta: Optional[Decimal] = Field(
        default=None,
        description="Systematic risk relative to benchmark (e.g. NIFTY 50). Null if benchmark history is unavailable or variance is zero.",
    )
    benchmark_relative_return_percent: Optional[Decimal] = Field(
        default=None,
        description="Portfolio return minus benchmark return over comparable period. Null if benchmark data is unavailable.",
    )
    benchmark_symbol: Optional[str] = Field(
        default=None,
        description="Benchmark index identifier (e.g. NIFTY 50).",
    )
    data_status: str = Field(
        default="INSUFFICIENT_HISTORY",
        description="Data availability indicator: COMPLETE, INSUFFICIENT_HISTORY, BENCHMARK_UNAVAILABLE, or UNAVAILABLE.",
    )
    disclaimer: str = Field(
        default="Historical volatility and risk metrics reflect actual chronological price observations when available. When historical price series are unavailable, metrics are strictly reported as null rather than simulated.",
        description="Regulatory and transparency disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)

class RiskComponentScores(BaseModel):
    single_stock_concentration_score: Optional[Decimal] = Field(
        default=None,
        description="Normalized risk score 0.00-100.00 for single-stock concentration (35% weight). Null if unpriced or empty.",
    )
    sector_concentration_score: Optional[Decimal] = Field(
        default=None,
        description="Normalized risk score 0.00-100.00 for sector concentration (25% weight). Null if unpriced or empty.",
    )
    diversification_breadth_score: Optional[Decimal] = Field(
        default=None,
        description="Normalized risk score 0.00-100.00 for portfolio breadth / ENH (20% weight). Null if unpriced or empty.",
    )
    data_quality_score: Optional[Decimal] = Field(
        default=None,
        description="Normalized risk score 0.00-100.00 for valuation uncertainty / data quality (20% weight). Null if unpriced or empty.",
    )

    model_config = ConfigDict(from_attributes=True)


class PortfolioRiskAssessment(BaseModel):
    composite_risk_score: Optional[Decimal] = Field(
        default=None,
        description="Weighted composite structural risk score on a 0.00-100.00 scale. Null if portfolio is empty or wholly unpriced.",
    )
    risk_tier: Optional[str] = Field(
        default=None,
        description="Qualitative risk tier: LOW (<= 30.00), MODERATE (30.01 - 55.00), ELEVATED (55.01 - 75.00), HIGH (> 75.00). Null if unpriced.",
    )
    assessment_status: str = Field(
        default="COMPLETE",
        description="Risk assessment status: COMPLETE, PARTIAL, UNVALUED, or EMPTY",
    )
    components: RiskComponentScores = Field(
        default_factory=RiskComponentScores,
        description="Component risk scores on 0-100 scale",
    )
    weights: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "single_stock_concentration": Decimal("0.35"),
            "sector_concentration": Decimal("0.25"),
            "diversification_breadth": Decimal("0.20"),
            "data_quality": Decimal("0.20"),
        },
        description="Deterministic component weight distribution summing to 1.00",
    )
    methodology_scope: str = Field(
        default="Measures structural portfolio concentration, sector exposure, breadth (ENH), and valuation completeness. This is not a comprehensive market-risk model; it does not infer historical volatility, beta, or drawdown from snapshot quotes.",
        description="Scope and methodology disclosure",
    )
    disclaimer: str = Field(
        default="Educational and demonstration risk assessment only. Not SEBI-registered investment advice.",
        description="Regulatory compliance disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)


class PortfolioAnalyticsResponse(BaseModel):
    portfolio_id: str = Field(..., description="Portfolio identifier")
    portfolio_name: str = Field(..., description="Portfolio name")
    is_sample: bool = Field(..., description="Marker indicating demo/sample portfolio")
    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC calculation timestamp",
    )
    status: ValuationStatus = Field(
        ...,
        description="Portfolio valuation status: EMPTY, COMPLETE, PARTIAL, or UNVALUED",
    )
    valuation: PortfolioValuation = Field(..., description="Portfolio aggregate valuation")
    completeness: PortfolioCompleteness = Field(..., description="Data completeness and quality indicators")
    concentration: ConcentrationMetrics = Field(..., description="Portfolio concentration indicators")
    sector_allocations: List[SectorAllocation] = Field(
        default_factory=list, description="Sector exposure breakdowns"
    )
    holdings: List[HoldingAnalyticsDetail] = Field(
        default_factory=list, description="Detailed per-holding analytics"
    )
    historical_risk: Optional[HistoricalRiskMetrics] = Field(
        default=None,
        description="Historical volatility, drawdown, and benchmark risk metrics",
    )
    risk_assessment: Optional[PortfolioRiskAssessment] = Field(
        default=None,
        description="Deterministic portfolio risk aggregation, component scores, and classification tier",
    )
    disclaimer: str = Field(
        default="Calculated analytics reflect simulated market quotes where applicable. Missing market prices are excluded from market valuations rather than fabricated.",
        description="Informational disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)
