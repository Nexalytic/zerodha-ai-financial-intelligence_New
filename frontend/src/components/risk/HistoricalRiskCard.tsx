import React from 'react';
import { HistoricalRiskMetrics } from '../../types/analytics';
import { formatNumber, formatPercent } from '../../utils/formatters';
import { History, AlertTriangle, ShieldCheck, Info } from 'lucide-react';

export interface HistoricalRiskCardProps {
  historicalRisk: HistoricalRiskMetrics | null | undefined;
  isLoading: boolean;
}

export const HistoricalRiskCard: React.FC<HistoricalRiskCardProps> = ({
  historicalRisk,
  isLoading,
}) => {
  const dataStatus = historicalRisk?.data_status || 'INSUFFICIENT_HISTORY';
  const isHistoryComplete = dataStatus === 'COMPLETE';

  const formatHistoricalMetric = (
    value: number | string | null | undefined,
    formatter: (v: number | string | null | undefined) => string
  ) => {
    if (value === null || value === undefined || value === '') {
      return 'Unavailable';
    }
    return formatter(value);
  };

  return (
    <div
      data-testid="historical-risk-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Chronological Historical Risk &amp; Benchmark Metrics
            </h2>
            <p className="text-xs text-gray-500">
              Longitudinal time-series volatility, maximum peak-to-trough drawdown, and systematic beta relative to benchmark.
            </p>
          </div>
        </div>

        <div>
          <span
            data-testid="historical-data-status"
            className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold ${
              isHistoryComplete
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-800 border border-amber-200'
            }`}
          >
            {isHistoryComplete ? (
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            )}
            <span>STATUS: {dataStatus}</span>
          </span>
        </div>
      </div>

      <div className="p-5 space-y-6">
        {isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Querying chronological trade history and benchmark series...</span>
            </div>
          </div>
        ) : (
          <>
            {/* Primary Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Annualized Volatility */}
              <div
                data-testid="metric-volatility"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Annualized Volatility
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatHistoricalMetric(
                    historicalRisk?.annualized_volatility_percent,
                    formatPercent
                  )}
                </div>
                <p className="text-[11px] text-gray-500">
                  252-day standard deviation of daily returns
                </p>
              </div>

              {/* Maximum Drawdown */}
              <div
                data-testid="metric-drawdown"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Maximum Drawdown
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatHistoricalMetric(
                    historicalRisk?.maximum_drawdown_percent,
                    formatPercent
                  )}
                </div>
                <p className="text-[11px] text-gray-500">
                  Worst historical peak-to-trough decline
                </p>
              </div>

              {/* Systematic Beta */}
              <div
                data-testid="metric-beta"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Systematic Beta (&beta;)
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatHistoricalMetric(historicalRisk?.beta, (v) => formatNumber(v, 2))}
                </div>
                <p className="text-[11px] text-gray-500">
                  Relative covariance vs {historicalRisk?.benchmark_symbol || 'NIFTY 50'}
                </p>
              </div>

              {/* Benchmark Relative Return */}
              <div
                data-testid="metric-relative-return"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Relative Return
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatHistoricalMetric(
                    historicalRisk?.benchmark_relative_return_percent,
                    formatPercent
                  )}
                </div>
                <p className="text-[11px] text-gray-500">
                  Performance differential vs benchmark
                </p>
              </div>
            </div>

            {/* Insufficient History Banner / Disclosure */}
            {!isHistoryComplete && (
              <div
                data-testid="insufficient-history-banner"
                className="p-4 rounded-lg bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-start space-x-3"
              >
                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-bold">
                    Historical Price Series Insufficient ({dataStatus})
                  </p>
                  <p className="text-amber-800 leading-relaxed text-[11px]">
                    Chronological volatility, maximum drawdown, and beta calculations require multi-period verified historical price series. Rather than extrapolating synthetic charts or fabricating fake historical volatility from live snapshot prices, these metrics are strictly reported as unavailable until adequate chronological trade history is archived.
                  </p>
                </div>
              </div>
            )}

            {/* Transparency Disclaimer */}
            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 flex items-start space-x-2.5 text-xs text-gray-500">
              <Info className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-gray-700 text-[11px] uppercase tracking-wide">
                  Historical Integrity &amp; Transparency Guarantee
                </p>
                <p className="mt-0.5 text-[11px] leading-relaxed">
                  {historicalRisk?.disclaimer ||
                    'Historical volatility and risk metrics reflect actual chronological price observations when available. When historical price series are unavailable, metrics are strictly reported as null rather than simulated.'}
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
