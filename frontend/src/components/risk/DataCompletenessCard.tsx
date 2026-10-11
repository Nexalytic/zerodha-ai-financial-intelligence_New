import React from 'react';
import { PortfolioCompleteness } from '../../types/analytics';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import {
  FileCheck2,
  AlertTriangle,
  Clock,
  Sparkles,
  Info,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export interface DataCompletenessCardProps {
  completeness: PortfolioCompleteness | undefined;
  isLoading: boolean;
}

export const DataCompletenessCard: React.FC<DataCompletenessCardProps> = ({
  completeness,
  isLoading,
}) => {
  const isComplete = completeness?.is_complete ?? false;
  const ratioPercent =
    completeness?.completeness_ratio !== null &&
    completeness?.completeness_ratio !== undefined
      ? Number(completeness.completeness_ratio) * 100
      : null;

  const unpricedList = completeness?.unpriced_positions || [];

  return (
    <div
      data-testid="data-completeness-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <FileCheck2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Data Quality &amp; Price Completeness
            </h2>
            <p className="text-xs text-gray-500">
              Transparency audit of pricing sources, completeness ratios, and emergency cache usage.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isComplete ? (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>100% PRICING COVERAGE</span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>PARTIAL COVERAGE</span>
            </span>
          )}
        </div>
      </div>

      <div className="p-5 space-y-6">
        {isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Auditing price completeness and feed freshness...</span>
            </div>
          </div>
        ) : (
          <>
            {/* Primary Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Completeness Ratio */}
              <div
                data-testid="completeness-ratio-metric"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Completeness Ratio
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatPercent(ratioPercent)}
                </div>
                <p className="text-[11px] text-gray-500">
                  Priced positions / total positions
                </p>
              </div>

              {/* Priced Positions Count */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Priced Positions
                </span>
                <div className="text-2xl font-bold text-emerald-700">
                  {completeness?.priced_holdings_count ?? '—'}
                </div>
                <p className="text-[11px] text-gray-500">
                  Positions with valid market valuation
                </p>
              </div>

              {/* Unpriced Positions Count */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Unpriced Positions
                </span>
                <div className={`text-2xl font-bold ${
                  (completeness?.unpriced_holdings_count ?? 0) > 0 ? 'text-amber-700' : 'text-gray-900'
                }`}>
                  {completeness?.unpriced_holdings_count ?? '—'}
                </div>
                <p className="text-[11px] text-gray-500">
                  Excluded from market valuation
                </p>
              </div>

              {/* Total Positions Count */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Total Positions
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {completeness?.total_holdings_count ?? '—'}
                </div>
                <p className="text-[11px] text-gray-500">
                  Recorded in portfolio ledger
                </p>
              </div>
            </div>

            {/* Price Quality Disclosures & Warnings */}
            <div className="space-y-3">
              {/* Stale Price Warning Banner */}
              {completeness?.has_stale_prices && (
                <div
                  data-testid="stale-price-warning"
                  className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start space-x-3"
                >
                  <Clock className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">Emergency Stale Price Quotes In Use</p>
                    <p className="mt-0.5 text-amber-800 leading-relaxed">
                      One or more holdings in this portfolio are valued using cached emergency quotes due to temporary upstream provider rate limits or downtime. Structural risk and valuation precision reflect higher uncertainty.
                    </p>
                  </div>
                </div>
              )}

              {/* Simulated Price Disclosure */}
              {completeness?.has_simulated_prices && (
                <div
                  data-testid="simulated-price-disclosure"
                  className="p-3.5 rounded-lg bg-blue-50/60 border border-blue-200 text-xs text-blue-900 flex items-start space-x-2.5"
                >
                  <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-blue-900">
                      Simulated Market Pricing Active:
                    </span>{' '}
                    <span className="text-blue-800">
                      Quotes reflect synthetic educational market data generated with deterministic spreads and zero external API credit expenditure.
                    </span>
                  </div>
                </div>
              )}

              {/* Distinction between Structural Risk and Data Quality Uncertainty */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 flex items-start space-x-2.5 text-xs text-gray-600">
                <Info className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">
                    Structural Risk vs. Data Quality Uncertainty
                  </p>
                  <p className="mt-0.5 leading-relaxed text-[11px]">
                    Structural risk assesses the allocation balance of your capital across assets and industries. Missing or stale quotes introduce estimation uncertainty. Unpriced holdings are intentionally excluded from market valuation rather than fabricated as zero or simulated guesses.
                  </p>
                </div>
              </div>
            </div>

            {/* Unpriced Positions Table */}
            {unpricedList.length > 0 && (
              <div
                data-testid="risk-unpriced-positions"
                className="mt-4 pt-4 border-t border-gray-100"
              >
                <div className="flex items-center space-x-2 mb-3">
                  <AlertCircle className="w-4 h-4 text-amber-600" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-800">
                    Unpriced Positions Excluded from Market Valuation ({unpricedList.length})
                  </h3>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-amber-50/50 border-y border-amber-200/60 text-amber-900 font-semibold uppercase tracking-wider text-[11px]">
                        <th scope="col" className="py-2.5 px-3">Symbol</th>
                        <th scope="col" className="py-2.5 px-3">Exchange</th>
                        <th scope="col" className="py-2.5 px-3 text-right">Qty</th>
                        <th scope="col" className="py-2.5 px-3 text-right">Cost Basis</th>
                        <th scope="col" className="py-2.5 px-3 text-center">Status</th>
                        <th scope="col" className="py-2.5 px-3">Price Explanation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {unpricedList.map((pos) => (
                        <tr
                          key={pos.holding_id}
                          className="hover:bg-gray-50/60 transition-colors"
                        >
                          <td className="py-2.5 px-3 font-semibold text-gray-900">
                            {pos.symbol}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-gray-600">
                            {pos.exchange}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-gray-800">
                            {pos.quantity}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-gray-800">
                            {formatCurrency(pos.cost_basis)}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200">
                              {pos.pricing_status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-gray-600 text-[11px]">
                            {pos.price_explanation || 'No market price quote available'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
