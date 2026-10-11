import React from 'react';
import { SectorAllocation } from '../../types/analytics';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import { Layers, Building2 } from 'lucide-react';

export interface SectorAllocationsCardProps {
  sectors: SectorAllocation[];
  isLoading: boolean;
}

export const SectorAllocationsCard: React.FC<SectorAllocationsCardProps> = ({
  sectors,
  isLoading,
}) => {
  return (
    <div
      data-testid="sector-allocations-table"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Industry Sector Allocations &amp; Exposures
            </h2>
            <p className="text-xs text-gray-500">
              Distribution of capital, market valuation weights, and unrealized return contributions across economic sectors.
            </p>
          </div>
        </div>

        <span className="text-xs font-mono text-gray-400">
          {sectors.length} {sectors.length === 1 ? 'Sector' : 'Sectors'} Identified
        </span>
      </div>

      <div className="p-5">
        {isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Aggregating sector-level valuations and cost basis...</span>
            </div>
          </div>
        ) : sectors.length === 0 ? (
          <div
            data-testid="no-sectors-message"
            className="py-8 text-center text-gray-400 text-xs flex flex-col items-center justify-center space-y-1.5"
          >
            <Building2 className="w-8 h-8 text-gray-300" />
            <p className="font-semibold text-gray-600">No sector allocation data available</p>
            <p className="text-gray-400">Holdings do not have assigned sectors or portfolio is empty.</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-5 -mb-5">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-50/80 border-y border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[11px]">
                  <th scope="col" className="py-3 px-5">Sector</th>
                  <th scope="col" className="py-3 px-3 text-center">Positions</th>
                  <th scope="col" className="py-3 px-3 text-right">Market Value</th>
                  <th scope="col" className="py-3 px-3 text-right">Allocation %</th>
                  <th scope="col" className="py-3 px-3 text-right">Cost Basis</th>
                  <th scope="col" className="py-3 px-3 text-right">Cost Weight</th>
                  <th scope="col" className="py-3 px-3 text-right">Unrealized P/L</th>
                  <th scope="col" className="py-3 px-5 text-right">P/L %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sectors.map((sec) => {
                  const pnlNum = typeof sec.unrealized_pnl === 'string'
                    ? parseFloat(sec.unrealized_pnl)
                    : sec.unrealized_pnl;
                  const isPositive = pnlNum !== null && pnlNum !== undefined && pnlNum > 0;
                  const isNegative = pnlNum !== null && pnlNum !== undefined && pnlNum < 0;

                  return (
                    <tr
                      key={sec.sector}
                      data-testid={`sector-row-${sec.sector}`}
                      className="hover:bg-gray-50/60 transition-colors"
                    >
                      <td className="py-3 px-5 font-semibold text-gray-900">
                        {sec.sector}
                      </td>
                      <td className="py-3 px-3 text-center font-mono text-gray-600">
                        {sec.unpriced_count > 0 ? (
                          <span
                            title={`${sec.priced_count} priced, ${sec.unpriced_count} unpriced`}
                            className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded text-[11px] font-medium"
                          >
                            {sec.priced_count}/{sec.holdings_count}
                          </span>
                        ) : (
                          <span>{sec.holdings_count}</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-medium text-gray-900">
                        {formatCurrency(sec.market_value)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-gray-900">
                        {formatPercent(sec.allocation_percent)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-gray-600">
                        {formatCurrency(sec.cost_basis)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-gray-600">
                        {formatPercent(sec.cost_basis_weight_percent)}
                      </td>
                      <td
                        className={`py-3 px-3 text-right font-mono font-semibold ${
                          isPositive
                            ? 'text-emerald-600'
                            : isNegative
                            ? 'text-rose-600'
                            : 'text-gray-600'
                        }`}
                      >
                        {formatCurrency(sec.unrealized_pnl)}
                      </td>
                      <td
                        className={`py-3 px-5 text-right font-mono font-semibold ${
                          isPositive
                            ? 'text-emerald-600'
                            : isNegative
                            ? 'text-rose-600'
                            : 'text-gray-600'
                        }`}
                      >
                        {formatPercent(sec.unrealized_pnl_percent)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
