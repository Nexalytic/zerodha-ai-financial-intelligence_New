import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePortfolio } from '../../context/PortfolioContext';
import { fetchPortfolioAnalytics, fetchPortfolioInsights } from '../../api/analytics';
import { generateAIPortfolioInsights } from '../../api/aiReasoning';
import { seedDemoPortfolio } from '../../api/portfolios';
import { parseApiError } from '../../api/client';
import { PortfolioAnalyticsResponse } from '../../types/analytics';
import { PortfolioInsightsResponse, AIInsightReport } from '../../types/aiReasoning';
import { PortfolioOverviewCard } from './PortfolioOverviewCard';
import { HoldingsTable } from './HoldingsTable';
import { RuleBasedInsightsSection } from './RuleBasedInsightsSection';
import { AIInsightsSection } from './AIInsightsSection';
import {
  Briefcase,
  RefreshCw,
  Sparkles,
  AlertCircle,
  Database,
  Plus,
  CheckCircle2,
} from 'lucide-react';
import { CreatePortfolioModal } from './CreatePortfolioModal';
import { AddHoldingModal } from './AddHoldingModal';

export const PortfolioHub: React.FC = () => {
  const {
    activePortfolioId,
    activePortfolio,
    portfolios,
    isLoading: isContextLoading,
    refreshPortfolios,
    setActivePortfolioId,
  } = usePortfolio();

  const [analytics, setAnalytics] = useState<PortfolioAnalyticsResponse | null>(null);
  const [insights, setInsights] = useState<PortfolioInsightsResponse | null>(null);
  const [aiReport, setAiReport] = useState<AIInsightReport | null>(null);

  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState<boolean>(false);
  const [isLoadingInsights, setIsLoadingInsights] = useState<boolean>(false);
  const [isGeneratingAI, setIsGeneratingAI] = useState<boolean>(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState<boolean>(false);

  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [createSuccessMessage, setCreateSuccessMessage] = useState<string | null>(null);

  const [isAddHoldingModalOpen, setIsAddHoldingModalOpen] = useState<boolean>(false);
  const [holdingSuccessMessage, setHoldingSuccessMessage] = useState<string | null>(null);

  const requestIdRef = useRef<number>(0);
  const aiRequestIdRef = useRef<number>(0);

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

      // Protect against out-of-order responses from superseded requests
      if (requestId !== requestIdRef.current) {
        return;
      }

      if (analyticsData.status === 'fulfilled') {
        setAnalytics(analyticsData.value);
      } else {
        const parsed = parseApiError(analyticsData.reason);
        setAnalyticsError(parsed.message || 'Failed to load portfolio analytics.');
        setAnalytics(null);
      }

      if (insightsData.status === 'fulfilled') {
        setInsights(insightsData.value);
      } else {
        const parsed = parseApiError(insightsData.reason);
        setInsightsError(parsed.message || 'Failed to load portfolio insights.');
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
    // Invalidate inflight AI requests and reset AI state when active portfolio changes
    aiRequestIdRef.current++;
    setIsGeneratingAI(false);
    setAiReport(null);
    setAiError(null);

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

  const handleHoldingAdded = async (symbol: string, quantity: number) => {
    // Invalidate inflight AI requests and reset AI state so stale claims are not displayed
    aiRequestIdRef.current++;
    setIsGeneratingAI(false);
    setAiReport(null);
    setAiError(null);

    setHoldingSuccessMessage(
      `Added ${quantity} share${quantity === 1 ? '' : 's'} of ${symbol} to ${activePortfolio?.name || 'portfolio'}. Analytics updated.`
    );

    if (activePortfolioId) {
      await Promise.all([loadData(activePortfolioId), refreshPortfolios()]);
    }
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
        setAiError(parsed.message || 'AI reasoning engine failed to synthesize insights.');
      }
    } finally {
      if (aiReqId === aiRequestIdRef.current) {
        setIsGeneratingAI(false);
      }
    }
  };

  // 1. Initial Context Loading State
  if (isContextLoading && portfolios.length === 0) {
    return (
      <section
        role="tabpanel"
        id="tabpanel-portfolio"
        aria-labelledby="tab-portfolio"
        data-testid="portfolio-hub-loading"
        className="py-16 text-center text-gray-500"
      >
        <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm font-semibold text-gray-800">Connecting to Portfolio Service...</p>
        <p className="text-xs text-gray-400 mt-1">Verifying stored positions and active valuations</p>
      </section>
    );
  }

  // 2. Empty State: No portfolios exist
  if (portfolios.length === 0 || !activePortfolio) {
    return (
      <section
        role="tabpanel"
        id="tabpanel-portfolio"
        aria-labelledby="tab-portfolio"
        data-testid="portfolio-hub-empty"
        className="bg-white rounded-xl border border-gray-200 shadow-xs p-8 sm:p-12 text-center max-w-2xl mx-auto"
      >
        <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Briefcase className="w-7 h-7" />
        </div>
        <h3 className="text-xl font-bold text-gray-900 tracking-tight">
          No Portfolios Available
        </h3>
        <p className="text-sm text-gray-500 mt-2 leading-relaxed">
          Get started immediately with the canonical &ldquo;Demo Indian Bluechip Portfolio&rdquo; seeded with realistic
          holdings (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK) and verified market baselines.
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
          <button
            onClick={() => setIsCreateModalOpen(true)}
            data-testid="empty-create-portfolio-btn"
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-5 py-2.5 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Custom Portfolio</span>
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-100 flex items-center justify-center space-x-2 text-xs text-gray-400">
          <Database className="w-3.5 h-3.5" />
          <span>Local SQLite Storage &bull; ₹0 Spend Policy Active</span>
        </div>

        <CreatePortfolioModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onCreated={(name) => {
            setCreateSuccessMessage(`Portfolio "${name}" created successfully.`);
          }}
        />
      </section>
    );
  }

  // 3. Main Dashboard View
  return (
    <section
      role="tabpanel"
      id="tabpanel-portfolio"
      aria-labelledby="tab-portfolio"
      data-testid="portfolio-intelligence-hub"
      className="space-y-6"
    >
      {/* Top Header Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
            Portfolio Intelligence Hub
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Holistic valuations, position analytics, rule-based risk observations, and evidence-grounded AI reasoning.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          <button
            onClick={() => setIsCreateModalOpen(true)}
            data-testid="new-portfolio-btn"
            aria-label="Create new portfolio"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Portfolio</span>
          </button>
          <button
            onClick={handleRefresh}
            data-testid="refresh-hub-btn"
            aria-label="Refresh portfolio hub"
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

      {/* Portfolio Creation Success Notification */}
      {createSuccessMessage && (
        <div
          role="status"
          data-testid="portfolio-create-success-banner"
          className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between"
        >
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span className="font-semibold">{createSuccessMessage}</span>
          </div>
          <button
            onClick={() => setCreateSuccessMessage(null)}
            className="text-emerald-700 hover:text-emerald-900 cursor-pointer font-bold text-sm ml-4"
            aria-label="Dismiss success message"
          >
            &times;
          </button>
        </div>
      )}

      {/* Position Added Success Notification */}
      {holdingSuccessMessage && (
        <div
          role="status"
          data-testid="holding-add-success-banner"
          className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between"
        >
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span className="font-semibold">{holdingSuccessMessage}</span>
          </div>
          <button
            onClick={() => setHoldingSuccessMessage(null)}
            className="text-emerald-700 hover:text-emerald-900 cursor-pointer font-bold text-sm ml-4"
            aria-label="Dismiss holding success message"
          >
            &times;
          </button>
        </div>
      )}

      {/* Analytics Error Notification */}
      {analyticsError && (
        <div
          data-testid="analytics-error-banner"
          className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-3"
        >
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-bold text-rose-900">Analytics Calculation Failed</p>
            <p className="mt-0.5 text-rose-700 leading-relaxed">{analyticsError}</p>
          </div>
        </div>
      )}

      {/* 1. Valuation & Completeness Overview */}
      <PortfolioOverviewCard
        portfolio={activePortfolio}
        analytics={analytics}
        isLoading={isLoadingAnalytics}
      />

      {/* 2. Holdings Table */}
      <HoldingsTable
        holdings={analytics?.holdings || []}
        isLoading={isLoadingAnalytics}
        onAddHolding={() => setIsAddHoldingModalOpen(true)}
      />

      {/* 3. Deterministic Rule-Based Observations */}
      <RuleBasedInsightsSection
        insightsResponse={insights}
        isLoading={isLoadingInsights}
        error={insightsError}
      />

      {/* 4. Evidence-Grounded AI Intelligence */}
      <AIInsightsSection
        aiReport={aiReport && aiReport.portfolio_id === activePortfolio.id ? aiReport : null}
        isGenerating={isGeneratingAI}
        error={aiError}
        onGenerate={handleGenerateAI}
        portfolioId={activePortfolio.id}
      />

      {/* Create Portfolio Modal */}
      <CreatePortfolioModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={(name) => {
          setCreateSuccessMessage(`Portfolio "${name}" created successfully.`);
        }}
      />

      {/* Add Holding Modal */}
      {activePortfolio && (
        <AddHoldingModal
          isOpen={isAddHoldingModalOpen}
          onClose={() => setIsAddHoldingModalOpen(false)}
          portfolioId={activePortfolio.id}
          portfolioName={activePortfolio.name}
          onHoldingAdded={handleHoldingAdded}
        />
      )}
    </section>
  );
};
