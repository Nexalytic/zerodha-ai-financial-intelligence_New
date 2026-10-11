import React, { useEffect, useState, useCallback, useRef } from 'react';
import { usePortfolio } from '../../context/PortfolioContext';
import { fetchPortfolioAnalytics, fetchPortfolioInsights } from '../../api/analytics';
import { seedDemoPortfolio } from '../../api/portfolios';
import { PortfolioAnalyticsResponse } from '../../types/analytics';
import { PortfolioInsightsResponse } from '../../types/aiReasoning';
import { parseApiError } from '../../api/client';
import { RiskScoreCard } from './RiskScoreCard';
import { ConcentrationCard } from './ConcentrationCard';
import { SectorAllocationsCard } from './SectorAllocationsCard';
import { DataCompletenessCard } from './DataCompletenessCard';
import { HistoricalRiskCard } from './HistoricalRiskCard';
import { RiskInsightsSection } from './RiskInsightsSection';
import {
  ShieldAlert,
  RefreshCw,
  AlertCircle,
  Briefcase,
  Sparkles,
  ChevronDown,
} from 'lucide-react';

export const RiskExposurePanel: React.FC = () => {
  const {
    portfolios,
    activePortfolioId,
    activePortfolio,
    setActivePortfolioId,
    refreshPortfolios,
    isLoading: isContextLoading,
  } = usePortfolio();

  const [analytics, setAnalytics] = useState<PortfolioAnalyticsResponse | null>(null);
  const [insights, setInsights] = useState<PortfolioInsightsResponse | null>(null);
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState<boolean>(false);
  const [isLoadingInsights, setIsLoadingInsights] = useState<boolean>(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // Demo seeding state for empty state
  const [isSeedingDemo, setIsSeedingDemo] = useState<boolean>(false);
  const [seedError, setSeedError] = useState<string | null>(null);

  // Request-generation counter to prevent stale out-of-order responses
  const requestIdRef = useRef<number>(0);

  const loadData = useCallback(async (portfolioId: string) => {
    const requestId = ++requestIdRef.current;
    setIsLoadingAnalytics(true);
    setIsLoadingInsights(true);
    setAnalyticsError(null);
    setInsightsError(null);

    try {
      const [analyticsData, insightsData] = await Promise.allSettled([
        fetchPortfolioAnalytics(portfolioId),
        fetchPortfolioInsights(portfolioId),
      ]);

      // Discard response if a newer request has started
      if (requestId !== requestIdRef.current) {
        return;
      }

      if (analyticsData.status === 'fulfilled') {
        setAnalytics(analyticsData.value);
      } else {
        const parsed = parseApiError(analyticsData.reason);
        setAnalyticsError(parsed.message || 'Failed to load portfolio risk analytics.');
        setAnalytics(null);
      }

      if (insightsData.status === 'fulfilled') {
        setInsights(insightsData.value);
      } else {
        const parsed = parseApiError(insightsData.reason);
        setInsightsError(parsed.message || 'Failed to load portfolio risk insights.');
        setInsights(null);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoadingAnalytics(false);
        setIsLoadingInsights(false);
      }
    }
  }, []);

  useEffect(() => {
    if (activePortfolioId) {
      loadData(activePortfolioId);
    } else {
      setAnalytics(null);
      setInsights(null);
    }
  }, [activePortfolioId, loadData]);

  const handleRefresh = async () => {
    await refreshPortfolios();
    if (activePortfolioId) {
      await loadData(activePortfolioId);
    }
  };

  const handleSeedDemo = async () => {
    setIsSeedingDemo(true);
    setSeedError(null);
    try {
      const res = await seedDemoPortfolio();
      await refreshPortfolios();
      if (res?.portfolio?.id) {
        setActivePortfolioId(res.portfolio.id);
      }
    } catch (err: unknown) {
      const parsed = parseApiError(err);
      setSeedError(parsed.message || 'Failed to seed demo portfolio.');
    } finally {
      setIsSeedingDemo(false);
    }
  };

  // 1. Initial Context Loading State
  if (isContextLoading && portfolios.length === 0) {
    return (
      <section
        role="tabpanel"
        id="tabpanel-risk"
        aria-labelledby="tab-risk"
        data-testid="risk-panel-loading"
        className="py-16 text-center text-gray-500"
      >
        <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm font-semibold text-gray-800">Connecting to Risk &amp; Exposure Service...</p>
        <p className="text-xs text-gray-400 mt-1">Evaluating multi-factor structural risk models and quote completeness</p>
      </section>
    );
  }

  // 2. Empty State: No portfolios exist
  if (portfolios.length === 0 || !activePortfolio) {
    return (
      <section
        role="tabpanel"
        id="tabpanel-risk"
        aria-labelledby="tab-risk"
        data-testid="risk-panel-empty"
        className="bg-white rounded-xl border border-gray-200 shadow-xs p-8 sm:p-12 text-center max-w-2xl mx-auto"
      >
        <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Briefcase className="w-7 h-7" />
        </div>
        <h3 className="text-xl font-bold text-gray-900 tracking-tight">
          No Portfolio Available for Risk Analysis
        </h3>
        <p className="text-sm text-gray-500 mt-2 leading-relaxed">
          Risk &amp; exposure assessment requires an active portfolio with recorded positions. Get started by seeding the canonical Indian Bluechip Portfolio.
        </p>

        {seedError && (
          <div
            role="alert"
            data-testid="seed-demo-error"
            className="mt-5 p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 text-left flex items-start space-x-2.5 max-w-md mx-auto"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-900">Failed to seed demo portfolio</p>
              <p className="mt-0.5 text-rose-700 leading-relaxed">{seedError}</p>
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={handleSeedDemo}
            disabled={isSeedingDemo}
            data-testid="seed-demo-btn"
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <Sparkles className={`w-4 h-4 ${isSeedingDemo ? 'animate-spin' : ''}`} />
            <span>{isSeedingDemo ? 'Seeding Demo Data...' : 'Seed Demo Bluechip Portfolio'}</span>
          </button>
        </div>
      </section>
    );
  }

  return (
    <section
      role="tabpanel"
      id="tabpanel-risk"
      aria-labelledby="tab-risk"
      data-testid="risk-exposure-panel"
      className="space-y-6"
    >
      {/* Control & Selector Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-gray-900 tracking-tight">
                Risk &amp; Exposure Governance Panel
              </h1>
              {activePortfolio.is_sample && (
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                  Demo
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">
              Structural concentration, sector allocations, 4-component deterministic risk scores, and data quality.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 self-end sm:self-auto">
          {/* Portfolio Selector */}
          <div className="relative inline-flex items-center">
            <label htmlFor="risk-portfolio-select" className="sr-only">
              Select portfolio
            </label>
            <select
              id="risk-portfolio-select"
              aria-label="Select portfolio for risk analysis"
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

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            data-testid="refresh-risk-btn"
            aria-label="Refresh risk analytics"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 rounded-lg text-xs font-medium shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${
                isLoadingAnalytics || isLoadingInsights ? 'animate-spin' : ''
              }`}
            />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Analytics Error Notification */}
      {analyticsError && (
        <div
          data-testid="analytics-error-banner"
          className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-3"
        >
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-bold text-rose-900">Risk Analytics Calculation Failed</p>
            <p className="mt-0.5 text-rose-700 leading-relaxed">{analyticsError}</p>
          </div>
        </div>
      )}

      {/* 1. Deterministic Structural Risk Score Overview */}
      <RiskScoreCard
        riskAssessment={analytics?.risk_assessment}
        valuationStatus={analytics?.status}
        isLoading={isLoadingAnalytics}
      />

      {/* 2. Concentration & Diversification Profile */}
      <ConcentrationCard
        concentration={analytics?.concentration}
        isLoading={isLoadingAnalytics}
      />

      {/* 3. Industry Sector Allocations */}
      <SectorAllocationsCard
        sectors={analytics?.sector_allocations || []}
        isLoading={isLoadingAnalytics}
      />

      {/* 4. Data Quality & Price Completeness */}
      <DataCompletenessCard
        completeness={analytics?.completeness}
        isLoading={isLoadingAnalytics}
      />

      {/* 5. Chronological Historical Risk & Benchmark */}
      <HistoricalRiskCard
        historicalRisk={analytics?.historical_risk}
        isLoading={isLoadingAnalytics}
      />

      {/* 6. Deterministic Risk Observations */}
      <RiskInsightsSection
        insightsResponse={insights}
        isLoading={isLoadingInsights}
        error={insightsError}
      />
    </section>
  );
};
