import React, { useEffect, useState, useCallback, useRef } from 'react';
import { usePortfolio } from '../../context/PortfolioContext';
import { fetchQuote, fetchBatchQuotes } from '../../api/marketData';
import { fetchNews } from '../../api/news';
import { generateAIPortfolioInsights } from '../../api/aiReasoning';
import { Quote, NewsResponse } from '../../types/marketData';
import { AIInsightReport } from '../../types/aiReasoning';
import { parseApiError } from '../../api/client';
import { MarketOverviewCard } from './MarketOverviewCard';
import { StockInspectorCard } from './StockInspectorCard';
import { MarketNewsSection } from './MarketNewsSection';
import { AIExplanationSection } from './AIExplanationSection';
import {
  TrendingUp,
  RefreshCw,
  ChevronDown,
} from 'lucide-react';

const DEFAULT_SYMBOLS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'];

export const MarketMovementExplainer: React.FC = () => {
  const {
    portfolios,
    activePortfolioId,
    activePortfolio,
    setActivePortfolioId,
    refreshPortfolios,
    isLoading: isContextLoading,
  } = usePortfolio();

  // State: Symbols and Selection
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE');
  const [selectedExchange, setSelectedExchange] = useState<string>('NSE');
  const [isFilteredBySymbol, setIsFilteredBySymbol] = useState<boolean>(true);

  // State: Market Data & AI
  const [batchQuotes, setBatchQuotes] = useState<Record<string, Quote>>({});
  const [singleQuote, setSingleQuote] = useState<Quote | null>(null);
  const [newsResponse, setNewsResponse] = useState<NewsResponse | null>(null);
  const [aiReport, setAiReport] = useState<AIInsightReport | null>(null);

  // Loading States
  const [isLoadingBatch, setIsLoadingBatch] = useState<boolean>(false);
  const [isLoadingSingle, setIsLoadingSingle] = useState<boolean>(false);
  const [isLoadingNews, setIsLoadingNews] = useState<boolean>(false);
  const [isGeneratingAI, setIsGeneratingAI] = useState<boolean>(false);

  // Error States
  const [singleError, setSingleError] = useState<string | null>(null);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  // Request-Generation Race Refs
  const symbolRequestIdRef = useRef<number>(0);
  const newsRequestIdRef = useRef<number>(0);
  const aiRequestIdRef = useRef<number>(0);

  // Derive symbols list from default bluechips
  const availableSymbols = DEFAULT_SYMBOLS;

  // 1. Load Single Quote
  const loadSingleQuote = useCallback(async (sym: string, exch: string) => {
    const reqId = ++symbolRequestIdRef.current;
    setIsLoadingSingle(true);
    setSingleError(null);

    try {
      const q = await fetchQuote(sym, exch);
      if (reqId === symbolRequestIdRef.current) {
        setSingleQuote(q);
      }
    } catch (err: unknown) {
      if (reqId === symbolRequestIdRef.current) {
        const parsed = parseApiError(err);
        setSingleError(parsed.message || `Failed to fetch quote for ${sym}.`);
        setSingleQuote(null);
      }
    } finally {
      if (reqId === symbolRequestIdRef.current) {
        setIsLoadingSingle(false);
      }
    }
  }, []);

  // 2. Load News Articles
  const loadNews = useCallback(async (sym: string, filterBySym: boolean) => {
    const reqId = ++newsRequestIdRef.current;
    setIsLoadingNews(true);
    setNewsError(null);

    try {
      const filterSymbols = filterBySym ? [sym] : undefined;
      const res = await fetchNews(filterSymbols, 10);
      if (reqId === newsRequestIdRef.current) {
        setNewsResponse(res);
      }
    } catch (err: unknown) {
      if (reqId === newsRequestIdRef.current) {
        const parsed = parseApiError(err);
        setNewsError(parsed.message || 'Failed to fetch financial news.');
        setNewsResponse(null);
      }
    } finally {
      if (reqId === newsRequestIdRef.current) {
        setIsLoadingNews(false);
      }
    }
  }, []);

  // 3. Load Batch Quotes
  const loadBatchQuotes = useCallback(async (syms: string[], exch: string) => {
    setIsLoadingBatch(true);
    try {
      const res = await fetchBatchQuotes(syms, exch);
      if (res?.quotes) {
        setBatchQuotes(res.quotes);
      }
    } catch {
      // Fallback: batch failure shouldn't crash page
    } finally {
      setIsLoadingBatch(false);
    }
  }, []);

  // Effect: When selected symbol or exchange changes
  useEffect(() => {
    loadSingleQuote(selectedSymbol, selectedExchange);
  }, [selectedSymbol, selectedExchange, loadSingleQuote]);

  // Effect: When news filter or symbol changes
  useEffect(() => {
    loadNews(selectedSymbol, isFilteredBySymbol);
  }, [selectedSymbol, isFilteredBySymbol, loadNews]);

  // Effect: Initial batch quotes
  useEffect(() => {
    loadBatchQuotes(availableSymbols, selectedExchange);
  }, [availableSymbols, selectedExchange, loadBatchQuotes]);

  // Effect: Reset AI Report when active portfolio changes
  useEffect(() => {
    aiRequestIdRef.current++;
    setIsGeneratingAI(false);
    setAiReport(null);
    setAiError(null);
  }, [activePortfolioId]);

  // Handlers
  const handleSelectSymbol = (sym: string) => {
    const cleanSym = sym.trim().toUpperCase();
    setSelectedSymbol(cleanSym);
  };

  const handleSelectExchange = (exch: string) => {
    setSelectedExchange(exch);
  };

  const handleToggleNewsFilter = (filterBySym: boolean) => {
    setIsFilteredBySymbol(filterBySym);
  };

  const handleRefresh = async () => {
    await refreshPortfolios();
    await Promise.allSettled([
      loadBatchQuotes(availableSymbols, selectedExchange),
      loadSingleQuote(selectedSymbol, selectedExchange),
      loadNews(selectedSymbol, isFilteredBySymbol),
    ]);
  };

  const handleGenerateAI = async () => {
    if (!activePortfolioId) return;
    const aiReqId = ++aiRequestIdRef.current;
    const targetPortfolioId = activePortfolioId;
    setIsGeneratingAI(true);
    setAiError(null);

    try {
      const report = await generateAIPortfolioInsights(targetPortfolioId, {
        include_news: true,
        news_limit: 10,
      });

      if (aiReqId === aiRequestIdRef.current && activePortfolioId === targetPortfolioId) {
        setAiReport(report);
      }
    } catch (err: unknown) {
      if (aiReqId === aiRequestIdRef.current && activePortfolioId === targetPortfolioId) {
        const parsed = parseApiError(err);
        setAiError(parsed.message || 'AI reasoning engine failed to synthesize movement insights.');
      }
    } finally {
      if (aiReqId === aiRequestIdRef.current) {
        setIsGeneratingAI(false);
      }
    }
  };

  // Initial Context Loading
  if (isContextLoading && portfolios.length === 0) {
    return (
      <section
        role="tabpanel"
        id="tabpanel-market"
        aria-labelledby="tab-market"
        data-testid="market-movement-loading"
        className="py-16 text-center text-gray-500"
      >
        <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm font-semibold text-gray-800">Connecting to Market Movement Service...</p>
        <p className="text-xs text-gray-400 mt-1">Retrieving quote caches, exchange feeds, and financial news</p>
      </section>
    );
  }

  return (
    <section
      role="tabpanel"
      id="tabpanel-market"
      aria-labelledby="tab-market"
      data-testid="market-movement-explainer"
      className="space-y-6"
    >
      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-gray-900 tracking-tight">
                Market Movement Explainer
              </h1>
              {activePortfolio?.is_sample && (
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                  Demo Active
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">
              Simulated price movements, ticker inspector, financial sentiment news, and fact-grounded AI attribution.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 self-end sm:self-auto">
          {/* Portfolio Selector (if portfolios exist) */}
          {portfolios.length > 0 && (
            <div className="relative inline-flex items-center">
              <label htmlFor="market-portfolio-select" className="sr-only">
                Select portfolio
              </label>
              <select
                id="market-portfolio-select"
                aria-label="Select portfolio for market analysis"
                value={activePortfolioId || ''}
                onChange={(e) => setActivePortfolioId(e.target.value)}
                className="appearance-none bg-white text-xs font-medium text-gray-800 border border-gray-300 rounded-lg pl-3 pr-8 py-1.5 hover:border-gray-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs"
              >
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.holdings_count} pos)
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2.5 pointer-events-none" />
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            data-testid="refresh-market-btn"
            aria-label="Refresh market quotes and news"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 rounded-lg text-xs font-medium shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${
                isLoadingBatch || isLoadingSingle || isLoadingNews ? 'animate-spin' : ''
              }`}
            />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 1. Market Overview: Multi-asset Quote Table */}
      <MarketOverviewCard
        quotes={batchQuotes}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={handleSelectSymbol}
        isLoading={isLoadingBatch}
      />

      {/* 2. Stock Inspector: Deep-Dive into Selected Symbol */}
      <StockInspectorCard
        quote={singleQuote}
        symbols={availableSymbols}
        selectedSymbol={selectedSymbol}
        selectedExchange={selectedExchange}
        onSelectSymbol={handleSelectSymbol}
        onSelectExchange={handleSelectExchange}
        isLoading={isLoadingSingle}
        error={singleError}
      />

      {/* 3. Financial News & Sentiment Feed */}
      <MarketNewsSection
        newsResponse={newsResponse}
        selectedSymbol={selectedSymbol}
        isFilteredBySymbol={isFilteredBySymbol}
        onToggleFilter={handleToggleNewsFilter}
        onSelectSymbol={handleSelectSymbol}
        isLoading={isLoadingNews}
        error={newsError}
      />

      {/* 4. Evidence-Grounded AI Movement Attribution */}
      <AIExplanationSection
        aiReport={aiReport && aiReport.portfolio_id === activePortfolio?.id ? aiReport : null}
        portfolioId={activePortfolio?.id || null}
        portfolioName={activePortfolio?.name}
        isGenerating={isGeneratingAI}
        error={aiError}
        onGenerate={handleGenerateAI}
      />

      {/* Educational & Non-Trading Disclaimer */}
      <div
        data-testid="market-explainer-disclaimer"
        className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-500 leading-relaxed text-center"
      >
        <p className="font-semibold text-gray-700">
          Educational market intelligence and attribution analysis only.
        </p>
        <p className="mt-1">
          This platform is strictly an educational financial analytics engine. It contains no order placement forms, broker trade execution capabilities, or individual buy/sell recommendations.
        </p>
      </div>
    </section>
  );
};
