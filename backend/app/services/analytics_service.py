from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import (
    ConcentrationMetrics,
    HoldingAnalyticsDetail,
    HistoricalRiskMetrics,
    PortfolioAnalyticsResponse,
    PortfolioCompleteness,
    PortfolioRiskAssessment,
    PortfolioValuation,
    RiskComponentScores,
    SectorAllocation,
    UnpricedPositionDetail,
    ValuationStatus,
)
from app.schemas.insight import PortfolioInsightsResponse
from app.schemas.market_data import QuoteStatus
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService
from app.services.risk_scoring_service import (
    calculate_portfolio_risk_assessment,
    generate_portfolio_risk_insights,
)

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

def quantize_currency(val: Decimal) -> Decimal:
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

def quantize_ratio(val: Decimal) -> Decimal:
    return val.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

class AnalyticsService:
    """
    Portfolio analytics and financial valuation engine.
    Calculates cost basis, market valuation, unrealized P/L, sector exposure,
    and concentration with strict Decimal accuracy and missing-price handling.
    """

    def __init__(
        self,
        session: AsyncSession,
        market_data_service: Optional[MarketDataService] = None,
    ):
        self.session = session
        self.portfolio_service = PortfolioService(session)
        self.market_data_service = market_data_service or MarketDataService()

    async def calculate_portfolio_analytics(
        self, portfolio_id: str
    ) -> Optional[PortfolioAnalyticsResponse]:
        """
        Calculates comprehensive analytics for a portfolio by ID.
        Returns None if portfolio does not exist (calling route yields 404).
        """
        portfolio = await self.portfolio_service.get_portfolio(portfolio_id)
        if portfolio is None:
            return None

        now = datetime.now(timezone.utc)
        holdings = portfolio.holdings or []
        total_holdings_count = len(holdings)

        # 1. Edge Case: Empty Portfolio
        if total_holdings_count == 0:
            return PortfolioAnalyticsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                is_sample=portfolio.is_sample,
                calculated_at=now,
                status=ValuationStatus.EMPTY,
                valuation=PortfolioValuation(
                    total_cost_basis=Decimal("0.00"),
                    total_market_value=Decimal("0.00"),
                    priced_cost_basis=Decimal("0.00"),
                    unrealized_pnl=None,
                    unrealized_pnl_percent=None,
                ),
                completeness=PortfolioCompleteness(
                    is_complete=False,
                    completeness_ratio=Decimal("0.0000"),
                    total_holdings_count=0,
                    priced_holdings_count=0,
                    unpriced_holdings_count=0,
                    has_stale_prices=False,
                    has_simulated_prices=True,
                    unpriced_positions=[],
                ),
                concentration=ConcentrationMetrics(
                    top_holding_symbol=None,
                    top_holding_weight_percent=None,
                    top_3_concentration_percent=None,
                    herfindahl_index=None,
                    effective_holdings_count=None,
                    concentration_tier=None,
                ),
                sector_allocations=[],
                holdings=[],
                historical_risk=HistoricalRiskMetrics(
                    annualized_volatility_percent=None,
                    maximum_drawdown_percent=None,
                    beta=None,
                    benchmark_relative_return_percent=None,
                    benchmark_symbol="NIFTY 50",
                    data_status="INSUFFICIENT_HISTORY",
                ),
                risk_assessment=PortfolioRiskAssessment(
                    composite_risk_score=None,
                    risk_tier=None,
                    assessment_status="EMPTY",
                    components=RiskComponentScores(),
                ),
            )

        # 2. Query market data per unique (symbol, exchange) holding position
        holding_details_raw = []
        unpriced_positions: List[UnpricedPositionDetail] = []
        total_cost_basis = Decimal("0.00")
        has_stale_prices = False
        has_simulated_prices = False

        for h in holdings:
            qty = Decimal(h.quantity)
            buy_price = Decimal(h.average_buy_price)
            cost_basis = quantize_currency(qty * buy_price)
            total_cost_basis += cost_basis

            quote = await self.market_data_service.get_quote(h.symbol, exchange=h.exchange)

            if quote.is_stale:
                has_stale_prices = True
            if quote.is_simulated:
                has_simulated_prices = True

            is_priced = quote.status == QuoteStatus.AVAILABLE and quote.current_price is not None

            if is_priced:
                curr_price = Decimal(quote.current_price)
                market_val = quantize_currency(qty * curr_price)
                unrealized_pnl = quantize_currency(market_val - cost_basis)
                unrealized_pnl_pct = (
                    quantize_currency((unrealized_pnl / cost_basis) * Decimal("100"))
                    if cost_basis > Decimal("0")
                    else Decimal("0.00")
                )
            else:
                curr_price = None
                market_val = None
                unrealized_pnl = None
                unrealized_pnl_pct = None
                unpriced_positions.append(
                    UnpricedPositionDetail(
                        holding_id=h.id,
                        symbol=h.symbol,
                        exchange=h.exchange,
                        quantity=h.quantity,
                        cost_basis=cost_basis,
                        pricing_status=quote.status.value,
                        pricing_source=quote.source,
                        price_explanation=quote.explanation,
                    )
                )

            holding_details_raw.append(
                {
                    "holding": h,
                    "cost_basis": cost_basis,
                    "current_price": curr_price,
                    "market_value": market_val,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_percent": unrealized_pnl_pct,
                    "quote": quote,
                }
            )

        total_cost_basis = quantize_currency(total_cost_basis)

        # 3. Aggregations for priced vs unpriced
        priced_items = [item for item in holding_details_raw if item["market_value"] is not None]
        priced_count = len(priced_items)
        unpriced_count = total_holdings_count - priced_count

        total_market_value = quantize_currency(
            sum((item["market_value"] for item in priced_items), Decimal("0.00"))
        )
        priced_cost_basis = quantize_currency(
            sum((item["cost_basis"] for item in priced_items), Decimal("0.00"))
        )

        # Determine top-level valuation status & completeness
        if priced_count == 0:
            status = ValuationStatus.UNVALUED
            is_complete = False
            completeness_ratio = Decimal("0.0000")
            portfolio_pnl = None
            portfolio_pnl_pct = None
        elif priced_count == total_holdings_count:
            status = ValuationStatus.COMPLETE
            is_complete = True
            completeness_ratio = Decimal("1.0000")
            portfolio_pnl = quantize_currency(total_market_value - priced_cost_basis)
            portfolio_pnl_pct = (
                quantize_currency((portfolio_pnl / priced_cost_basis) * Decimal("100"))
                if priced_cost_basis > Decimal("0")
                else None
            )
        else:
            status = ValuationStatus.PARTIAL
            is_complete = False
            completeness_ratio = quantize_ratio(
                Decimal(priced_count) / Decimal(total_holdings_count)
            )
            # Partial pricing compares market value ONLY against priced cost basis (no false loss)
            portfolio_pnl = quantize_currency(total_market_value - priced_cost_basis)
            portfolio_pnl_pct = (
                quantize_currency((portfolio_pnl / priced_cost_basis) * Decimal("100"))
                if priced_cost_basis > Decimal("0")
                else None
            )

        # 4. Holding-level weights and performance contributions
        final_holdings: List[HoldingAnalyticsDetail] = []
        for item in holding_details_raw:
            h = item["holding"]
            q = item["quote"]
            mv = item["market_value"]
            cb = item["cost_basis"]
            pnl = item["unrealized_pnl"]

            # Market value weight
            if mv is not None and total_market_value > Decimal("0"):
                mv_weight = quantize_currency((mv / total_market_value) * Decimal("100"))
            else:
                mv_weight = None

            # Cost basis weight
            if total_cost_basis > Decimal("0"):
                cb_weight = quantize_currency((cb / total_cost_basis) * Decimal("100"))
            else:
                cb_weight = None

            # Unrealized P/L contribution in INR (market value - cost basis)
            if pnl is not None:
                pnl_contrib = pnl  # already quantized to currency
            else:
                pnl_contrib = None

            # Cost-basis-weighted unrealized return contribution in percentage points
            # Formula: (unrealized_pnl / priced_cost_basis) * 100
            if pnl is not None and priced_cost_basis > Decimal("0"):
                return_contrib = quantize_currency((pnl / priced_cost_basis) * Decimal("100"))
            else:
                return_contrib = None

            final_holdings.append(
                HoldingAnalyticsDetail(
                    holding_id=h.id,
                    symbol=h.symbol,
                    exchange=h.exchange,
                    quantity=h.quantity,
                    average_buy_price=h.average_buy_price,
                    cost_basis=cb,
                    current_price=item["current_price"],
                    market_value=mv,
                    unrealized_pnl=pnl,
                    unrealized_pnl_percent=item["unrealized_pnl_percent"],
                    market_value_weight_percent=mv_weight,
                    cost_basis_weight_percent=cb_weight,
                    unrealized_pnl_contribution=pnl_contrib,
                    cost_basis_weighted_return_contribution_percent=return_contrib,
                    pricing_status=q.status.value,
                    pricing_source=q.source,
                    quote_generated_at=q.generated_at,
                    quote_cached_at=q.cached_at,
                    market_as_of=q.market_as_of,
                    is_simulated=q.is_simulated,
                    is_stale=q.is_stale,
                    sector=h.sector,
                    asset_class=h.asset_class,
                    price_explanation=q.explanation,
                )
            )

        # 5. Concentration Metrics (based on priced holdings)
        if priced_count > 0 and total_market_value > Decimal("0"):
            sorted_priced = sorted(priced_items, key=lambda x: x["market_value"], reverse=True)
            top_item = sorted_priced[0]
            top_symbol = top_item["holding"].symbol
            top_weight = quantize_currency(
                (top_item["market_value"] / total_market_value) * Decimal("100")
            )

            # Top 3 concentration
            top_3_sum = sum((x["market_value"] for x in sorted_priced[:3]), Decimal("0.00"))
            top_3_pct = quantize_currency((top_3_sum / total_market_value) * Decimal("100"))

            # Herfindahl-Hirschman Index using unrounded intermediate Decimal shares
            unrounded_shares = [
                x["market_value"] / total_market_value for x in sorted_priced
            ]
            hhi_raw = sum(s * s for s in unrounded_shares)
            hhi = quantize_ratio(hhi_raw)

            # Effective number of holdings (ENH = 1 / unrounded HHI)
            if hhi_raw > Decimal("0"):
                enh = quantize_ratio(Decimal("1") / hhi_raw)
            else:
                enh = None

            # Concentration tier based on documented HHI boundaries
            if hhi < Decimal("0.1500"):
                concentration_tier = "LOW"
            elif hhi <= Decimal("0.2500"):
                concentration_tier = "MODERATE"
            else:
                concentration_tier = "HIGH"

            concentration = ConcentrationMetrics(
                top_holding_symbol=top_symbol,
                top_holding_weight_percent=top_weight,
                top_3_concentration_percent=top_3_pct,
                herfindahl_index=hhi,
                effective_holdings_count=enh,
                concentration_tier=concentration_tier,
            )
        else:
            concentration = ConcentrationMetrics(
                top_holding_symbol=None,
                top_holding_weight_percent=None,
                top_3_concentration_percent=None,
                herfindahl_index=None,
                effective_holdings_count=None,
                concentration_tier=None,
            )

        # 6. Sector Allocations
        sector_groups: Dict[str, Dict] = {}
        for item in holding_details_raw:
            h = item["holding"]
            sec = h.sector.strip() if h.sector and h.sector.strip() else "Unclassified"
            if sec not in sector_groups:
                sector_groups[sec] = {
                    "cost_basis": Decimal("0.00"),
                    "priced_cost_basis": Decimal("0.00"),
                    "market_value": Decimal("0.00"),
                    "holdings_count": 0,
                    "priced_count": 0,
                    "unpriced_count": 0,
                }
            sector_groups[sec]["cost_basis"] += item["cost_basis"]
            sector_groups[sec]["holdings_count"] += 1

            if item["market_value"] is not None:
                sector_groups[sec]["market_value"] += item["market_value"]
                sector_groups[sec]["priced_cost_basis"] += item["cost_basis"]
                sector_groups[sec]["priced_count"] += 1
            else:
                sector_groups[sec]["unpriced_count"] += 1

        sector_allocations: List[SectorAllocation] = []
        for sec, data in sector_groups.items():
            sec_cb = quantize_currency(data["cost_basis"])
            sec_priced_cb = quantize_currency(data["priced_cost_basis"])
            sec_mv = quantize_currency(data["market_value"])

            # Market-value allocation percentage
            if total_market_value > Decimal("0") and data["priced_count"] > 0:
                alloc_pct = quantize_currency((sec_mv / total_market_value) * Decimal("100"))
            else:
                alloc_pct = None  # Do not imply zero exposure when unpriced

            cb_weight = (
                quantize_currency((sec_cb / total_cost_basis) * Decimal("100"))
                if total_cost_basis > Decimal("0")
                else None
            )

            # Sector unrealized P/L and return metrics (priced holdings only)
            if data["priced_count"] > 0:
                sec_pnl = quantize_currency(sec_mv - sec_priced_cb)
                sec_pnl_pct = (
                    quantize_currency((sec_pnl / sec_priced_cb) * Decimal("100"))
                    if sec_priced_cb > Decimal("0")
                    else Decimal("0.00")
                )
                sec_return_contrib = (
                    quantize_currency((sec_pnl / priced_cost_basis) * Decimal("100"))
                    if priced_cost_basis > Decimal("0")
                    else None
                )
            else:
                sec_pnl = None
                sec_pnl_pct = None
                sec_return_contrib = None

            sector_allocations.append(
                SectorAllocation(
                    sector=sec,
                    cost_basis=sec_cb,
                    market_value=sec_mv,
                    allocation_percent=alloc_pct,
                    cost_basis_weight_percent=cb_weight,
                    unrealized_pnl=sec_pnl,
                    unrealized_pnl_percent=sec_pnl_pct,
                    cost_basis_weighted_return_contribution_percent=sec_return_contrib,
                    holdings_count=data["holdings_count"],
                    priced_count=data["priced_count"],
                    unpriced_count=data["unpriced_count"],
                )
            )

        # Sort sectors descending by market value, then cost basis
        sector_allocations.sort(key=lambda s: (s.market_value, s.cost_basis), reverse=True)

        completeness_obj = PortfolioCompleteness(
            is_complete=is_complete,
            completeness_ratio=completeness_ratio,
            total_holdings_count=total_holdings_count,
            priced_holdings_count=priced_count,
            unpriced_holdings_count=unpriced_count,
            has_stale_prices=has_stale_prices,
            has_simulated_prices=has_simulated_prices,
            unpriced_positions=unpriced_positions,
        )

        risk_assessment = calculate_portfolio_risk_assessment(
            status=status,
            concentration=concentration,
            completeness=completeness_obj,
            sector_allocations=sector_allocations,
        )

        return PortfolioAnalyticsResponse(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio.name,
            is_sample=portfolio.is_sample,
            calculated_at=now,
            status=status,
            valuation=PortfolioValuation(
                total_cost_basis=total_cost_basis,
                total_market_value=total_market_value,
                priced_cost_basis=priced_cost_basis,
                unrealized_pnl=portfolio_pnl,
                unrealized_pnl_percent=portfolio_pnl_pct,
            ),
            completeness=completeness_obj,
            concentration=concentration,
            sector_allocations=sector_allocations,
            holdings=final_holdings,
            historical_risk=HistoricalRiskMetrics(
                annualized_volatility_percent=None,
                maximum_drawdown_percent=None,
                beta=None,
                benchmark_relative_return_percent=None,
                benchmark_symbol="NIFTY 50",
                data_status="INSUFFICIENT_HISTORY",
            ),
            risk_assessment=risk_assessment,
        )

    async def get_portfolio_insights(
        self, portfolio_id: str
    ) -> Optional[PortfolioInsightsResponse]:
        """
        Calculates deterministic, explainable insights for a portfolio by ID.
        Returns None if portfolio does not exist (calling route yields 404).
        """
        analytics = await self.calculate_portfolio_analytics(portfolio_id)
        if analytics is None:
            return None

        portfolio = await self.portfolio_service.get_portfolio(portfolio_id)
        is_sample = portfolio.is_sample if portfolio else False

        insights = generate_portfolio_risk_insights(
            portfolio_id=portfolio_id,
            status=analytics.status,
            concentration=analytics.concentration,
            completeness=analytics.completeness,
            sector_allocations=analytics.sector_allocations,
            risk_assessment=analytics.risk_assessment or PortfolioRiskAssessment(),
        )

        return PortfolioInsightsResponse(
            portfolio_id=portfolio_id,
            insights=insights,
            total_insights=len(insights),
            generated_at=datetime.now(timezone.utc),
            is_sample_portfolio=is_sample,
        )
