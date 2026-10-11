import React from 'react';
import {
  PortfolioAnalyticsResponse,
  ValuationStatus,
} from '../../types/analytics';
import { PortfolioResponse } from '../../types/portfolio';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Clock,
  Briefcase,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

export interface PortfolioOverviewCardProps {
  portfolio: PortfolioResponse;
  analytics: PortfolioAnalyticsResponse | null;
  isLoading: boolean;
}

export const PortfolioOverviewCard: React.FC<PortfolioOverviewCardProps> = ({
  portfolio,
  analytics,
  isLoading,
}) => {
  const getStatusBadge = (status?: ValuationStatus) => {
    switch (status) {
      case 'COMPLETE':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>COMPLETE</span>
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>PARTIAL VALUATION</span>
          </span>
        );
      case 'UNVALUED':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            <span>UNVALUED</span>
          </span>
        );
      case 'EMPTY':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-50 text-gray-700 border border-gray-200">
            <HelpCircle className="w-3.5 h-3.5 text-gray-500" />
            <span>EMPTY</span>
          </span>
        );
    }
  };

  const valuation = analytics?.valuation;
  const completeness = analytics?.completeness;

  const pnlNum = valuation?.unrealized_pnl
    ? typeof valuation.unrealized_pnl === 'string'
      ? parseFloat(valuation.unrealized_pnl)
      : valuation.unrealized_pnl
    : null;

  const isProfit = pnlNum !== null && pnlNum >= 0;

  return (
    <div
      data-testid="portfolio-overview-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header Banner */}
      <div className="p-6 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
              <Briefcase className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-bold text-gray-900 tracking-tight">
                  {portfolio.name}
                </h2>
                {portfolio.is_sample && (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
                    Sample / Demo
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                {portfolio.description || 'Investment portfolio position overview'} &bull;{' '}
                <span className="font-medium text-gray-700">
                  {portfolio.holdings_count} position{portfolio.holdings_count === 1 ? '' : 's'}
                </span>
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-start md:self-auto">
          {isLoading ? (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 animate-pulse">
              Calculating analytics...
            </span>
          ) : (
            getStatusBadge(analytics?.status)
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Market Value */}
          <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Total Market Value
            </p>
            <p
              data-testid="total-market-value"
              className="text-2xl font-bold text-gray-900 mt-1 tracking-tight"
            >
              {isLoading ? '...' : formatCurrency(valuation?.total_market_value)}
            </p>
            <p className="text-[11px] text-gray-500 mt-1 flex items-center space-x-1">
              <span>Priced Basis:</span>
              <span className="font-medium text-gray-700">
                {formatCurrency(valuation?.priced_cost_basis)}
              </span>
            </p>
          </div>

          {/* Total Cost Basis */}
          <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Total Cost Basis
            </p>
            <p
              data-testid="total-cost-basis"
              className="text-2xl font-bold text-gray-900 mt-1 tracking-tight"
            >
              {isLoading ? '...' : formatCurrency(valuation?.total_cost_basis)}
            </p>
            <p className="text-[11px] text-gray-500 mt-1">
              Acquisition value of all positions
            </p>
          </div>

          {/* Unrealized P/L */}
          <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Unrealized P&L
            </p>
            <div className="flex items-baseline space-x-2 mt-1">
              <span
                data-testid="unrealized-pnl"
                className={`text-2xl font-bold tracking-tight ${
                  pnlNum === null
                    ? 'text-gray-400'
                    : isProfit
                    ? 'text-emerald-700'
                    : 'text-rose-700'
                }`}
              >
                {isLoading ? '...' : formatCurrency(valuation?.unrealized_pnl)}
              </span>
              {valuation?.unrealized_pnl_percent !== undefined &&
                valuation?.unrealized_pnl_percent !== null && (
                  <span
                    className={`inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full ${
                      isProfit
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {isProfit ? (
                      <TrendingUp className="w-3 h-3 mr-0.5" />
                    ) : (
                      <TrendingDown className="w-3 h-3 mr-0.5" />
                    )}
                    {formatPercent(valuation.unrealized_pnl_percent)}
                  </span>
                )}
            </div>
            <p className="text-[11px] text-gray-500 mt-1">
              Based on priced positions only
            </p>
          </div>

          {/* Completeness & Quality */}
          <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Pricing Completeness
            </p>
            <div className="flex items-baseline space-x-2 mt-1">
              <span
                data-testid="completeness-ratio"
                className="text-2xl font-bold text-gray-900 tracking-tight"
              >
                {isLoading
                  ? '...'
                  : completeness
                  ? `${(
                      parseFloat(String(completeness.completeness_ratio)) * 100
                    ).toFixed(0)}%`
                  : '—'}
              </span>
              <span className="text-xs text-gray-500 font-medium">
                ({completeness?.priced_holdings_count || 0}/
                {completeness?.total_holdings_count || 0} priced)
              </span>
            </div>
            <div className="w-full bg-gray-200 h-1.5 rounded-full mt-2.5 overflow-hidden">
              <div
                className={`h-full transition-all ${
                  completeness?.is_complete ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
                style={{
                  width: completeness
                    ? `${parseFloat(String(completeness.completeness_ratio)) * 100}%`
                    : '0%',
                }}
              />
            </div>
          </div>
        </div>

        {/* Warning Banners: Stale Prices & Unpriced Positions */}
        {completeness?.has_stale_prices && (
          <div
            data-testid="stale-price-banner"
            className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 flex items-start space-x-2.5 text-xs text-amber-800"
          >
            <Clock className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Stale Market Quotes Detected:</span> One or
              more positions were valued using cached emergency stale prices due to temporary provider
              unavailability.
            </div>
          </div>
        )}

        {completeness && completeness.unpriced_positions.length > 0 && (
          <div
            data-testid="unpriced-positions-banner"
            className="mt-4 p-3.5 rounded-lg bg-rose-50/80 border border-rose-200 text-xs text-rose-900 space-y-1.5"
          >
            <div className="flex items-center space-x-2 font-semibold">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>
                {completeness.unpriced_positions.length} Unpriced Position
                {completeness.unpriced_positions.length === 1 ? '' : 's'} Excluded from Market
                Valuation:
              </span>
            </div>
            <p className="text-[11px] text-rose-700 leading-relaxed">
              Missing prices are strictly excluded from market totals rather than fabricated or assumed
              as zero.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {completeness.unpriced_positions.map((up) => (
                <span
                  key={up.holding_id}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-rose-100 text-rose-900 font-mono text-[11px]"
                >
                  <span className="font-bold">{up.symbol}</span>
                  <span className="text-rose-600">({up.pricing_status})</span>
                  {up.price_explanation && (
                    <span className="text-rose-500 text-[10px]">— {up.price_explanation}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
