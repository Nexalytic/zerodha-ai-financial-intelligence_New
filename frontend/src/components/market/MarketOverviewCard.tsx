import React from 'react';
import { Quote } from '../../types/marketData';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import {
  TrendingUp,
  TrendingDown,
  Clock,
  Sparkles,
  HelpCircle,
} from 'lucide-react';

export interface MarketOverviewCardProps {
  quotes: Record<string, Quote>;
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  isLoading: boolean;
}

export const MarketOverviewCard: React.FC<MarketOverviewCardProps> = ({
  quotes,
  selectedSymbol,
  onSelectSymbol,
  isLoading,
}) => {
  const quoteList = Object.values(quotes);

  const getStatusBadge = (quote: Quote) => {
    if (quote.status === 'ERROR') {
      return (
        <span
          data-testid={`quote-status-${quote.symbol}`}
          className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200"
        >
          ERROR
        </span>
      );
    }
    if (quote.status === 'UNAVAILABLE' || quote.current_price === null) {
      return (
        <span
          data-testid={`quote-status-${quote.symbol}`}
          className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200"
        >
          UNAVAILABLE
        </span>
      );
    }
    if (quote.is_stale) {
      return (
        <span
          data-testid={`quote-status-${quote.symbol}`}
          className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200"
        >
          STALE
        </span>
      );
    }
    return (
      <span
        data-testid={`quote-status-${quote.symbol}`}
        className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"
      >
        AVAILABLE
      </span>
    );
  };

  return (
    <div
      data-testid="market-overview-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Market Quote Overview &amp; Movements
            </h2>
            <p className="text-xs text-gray-500">
              Multi-asset price quotes, daily changes, cache freshness, and simulated provenance disclosures.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span
            data-testid="simulated-quotes-badge"
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>Simulated Demo Pricing</span>
          </span>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* End-of-Day / Simulated Transparency Disclosure */}
        <div
          data-testid="simulated-feed-banner"
          className="p-3 rounded-lg bg-blue-50/70 border border-blue-200 text-xs text-blue-900 flex items-start space-x-2.5"
        >
          <Clock className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <p className="leading-relaxed text-[11px]">
            <strong className="text-blue-950">Demonstration market feeds are active:</strong>{' '}
            Quotes reflect synthetic educational market data generated with deterministic pricing models. Market quotes are never labeled as real-time when served from historical baseline snapshots or simulated feeds.
          </p>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Fetching live simulated market quotes and exchange snapshots...</span>
            </div>
          </div>
        ) : quoteList.length === 0 ? (
          <div
            data-testid="no-quotes-message"
            className="py-8 text-center text-gray-400 text-xs flex flex-col items-center justify-center space-y-1.5"
          >
            <HelpCircle className="w-8 h-8 text-gray-300" />
            <p className="font-semibold text-gray-600">No market quotes available</p>
            <p className="text-gray-400">Add portfolio positions or select watch symbols to view quote feeds.</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-5 -mb-5">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-50/80 border-y border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[11px]">
                  <th scope="col" className="py-3 px-5">Symbol</th>
                  <th scope="col" className="py-3 px-3">Exchange</th>
                  <th scope="col" className="py-3 px-3 text-right">Price</th>
                  <th scope="col" className="py-3 px-3 text-right">Change</th>
                  <th scope="col" className="py-3 px-3 text-right">% Change</th>
                  <th scope="col" className="py-3 px-3 text-center">Status</th>
                  <th scope="col" className="py-3 px-3 text-center">Cache</th>
                  <th scope="col" className="py-3 px-5">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {quoteList.map((quote) => {
                  const isSelected = quote.symbol.toUpperCase() === selectedSymbol.toUpperCase();
                  const changeNum =
                    typeof quote.change === 'string' ? parseFloat(quote.change) : quote.change;
                  const isPositive = changeNum !== null && changeNum !== undefined && changeNum > 0;
                  const isNegative = changeNum !== null && changeNum !== undefined && changeNum < 0;

                  return (
                    <tr
                      key={`${quote.symbol}-${quote.exchange}`}
                      data-testid={`quote-row-${quote.symbol}`}
                      onClick={() => onSelectSymbol(quote.symbol)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-blue-50/70 hover:bg-blue-50'
                          : 'hover:bg-gray-50/60'
                      }`}
                    >
                      <td className="py-3 px-5 font-bold text-gray-900">
                        <div className="flex items-center space-x-1.5">
                          <span>{quote.symbol}</span>
                          {isSelected && (
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 font-mono text-gray-600">
                        {quote.exchange}
                      </td>
                      <td
                        data-testid={`quote-price-${quote.symbol}`}
                        className="py-3 px-3 text-right font-mono font-bold text-gray-900"
                      >
                        {formatCurrency(quote.current_price)}
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
                        <span className="inline-flex items-center justify-end space-x-0.5">
                          {isPositive && <TrendingUp className="w-3 h-3 mr-0.5 inline" />}
                          {isNegative && <TrendingDown className="w-3 h-3 mr-0.5 inline" />}
                          <span>{formatCurrency(quote.change)}</span>
                        </span>
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
                        {formatPercent(quote.change_percent)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {getStatusBadge(quote)}
                      </td>
                      <td
                        data-testid={`quote-cache-${quote.symbol}`}
                        className="py-3 px-3 text-center"
                      >
                        {quote.is_stale ? (
                          <span
                            data-testid={`quote-stale-${quote.symbol}`}
                            className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200"
                          >
                            STALE
                          </span>
                        ) : quote.cache_hit ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-gray-100 text-gray-600 border border-gray-200">
                            HIT
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-gray-50 text-gray-400">
                            MISS
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-5 text-gray-500 font-mono text-[11px]">
                        <span className="truncate max-w-[140px] block" title={quote.source}>
                          {quote.source}
                        </span>
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
