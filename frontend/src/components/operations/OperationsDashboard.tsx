import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  RefreshCw,
  Server,
  Radio,
  ShieldCheck,
  AlertCircle,
  Layers,
  Clock,
  Cpu,
  HelpCircle,
} from 'lucide-react';
import { HealthIndicator } from '../HealthIndicator';
import { fetchBatchQuotes } from '../../api/marketData';
import { BatchQuotesResponse, Quote } from '../../types/marketData';
import { formatCurrency } from '../../utils/formatters';

const BENCHMARK_WATCHLIST = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'];

export const OperationsDashboard: React.FC = () => {
  const [batchData, setBatchData] = useState<BatchQuotesResponse | null>(null);
  const [isMarketLoading, setIsMarketLoading] = useState<boolean>(true);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  // Request-generation counter to prevent out-of-order race conditions
  const requestIdRef = useRef<number>(0);

  const loadMarketTelemetry = useCallback(async () => {
    const currentRequestId = ++requestIdRef.current;
    setIsMarketLoading(true);
    setMarketError(null);

    try {
      const data = await fetchBatchQuotes(BENCHMARK_WATCHLIST, 'NSE');
      // Ignore late response if request was superseded
      if (requestIdRef.current === currentRequestId) {
        setBatchData(data);
        setIsMarketLoading(false);
      }
    } catch (err: any) {
      if (requestIdRef.current === currentRequestId) {
        const errorMsg =
          err?.response?.data?.message ||
          err?.message ||
          'Failed to retrieve market-data cache telemetry.';
        setMarketError(errorMsg);
        setIsMarketLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadMarketTelemetry();
  }, [loadMarketTelemetry]);

  const handleGlobalRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
    loadMarketTelemetry();
  };

  // Derive cache metrics and provenance safely from actual response
  const quotesList: Quote[] = batchData ? Object.values(batchData.quotes) : [];
  const totalSymbols = batchData?.total_symbols ?? 0;
  const cacheHits = batchData?.cache_hits_count ?? 0;

  // Calculate hit ratio strictly when denominator > 0; otherwise display unavailable marker '—'
  const hitRatio =
    totalSymbols > 0
      ? `${((cacheHits / totalSymbols) * 100).toFixed(1)}%`
      : '—';

  // Derive active provider source dynamically from actual quote objects
  const uniqueSources = Array.from(
    new Set(quotesList.map((q) => q.source).filter(Boolean))
  );
  const derivedSource =
    uniqueSources.length === 1
      ? uniqueSources[0]
      : uniqueSources.length > 1
      ? uniqueSources.join(', ')
      : '—';

  const hasSimulated = quotesList.some((q) => q.is_simulated);
  const hasStaleFallback = quotesList.some((q) => q.is_stale);

  return (
    <section
      role="tabpanel"
      aria-label="Operations"
      data-testid="operations-dashboard"
      className="space-y-6"
    >
      {/* 1. Header & Global Refresh Action */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                  Operations Dashboard
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Telemetry Live</span>
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Real-time API health, SQLite database engine state, market-data cache performance, and zero-cost governance.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleGlobalRefresh}
              aria-busy={isMarketLoading}
              data-testid="global-refresh-btn"
              aria-label="Refresh All Telemetry"
              className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isMarketLoading ? 'animate-spin' : ''}`}
              />
              <span>{isMarketLoading ? 'Refreshing...' : 'Refresh All Telemetry'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. System Health & Database Telemetry (Reusing HealthIndicator) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center space-x-1.5">
            <Server className="w-3.5 h-3.5" />
            <span>API Server &amp; Database Engine Status</span>
          </h3>
        </div>
        <HealthIndicator refreshTrigger={refreshTrigger} />
      </div>

      {/* 3. Market-Data Provider & Cache Performance Telemetry */}
      <div
        data-testid="market-telemetry-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
              <Radio className="w-4 h-4 text-blue-600" />
              <span>Market-Data Provider &amp; Cache Performance</span>
            </h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Live batch metrics for benchmark NSE watchlist (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK).
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            {hasSimulated && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                Simulated Data Mode
              </span>
            )}
            <span
              data-testid="stale-fallback-status"
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                hasStaleFallback
                  ? 'bg-amber-100 text-amber-900 border border-amber-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {hasStaleFallback ? 'Stale Fallback Active' : 'All Quotes Fresh'}
            </span>
          </div>
        </div>

        {/* Loading State for Market Data */}
        {isMarketLoading && !batchData && (
          <div
            role="status"
            aria-busy="true"
            data-testid="market-loading-state"
            className="py-10 text-center text-gray-500 text-xs space-y-2"
          >
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mx-auto" />
            <p className="font-semibold text-gray-800">
              Querying market-data quotes and cache statistics...
            </p>
            <p className="text-gray-400 text-[11px]">
              Inspecting in-memory TTL buffers and provider quote states.
            </p>
          </div>
        )}

        {/* Error State for Market Data */}
        {!isMarketLoading && marketError && (
          <div
            role="alert"
            data-testid="market-error-banner"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2.5"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="font-bold text-rose-900">
                Market Telemetry Retrieval Failed
              </p>
              <p className="text-rose-700">{marketError}</p>
              <div className="pt-1.5">
                <button
                  onClick={loadMarketTelemetry}
                  data-testid="retry-market-btn"
                  className="px-3 py-1 bg-rose-600 text-white rounded text-[11px] font-semibold hover:bg-rose-700 cursor-pointer transition shadow-2xs"
                >
                  Retry Market Telemetry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Loaded Market Data Content */}
        {batchData && (
          <div className="space-y-4">
            {/* Telemetry Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Cache Hits
                </span>
                <p
                  data-testid="cache-hits-count"
                  className="text-xl font-bold text-emerald-600 mt-0.5"
                >
                  {batchData.cache_hits_count}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Cache Misses
                </span>
                <p
                  data-testid="cache-misses-count"
                  className="text-xl font-bold text-gray-700 mt-0.5"
                >
                  {batchData.cache_misses_count}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Batch Hit Ratio
                </span>
                <p
                  data-testid="cache-hit-ratio"
                  className="text-xl font-bold text-blue-600 mt-0.5"
                >
                  {hitRatio}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Active Provider Source
                </span>
                <p
                  data-testid="active-provider-name"
                  className="text-xs font-mono font-bold text-gray-900 mt-1 truncate"
                  title={derivedSource}
                >
                  {derivedSource}
                </p>
              </div>
            </div>

            {/* Benchmark Quotes Telemetry Table */}
            {quotesList.length > 0 ? (
              <div className="border border-gray-200 rounded-lg overflow-x-auto">
                <table
                  data-testid="quotes-telemetry-table"
                  className="min-w-full divide-y divide-gray-200 text-xs text-left"
                >
                  <thead className="bg-gray-50 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    <tr>
                      <th className="px-3.5 py-2.5">Symbol</th>
                      <th className="px-3.5 py-2.5">Price (INR)</th>
                      <th className="px-3.5 py-2.5">Status</th>
                      <th className="px-3.5 py-2.5">Cache</th>
                      <th className="px-3.5 py-2.5">Remaining TTL</th>
                      <th className="px-3.5 py-2.5">Stale Flag</th>
                      <th className="px-3.5 py-2.5">Source</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {quotesList.map((q) => {
                      const hasPrice =
                        q.current_price !== null &&
                        q.current_price !== undefined &&
                        q.status === 'AVAILABLE';

                      return (
                        <tr
                          key={q.symbol}
                          data-testid={`quote-row-${q.symbol}`}
                          className="hover:bg-gray-50/70 transition"
                        >
                          <td className="px-3.5 py-2 font-mono font-bold text-gray-900">
                            {q.symbol}
                            <span className="text-[10px] text-gray-400 font-sans ml-1">
                              ({q.exchange})
                            </span>
                          </td>
                          <td
                            data-testid={`quote-price-${q.symbol}`}
                            className="px-3.5 py-2 font-mono"
                          >
                            {hasPrice ? formatCurrency(q.current_price) : '—'}
                          </td>
                          <td
                            data-testid={`quote-status-${q.symbol}`}
                            className="px-3.5 py-2"
                          >
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                                q.status === 'AVAILABLE'
                                  ? 'bg-emerald-50 text-emerald-700'
                                  : q.status === 'UNAVAILABLE'
                                  ? 'bg-amber-50 text-amber-700'
                                  : 'bg-rose-50 text-rose-700'
                              }`}
                            >
                              {q.status}
                            </span>
                            {q.explanation && (
                              <p className="text-[10px] text-gray-500 mt-0.5 max-w-xs">
                                {q.explanation}
                              </p>
                            )}
                          </td>
                          <td
                            data-testid={`quote-cache-${q.symbol}`}
                            className="px-3.5 py-2 font-mono"
                          >
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                q.cache_hit
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {q.cache_hit ? 'HIT' : 'MISS'}
                            </span>
                          </td>
                          <td
                            data-testid={`quote-ttl-${q.symbol}`}
                            className="px-3.5 py-2 font-mono text-gray-600"
                          >
                            {q.ttl_remaining_seconds !== null &&
                            q.ttl_remaining_seconds !== undefined
                              ? `${Math.round(q.ttl_remaining_seconds)}s`
                              : '—'}
                          </td>
                          <td
                            data-testid={`quote-stale-${q.symbol}`}
                            className="px-3.5 py-2 font-mono"
                          >
                            {q.is_stale ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
                                STALE
                              </span>
                            ) : (
                              <span className="text-gray-400 text-[10px]">Fresh</span>
                            )}
                          </td>
                          <td
                            data-testid={`quote-source-${q.symbol}`}
                            className="px-3.5 py-2 font-mono text-[11px] text-gray-500 truncate max-w-xs"
                            title={q.source}
                          >
                            {q.source}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div
                data-testid="empty-quotes-notice"
                className="py-8 text-center text-gray-400 text-xs flex flex-col items-center justify-center space-y-1.5"
              >
                <HelpCircle className="w-8 h-8 text-gray-300" />
                <p className="font-semibold text-gray-600">
                  No quote records returned for benchmark symbols
                </p>
                <p className="text-gray-400">
                  Verify market-data service availability and symbol parameters.
                </p>
              </div>
            )}

            {/* Scope Notice for Cache Telemetry */}
            <div
              data-testid="cache-scope-notice"
              className="p-3 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-500 flex items-start space-x-2"
            >
              <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-gray-700">
                  Point-in-Time Batch Snapshot Disclosure
                </p>
                <p className="mt-0.5 leading-relaxed">
                  Metrics reflect the latest batch quote request assembled at{' '}
                  <span className="font-mono text-gray-800">
                    {new Date(batchData.fetched_at).toLocaleTimeString()}
                  </span>
                  . This represents live in-memory cache status for the current session, not persistent long-term historical performance monitoring.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. AI Operating Mode & Governance */}
      <div
        data-testid="ai-governance-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-3"
      >
        <div className="flex items-center space-x-2.5 pb-2 border-b border-gray-100">
          <Cpu className="w-4 h-4 text-purple-600" />
          <h3 className="text-sm font-bold text-gray-900">
            AI Operating Mode &amp; Zero-Cost Governance
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1.5">
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
              AI Provider Runtime Configuration
            </span>
            <p
              data-testid="ai-runtime-config-notice"
              className="text-xs font-mono font-semibold text-gray-800"
            >
              Runtime configuration not exposed by the current API
            </p>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              The backend does not expose dynamic LLM provider settings via open REST endpoints. AI reasoning operations execute on demand under server-managed policies.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-emerald-50/60 border border-emerald-200 space-y-1.5">
            <div className="flex items-center space-x-1.5 text-emerald-900 font-bold text-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Zero-Cost Policy Enforcement Active</span>
            </div>
            <p className="text-[11px] text-emerald-800 leading-relaxed">
              Current system environment enforces deterministic zero-additional-spend guarantees. No billable third-party LLM inference or paid market-data subscriptions are required or active.
            </p>
          </div>
        </div>
      </div>

      {/* 5. Honest Operational Boundaries */}
      <div
        data-testid="operational-limitations-notice"
        className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-[11px] text-gray-500 space-y-1"
      >
        <div className="flex items-center space-x-1.5 text-gray-700 font-bold">
          <Layers className="w-3.5 h-3.5 text-gray-500" />
          <span>Operational Observability Boundaries</span>
        </div>
        <p className="leading-relaxed">
          Server uptime percentages, time-series request counters, cumulative error rates, provider SLAs, and historical FastMCP audit logs are not tracked or persisted by backend storage. All metrics shown are live, truthful point-in-time responses from supported API endpoints.
        </p>
      </div>
    </section>
  );
};
