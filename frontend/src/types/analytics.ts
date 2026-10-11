export type ValuationStatus = 'COMPLETE' | 'PARTIAL' | 'UNVALUED' | 'EMPTY';

export interface UnpricedPositionDetail {
  holding_id: string;
  symbol: string;
  exchange: string;
  quantity: number;
  cost_basis: number | string;
  pricing_status: string;
  pricing_source?: string | null;
  price_explanation?: string | null;
}

export interface HoldingAnalyticsDetail {
  holding_id: string;
  symbol: string;
  exchange: string;
  quantity: number;
  average_buy_price: number | string;
  cost_basis: number | string;
  current_price?: number | string | null;
  market_value?: number | string | null;
  unrealized_pnl?: number | string | null;
  unrealized_pnl_percent?: number | string | null;
  market_value_weight_percent?: number | string | null;
  cost_basis_weight_percent?: number | string | null;
  unrealized_pnl_contribution?: number | string | null;
  cost_basis_weighted_return_contribution_percent?: number | string | null;
  pricing_status: string;
  pricing_source?: string | null;
  quote_generated_at?: string | null;
  quote_cached_at?: string | null;
  market_as_of?: string | null;
  is_simulated: boolean;
  is_stale: boolean;
  sector?: string | null;
  asset_class: string;
  price_explanation?: string | null;
}

export interface SectorAllocation {
  sector: string;
  cost_basis: number | string;
  market_value: number | string;
  allocation_percent?: number | string | null;
  cost_basis_weight_percent?: number | string | null;
  unrealized_pnl?: number | string | null;
  unrealized_pnl_percent?: number | string | null;
  cost_basis_weighted_return_contribution_percent?: number | string | null;
  holdings_count: number;
  priced_count: number;
  unpriced_count: number;
}

export interface ConcentrationMetrics {
  top_holding_symbol?: string | null;
  top_holding_weight_percent?: number | string | null;
  top_3_concentration_percent?: number | string | null;
  herfindahl_index?: number | string | null;
  effective_holdings_count?: number | string | null;
  concentration_tier?: 'LOW' | 'MODERATE' | 'HIGH' | string | null;
}

export interface PortfolioValuation {
  total_cost_basis: number | string;
  total_market_value: number | string;
  priced_cost_basis: number | string;
  unrealized_pnl?: number | string | null;
  unrealized_pnl_percent?: number | string | null;
}

export interface PortfolioCompleteness {
  is_complete: boolean;
  completeness_ratio: number | string;
  total_holdings_count: number;
  priced_holdings_count: number;
  unpriced_holdings_count: number;
  has_stale_prices: boolean;
  has_simulated_prices: boolean;
  unpriced_positions: UnpricedPositionDetail[];
}

export interface HistoricalRiskMetrics {
  annualized_volatility_percent?: number | string | null;
  maximum_drawdown_percent?: number | string | null;
  beta?: number | string | null;
  benchmark_relative_return_percent?: number | string | null;
  benchmark_symbol?: string | null;
  data_status: string;
  disclaimer: string;
}

export interface RiskComponentScores {
  single_stock_concentration_score?: number | string | null;
  sector_concentration_score?: number | string | null;
  diversification_breadth_score?: number | string | null;
  data_quality_score?: number | string | null;
}

export interface PortfolioRiskAssessment {
  composite_risk_score?: number | string | null;
  risk_tier?: 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | string | null;
  assessment_status: string;
  components: RiskComponentScores;
  weights: Record<string, number | string>;
  methodology_scope: string;
  disclaimer: string;
}

export interface PortfolioAnalyticsResponse {
  portfolio_id: string;
  portfolio_name: string;
  is_sample: boolean;
  calculated_at: string;
  status: ValuationStatus;
  valuation: PortfolioValuation;
  completeness: PortfolioCompleteness;
  concentration: ConcentrationMetrics;
  sector_allocations: SectorAllocation[];
  holdings: HoldingAnalyticsDetail[];
  historical_risk?: HistoricalRiskMetrics | null;
  risk_assessment?: PortfolioRiskAssessment | null;
  disclaimer: string;
}
