import React from 'react';
import { HoldingAnalyticsDetail } from '../../types/analytics';
import { formatCurrency, formatPercent, formatNumber } from '../../utils/formatters';
import { Clock, CheckCircle2, AlertTriangle, AlertCircle, Plus } from 'lucide-react';

export interface HoldingsTableProps {
  holdings: HoldingAnalyticsDetail[];
  isLoading: boolean;
  onAddHolding?: () => void;
}

export const HoldingsTable: React.FC<HoldingsTableProps> = ({
  holdings,
  isLoading,
  onAddHolding,
}) => {
  const getPricingStatusBadge = (status: string, isStale: boolean, isSimulated: boolean) => {
    switch (status) {
      case 'AVAILABLE':
        return (
          <div className="flex flex-col space-y-1">
            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              <span>Available</span>
            </span>
            <div className="flex items-center space-x-1">
              {isSimulated && (
                <span
                  data-testid="simulated-price-badge"
                  className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200"
                >
                  Simulated
                </span>
              )}
              {isStale && (
                <span
                  data-testid="stale-price-badge"
                  className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200 flex items-center space-x-0.5"
                >
                  <Clock className="w-2.5 h-2.5" />
                  <span>Stale</span>
                </span>
              )}
            </div>
          </div>
        );
      case 'UNAVAILABLE':
        return (
          <span
            data-testid="unavailable-price-badge"
            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
          >
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            <span>Unavailable</span>
          </span>
        );
      case 'ERROR':
      default:
        return (
          <span
            data-testid="error-price-badge"
            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200"
          >
            <AlertCircle className="w-3 h-3 text-rose-600" />
            <span>Pricing Error</span>
          </span>
        );
    }
  };

  return (
    <div
      data-testid="holdings-table-container"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-gray-900 tracking-tight">
            Portfolio Holdings
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Individual positions, acquisition costs, live simulated valuations, and pricing veracity.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-xs font-mono text-gray-400">
            Total: {holdings.length} position{holdings.length === 1 ? '' : 's'}
          </span>
          {onAddHolding && (
            <button
              onClick={onAddHolding}
              data-testid="add-holding-btn"
              aria-label="Add holding position"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Holding</span>
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table
          aria-label="Portfolio Holdings"
          className="w-full text-left text-xs border-collapse"
        >
          <thead className="bg-gray-50/80 border-b border-gray-200 text-gray-600 uppercase tracking-wider text-[11px]">
            <tr>
              <th scope="col" className="py-3 px-4 font-semibold">
                Symbol & Sector
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Qty
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Avg Buy Price
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Cost Basis
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Market Price
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Market Value
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Unrealized P&L
              </th>
              <th scope="col" className="py-3 px-4 font-semibold text-right">
                Portfolio Weight
              </th>
              <th scope="col" className="py-3 px-4 font-semibold">
                Pricing Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 font-sans">
            {isLoading ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-gray-500">
                  <div className="inline-flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                    <span>Loading positions and analytics...</span>
                  </div>
                </td>
              </tr>
            ) : holdings.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-10 text-center text-gray-500">
                  <p className="text-sm font-semibold text-gray-700">No positions held in this portfolio.</p>
                  <p className="text-xs text-gray-400 mt-0.5 mb-3">Add your first equity, ETF, or mutual fund position to track valuations and analytics.</p>
                  {onAddHolding && (
                    <button
                      onClick={onAddHolding}
                      data-testid="empty-add-holding-btn"
                      className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add First Holding</span>
                    </button>
                  )}
                </td>
              </tr>
            ) : (
              holdings.map((h) => {
                const pnlNum = h.unrealized_pnl
                  ? typeof h.unrealized_pnl === 'string'
                    ? parseFloat(h.unrealized_pnl)
                    : h.unrealized_pnl
                  : null;
                const isPnlPositive = pnlNum !== null && pnlNum >= 0;

                return (
                  <tr
                    key={h.holding_id}
                    data-testid={`holding-row-${h.symbol}`}
                    className="hover:bg-gray-50/60 transition-colors"
                  >
                    {/* Symbol & Exchange & Sector */}
                    <td className="py-3.5 px-4 font-medium text-gray-900">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-gray-900 text-sm tracking-tight">
                          {h.symbol}
                        </span>
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-gray-100 text-gray-600">
                          {h.exchange}
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        {h.sector || 'Unassigned Sector'} &bull; {h.asset_class}
                      </p>
                    </td>

                    {/* Quantity */}
                    <td className="py-3.5 px-4 text-right font-mono text-gray-800">
                      {formatNumber(h.quantity, 0)}
                    </td>

                    {/* Average Buy Price */}
                    <td className="py-3.5 px-4 text-right font-mono text-gray-800">
                      {formatCurrency(h.average_buy_price)}
                    </td>

                    {/* Cost Basis */}
                    <td className="py-3.5 px-4 text-right font-mono text-gray-800">
                      {formatCurrency(h.cost_basis)}
                    </td>

                    {/* Market Price */}
                    <td className="py-3.5 px-4 text-right font-mono">
                      {h.current_price !== null && h.current_price !== undefined ? (
                        <div className="font-semibold text-gray-900">
                          {formatCurrency(h.current_price)}
                        </div>
                      ) : (
                        <div
                          data-testid="missing-price-cell"
                          className="text-gray-400 font-sans italic"
                          title={h.price_explanation || 'Price unavailable'}
                        >
                          Unavailable
                        </div>
                      )}
                    </td>

                    {/* Market Value */}
                    <td className="py-3.5 px-4 text-right font-mono font-medium text-gray-900">
                      {h.market_value !== null && h.market_value !== undefined ? (
                        formatCurrency(h.market_value)
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>

                    {/* Unrealized P/L */}
                    <td className="py-3.5 px-4 text-right font-mono">
                      {h.unrealized_pnl !== null && h.unrealized_pnl !== undefined ? (
                        <div
                          className={`font-semibold ${
                            isPnlPositive ? 'text-emerald-700' : 'text-rose-700'
                          }`}
                        >
                          <div>{formatCurrency(h.unrealized_pnl)}</div>
                          <div className="text-[10px]">
                            {formatPercent(h.unrealized_pnl_percent)}
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>

                    {/* Portfolio Weight */}
                    <td className="py-3.5 px-4 text-right font-mono text-gray-700">
                      {h.market_value_weight_percent !== null &&
                      h.market_value_weight_percent !== undefined ? (
                        <span>{parseFloat(String(h.market_value_weight_percent)).toFixed(2)}%</span>
                      ) : h.cost_basis_weight_percent !== null &&
                        h.cost_basis_weight_percent !== undefined ? (
                        <span className="text-gray-400 text-[11px]" title="Cost basis weight (unpriced)">
                          {parseFloat(String(h.cost_basis_weight_percent)).toFixed(2)}% (cost)
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>

                    {/* Pricing Status */}
                    <td className="py-3.5 px-4">
                      {getPricingStatusBadge(h.pricing_status, h.is_stale, h.is_simulated)}
                      {h.price_explanation && (
                        <p className="text-[10px] text-gray-400 mt-1 line-clamp-1" title={h.price_explanation}>
                          {h.price_explanation}
                        </p>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="p-3.5 bg-gray-50 border-t border-gray-100 text-[11px] text-gray-500 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
        <span>
          Prices marked <strong>Simulated</strong> reflect deterministic demonstration engine baselines.
        </span>
        <span>Unpriced holdings are excluded from market valuations without fabricated data.</span>
      </div>
    </div>
  );
};
