import React from 'react';
import { Quote } from '../../types/marketData';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import {
  Search,
  Clock,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Info,
  AlertCircle,
  ChevronDown,
} from 'lucide-react';

export interface StockInspectorCardProps {
  quote: Quote | null;
  symbols: string[];
  selectedSymbol: string;
  selectedExchange: string;
  onSelectSymbol: (symbol: string) => void;
  onSelectExchange: (exchange: string) => void;
  isLoading: boolean;
  error: string | null;
}

export const StockInspectorCard: React.FC<StockInspectorCardProps> = ({
  quote,
  symbols,
  selectedSymbol,
  selectedExchange,
  onSelectSymbol,
  onSelectExchange,
  isLoading,
  error,
}) => {
  const isAvailable =
    quote?.status === 'AVAILABLE' &&
    quote?.current_price !== null &&
    quote?.current_price !== undefined;
  const changeNum =
    typeof quote?.change === 'string' ? parseFloat(quote.change) : quote?.change;
  const isPositive = changeNum !== null && changeNum !== undefined && changeNum > 0;
  const isNegative = changeNum !== null && changeNum !== undefined && changeNum < 0;

  return (
    <div
      data-testid="stock-inspector-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header & Symbol Selector */}
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <Search className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Single Stock Quote Inspector
            </h2>
            <p className="text-xs text-gray-500">
              Detailed inspection of individual ticker pricing, spread baselines, and cache latency.
            </p>
          </div>
        </div>

        {/* Controls: Symbol & Exchange Selectors */}
        <div className="flex items-center space-x-2">
          {/* Symbol Select */}
          <div className="relative inline-flex items-center">
            <label htmlFor="inspector-symbol-select" className="sr-only">
              Select stock symbol
            </label>
            <select
              id="inspector-symbol-select"
              data-testid="symbol-select"
              aria-label="Select stock symbol"
              value={selectedSymbol}
              onChange={(e) => onSelectSymbol(e.target.value)}
              className="appearance-none bg-white text-xs font-bold text-gray-900 border border-gray-300 rounded-lg pl-3 pr-8 py-1.5 hover:border-gray-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs"
            >
              {symbols.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2.5 pointer-events-none" />
          </div>

          {/* Exchange Select */}
          <div className="relative inline-flex items-center">
            <label htmlFor="inspector-exchange-select" className="sr-only">
              Select exchange
            </label>
            <select
              id="inspector-exchange-select"
              data-testid="exchange-select"
              aria-label="Select exchange"
              value={selectedExchange}
              onChange={(e) => onSelectExchange(e.target.value)}
              className="appearance-none bg-white text-xs font-mono text-gray-700 border border-gray-300 rounded-lg pl-2.5 pr-7 py-1.5 hover:border-gray-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs"
            >
              <option value="NSE">NSE</option>
              <option value="BSE">BSE</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2 pointer-events-none" />
          </div>
        </div>
      </div>

      <div className="p-5 space-y-6">
        {error ? (
          <div
            data-testid="inspector-error-banner"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Failed to fetch quote for {selectedSymbol}</p>
              <p className="mt-0.5 text-rose-700">{error}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Fetching quote for {selectedSymbol} ({selectedExchange})...</span>
            </div>
          </div>
        ) : !quote ? (
          <div className="py-8 text-center text-gray-400 text-xs">
            No quote data available for {selectedSymbol}.
          </div>
        ) : !isAvailable ? (
          <div
            data-testid="inspector-unavailable-notice"
            className="p-6 rounded-lg bg-amber-50/70 border border-amber-200 text-center space-y-2"
          >
            <AlertTriangle className="w-8 h-8 text-amber-600 mx-auto" />
            <h3 className="text-sm font-bold text-amber-900">
              Quote Unavailable for {quote.symbol} ({quote.exchange})
            </h3>
            <p className="text-xs text-amber-800 max-w-md mx-auto leading-relaxed">
              {quote.explanation ||
                'Market price could not be retrieved from provider. Prices are not fabricated or assumed as zero.'}
            </p>
            <div className="pt-2 flex items-center justify-center space-x-2 text-[11px] font-mono text-amber-700">
              <span>Status: {quote.status}</span>
              <span>&bull;</span>
              <span>Source: {quote.source}</span>
            </div>
          </div>
        ) : (
          <>
            {/* Primary Quote Display */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Price */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Current Price
                </span>
                <div
                  data-testid="inspector-price"
                  className="text-3xl font-extrabold text-gray-900 tracking-tight"
                >
                  {formatCurrency(quote.current_price)}
                </div>
                <p className="text-[11px] text-gray-500">
                  {quote.symbol} &bull; {quote.exchange}
                </p>
              </div>

              {/* Absolute Change */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Net Change
                </span>
                <div
                  data-testid="inspector-change"
                  className={`text-2xl font-bold ${
                    isPositive
                      ? 'text-emerald-600'
                      : isNegative
                      ? 'text-rose-600'
                      : 'text-gray-900'
                  }`}
                >
                  <span className="inline-flex items-center space-x-1">
                    {isPositive && <TrendingUp className="w-5 h-5 inline mr-1" />}
                    {isNegative && <TrendingDown className="w-5 h-5 inline mr-1" />}
                    <span>{formatCurrency(quote.change)}</span>
                  </span>
                </div>
                <p className="text-[11px] text-gray-500">
                  Difference from baseline price
                </p>
              </div>

              {/* Percentage Change */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Percent Change
                </span>
                <div
                  data-testid="inspector-change-percent"
                  className={`text-2xl font-bold ${
                    isPositive
                      ? 'text-emerald-600'
                      : isNegative
                      ? 'text-rose-600'
                      : 'text-gray-900'
                  }`}
                >
                  {formatPercent(quote.change_percent)}
                </div>
                <p className="text-[11px] text-gray-500">
                  Daily relative movement
                </p>
              </div>

              {/* Cache / Latency Indicator */}
              <div className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Cache Performance
                </span>
                <div className="flex items-center space-x-2 pt-0.5">
                  <span
                    data-testid="inspector-status"
                    className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
                      quote.cache_hit
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-gray-100 text-gray-700 border border-gray-200'
                    }`}
                  >
                    {quote.cache_hit ? 'CACHE HIT' : 'CACHE MISS'}
                  </span>
                  {quote.ttl_remaining_seconds !== null &&
                    quote.ttl_remaining_seconds !== undefined && (
                      <span className="text-xs font-mono text-gray-500">
                        TTL: {Math.round(quote.ttl_remaining_seconds)}s
                      </span>
                    )}
                </div>
                <p className="text-[11px] text-gray-500 pt-0.5">
                  Sub-millisecond local SQLite cache
                </p>
              </div>
            </div>

            {/* Stale Warning Banner */}
            {quote.is_stale && (
              <div
                data-testid="inspector-stale-warning"
                className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start space-x-2.5"
              >
                <Clock className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Emergency Stale Cache Quote</p>
                  <p className="mt-0.5 text-amber-800 text-[11px]">
                    This quote was served from the emergency cache fallback due to provider limits or connectivity timeout.
                  </p>
                </div>
              </div>
            )}

            {/* Metadata & Timestamps Audit */}
            <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-200 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-gray-600">
              <div>
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Quote Generated At
                </span>
                <span className="font-mono text-[11px] text-gray-600 mt-0.5 block">
                  {quote.generated_at || '—'}
                </span>
              </div>
              <div>
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Market As-Of Observation
                </span>
                <span className="font-mono text-[11px] text-gray-600 mt-0.5 block">
                  {quote.market_as_of || 'Strictly null (Simulated Feed)'}
                </span>
              </div>
              <div>
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Originating Source
                </span>
                <span
                  data-testid="inspector-source"
                  className="font-mono text-[11px] text-gray-700 mt-0.5 block truncate"
                  title={quote.source}
                >
                  {quote.source}
                </span>
              </div>
            </div>

            {/* Non-Trading Disclosure */}
            <div className="p-3 rounded-lg bg-blue-50/60 border border-blue-200 flex items-start space-x-2 text-xs text-blue-900">
              <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                <strong className="text-blue-950">Non-Trading Disclosure:</strong>{' '}
                This platform is strictly an educational financial analytics engine. It contains no order placement forms, broker trade execution capabilities, or individual buy/sell recommendations.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
