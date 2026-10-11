import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Layers,
  AlertCircle,
  HelpCircle,
  Filter,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Clock,
  Briefcase,
  SlidersHorizontal,
  Tag,
  FileText,
} from 'lucide-react';
import { usePortfolio } from '../../context/PortfolioContext';
import { generateAIPortfolioInsights } from '../../api/aiReasoning';
import {
  AIInsightReport,
  ReviewStatus,
} from '../../types/aiReasoning';

export const RecommendationReviewConsole: React.FC = () => {
  const { activePortfolio, activePortfolioId, isLoading: isContextLoading } =
    usePortfolio();

  const [aiReport, setAiReport] = useState<AIInsightReport | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Client-side filter states for review cards
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  // Request race condition guard
  const requestIdRef = useRef<number>(0);

  // Clear report immediately when active portfolio changes
  useEffect(() => {
    setAiReport(null);
    setError(null);
    setIsGenerating(false);
    setStatusFilter('ALL');
    setCategoryFilter('ALL');
    setSeverityFilter('ALL');
    // Invalidate any in-flight requests from previous portfolio
    requestIdRef.current += 1;
  }, [activePortfolioId]);

  const handleGenerateReport = async () => {
    if (!activePortfolioId || isGenerating) return;

    const currentRequestId = ++requestIdRef.current;
    setIsGenerating(true);
    setError(null);

    try {
      const report = await generateAIPortfolioInsights(activePortfolioId, {
        include_news: true,
        news_limit: 10,
      });

      // Discard late response if request was superseded or portfolio changed
      if (requestIdRef.current === currentRequestId) {
        setAiReport(report);
        setIsGenerating(false);
      }
    } catch (err: any) {
      if (requestIdRef.current === currentRequestId) {
        const errorMsg =
          err?.response?.data?.message ||
          err?.message ||
          'Failed to generate AI intelligence review report. Check provider configuration.';
        setError(errorMsg);
        setIsGenerating(false);
      }
    }
  };

  // Rejection safety guard: report is REJECTED if status is REJECTED,
  // OR rejected_count > 0, OR is_acceptable === false
  const isGroundingRejected = Boolean(
    aiReport &&
      (aiReport.review_status === 'REJECTED' ||
        aiReport.grounding_report?.is_acceptable === false ||
        (aiReport.grounding_report?.rejected_count ?? 0) > 0)
  );

  const isFlaggedWithWarnings = Boolean(
    aiReport &&
      !isGroundingRejected &&
      (aiReport.review_status === 'FLAGGED_WITH_WARNINGS' ||
        (aiReport.grounding_report?.flagged_count ?? 0) > 0)
  );

  const isVerified = Boolean(
    aiReport &&
      !isGroundingRejected &&
      !isFlaggedWithWarnings &&
      aiReport.review_status === 'VERIFIED'
  );

  // Unique categories from review cards for filter dropdown
  const availableCategories = React.useMemo(() => {
    if (!aiReport?.review_cards) return [];
    const set = new Set<string>();
    aiReport.review_cards.forEach((c) => {
      if (c.category) set.add(c.category);
    });
    return Array.from(set).sort();
  }, [aiReport]);

  // Filtered review cards
  const filteredReviewCards = React.useMemo(() => {
    if (!aiReport?.review_cards) return [];
    return aiReport.review_cards.filter((card) => {
      if (statusFilter !== 'ALL' && card.review_status !== statusFilter) {
        return false;
      }
      if (categoryFilter !== 'ALL' && card.category !== categoryFilter) {
        return false;
      }
      if (severityFilter !== 'ALL' && card.severity !== severityFilter) {
        return false;
      }
      return true;
    });
  }, [aiReport, statusFilter, categoryFilter, severityFilter]);

  const getStatusBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>VERIFIED</span>
          </span>
        );
      case 'FLAGGED_WITH_WARNINGS':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            <span>FLAGGED</span>
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-600" />
            <span>REJECTED</span>
          </span>
        );
      case 'PENDING_REVIEW':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-700 border border-gray-200">
            <Clock className="w-3 h-3 text-gray-500" />
            <span>PENDING REVIEW</span>
          </span>
        );
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-orange-100 text-orange-800 border border-orange-200">
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            MEDIUM
          </span>
        );
      case 'LOW':
      case 'INFO':
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
            {severity || 'INFO'}
          </span>
        );
    }
  };

  const hasActiveFilters =
    statusFilter !== 'ALL' || categoryFilter !== 'ALL' || severityFilter !== 'ALL';

  return (
    <div
      role="tabpanel"
      aria-label="Recommendation Review"
      data-testid="recommendation-review-console"
      className="space-y-6"
    >
      {/* 1. Header & Generation Control */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-2.5 bg-purple-50 text-purple-600 rounded-xl">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                  Recommendation Review Console
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-100 text-purple-800">
                  Verifiable AI Guardrails
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Inspect evidence-grounded AI intelligence reports, mathematical claim audits, and modular review cards.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {activePortfolio && (
              <div
                data-testid="console-active-portfolio-badge"
                className="hidden md:flex items-center space-x-2 text-xs bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-200"
              >
                <Briefcase className="w-3.5 h-3.5 text-gray-400" />
                <span className="font-semibold text-gray-800">{activePortfolio.name}</span>
                <span className="text-gray-400 font-mono text-[11px]">
                  ({activePortfolio.holdings_count} pos)
                </span>
                {activePortfolio.is_sample && (
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-blue-50 text-blue-600">
                    Demo
                  </span>
                )}
              </div>
            )}

            <button
              onClick={handleGenerateReport}
              disabled={isGenerating || !activePortfolioId || isContextLoading}
              data-testid="generate-review-btn"
              className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`}
              />
              <span>
                {isGenerating
                  ? 'Generating Review...'
                  : aiReport
                  ? 'Refresh AI Review'
                  : 'Generate AI Intelligence Review'}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Educational Scope Disclaimer */}
      <div
        data-testid="console-scope-notice"
        className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200 text-xs text-blue-900 flex items-start space-x-2.5"
      >
        <Layers className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-semibold text-blue-950">
            Educational Financial Intelligence &bull; Deterministic Claim Verifier
          </p>
          <p className="text-blue-800 text-[11px] leading-relaxed">
            All AI insights and review cards represent algorithmic portfolio telemetry analysis for educational and review purposes.
            The platform does not issue SEBI-registered investment advice, provide execution buy/sell orders, or persist human review decisions in the database.
          </p>
        </div>
      </div>

      {/* 3. Loading State */}
      {isGenerating && (
        <div
          role="status"
          aria-busy="true"
          data-testid="review-loading-state"
          className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-xs space-y-3"
        >
          <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <h3 className="text-sm font-bold text-gray-900">
            Assembling Portfolio Evidence &amp; Running Grounding Verification...
          </h3>
          <p className="text-xs text-gray-500 max-w-md mx-auto leading-relaxed">
            Assembling position weights, quote snapshots, news feeds, and computing claim grounding checks across all synthesized assertions.
          </p>
        </div>
      )}

      {/* 4. Error State */}
      {!isGenerating && error && (
        <div
          role="alert"
          data-testid="review-error-banner"
          className="bg-rose-50 border border-rose-200 rounded-xl p-5 shadow-xs flex items-start space-x-3 text-xs"
        >
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <h4 className="font-bold text-rose-900">Review Generation Failed</h4>
            <p className="text-rose-700 leading-relaxed">{error}</p>
            <div className="pt-2">
              <button
                onClick={handleGenerateReport}
                data-testid="retry-review-btn"
                className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer transition"
              >
                Retry Review Generation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. No Portfolio Selected State */}
      {!isGenerating && !error && !activePortfolioId && (
        <div
          data-testid="no-portfolio-state"
          className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-xs space-y-3"
        >
          <Briefcase className="w-10 h-10 text-gray-300 mx-auto" />
          <h3 className="text-sm font-bold text-gray-800">No Portfolio Selected</h3>
          <p className="text-xs text-gray-500 max-w-sm mx-auto leading-relaxed">
            Please select an investment portfolio from the header selector to review AI recommendations and evidence citations.
          </p>
        </div>
      )}

      {/* 6. Empty Portfolio Warning (Zero Holdings) */}
      {!isGenerating &&
        !error &&
        activePortfolio &&
        activePortfolio.holdings_count === 0 &&
        !aiReport && (
          <div
            data-testid="empty-portfolio-state"
            className="bg-amber-50 border border-amber-200 rounded-xl p-6 shadow-xs text-xs space-y-2 text-amber-900"
          >
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
              <h3 className="font-bold text-sm text-amber-950">
                Portfolio is Empty (0 Holdings)
              </h3>
            </div>
            <p className="text-amber-800 leading-relaxed">
              Portfolio &ldquo;{activePortfolio.name}&rdquo; currently contains 0 recorded positions.
              Quantitative evidence synthesis requires active holdings to calculate concentration, sector allocation, and quote metrics.
            </p>
            <p className="text-amber-700 text-[11px]">
              You can still generate a review report to inspect empty-state disclosures, or add holdings via Portfolio Hub to enable full intelligence analysis.
            </p>
          </div>
        )}

      {/* 7. Initial / Uninitialized State (Before generation) */}
      {!isGenerating &&
        !error &&
        activePortfolioId &&
        !aiReport && (
          <div
            data-testid="uninitialized-review-state"
            className="bg-white rounded-xl border border-gray-200 p-8 shadow-xs space-y-6"
          >
            <div className="text-center space-y-2 max-w-xl mx-auto">
              <div className="w-12 h-12 rounded-full bg-purple-50 text-purple-600 flex items-center justify-center mx-auto">
                <FileText className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-gray-900">
                No Review Report Generated Yet for {activePortfolio?.name || 'Active Portfolio'}
              </h3>
              <p className="text-xs text-gray-500 leading-relaxed">
                Click &ldquo;Generate AI Intelligence Review&rdquo; to assemble factual portfolio evidence, execute deterministic reasoning, and audit claim veracity.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100 text-xs">
              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <div className="flex items-center space-x-2 text-gray-900 font-bold">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <h4>Grounding Guardrails</h4>
                </div>
                <p className="text-gray-600 text-[11px] leading-relaxed">
                  Every statement is cross-checked against actual ledger positions, preventing fabricated single-stock forecasts.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <div className="flex items-center space-x-2 text-gray-900 font-bold">
                  <SlidersHorizontal className="w-4 h-4 text-purple-600" />
                  <h4>Review Cards</h4>
                </div>
                <p className="text-gray-600 text-[11px] leading-relaxed">
                  Modular cards with cited metrics, categories, severity ratings, and algorithmic review statuses.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <div className="flex items-center space-x-2 text-gray-900 font-bold">
                  <Layers className="w-4 h-4 text-blue-600" />
                  <h4>Calibration &amp; Gaps</h4>
                </div>
                <p className="text-gray-600 text-[11px] leading-relaxed">
                  Clear confidence score limitations, staleness discounts, and explicit disclosures of missing or partial data.
                </p>
              </div>
            </div>
          </div>
        )}

      {/* 8. Rendered AI Intelligence Report Content */}
      {!isGenerating && !error && aiReport && (
        <div data-testid="review-report-content" className="space-y-6">
          {/* A. Overall Report Status Banner */}
          {isGroundingRejected ? (
            <div
              data-testid="report-status-rejected"
              className="p-5 rounded-xl bg-rose-50 border border-rose-300 text-xs text-rose-950 space-y-3 shadow-xs"
            >
              <div className="flex items-start space-x-3">
                <AlertOctagon className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-extrabold text-sm uppercase tracking-wider text-rose-900">
                      CLAIM GROUNDING REJECTED
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-200 text-rose-900">
                      {aiReport.grounding_report?.rejected_count ?? 0} REJECTED /{' '}
                      {aiReport.grounding_report?.flagged_count ?? 0} FLAGGED
                    </span>
                  </div>
                  <p className="mt-1 text-rose-800 leading-relaxed">
                    Grounding guardrails detected ungrounded, contradictory, or fabricated claims.
                    This report failed veracity verification and must not be treated as reliable portfolio intelligence.
                  </p>
                </div>
              </div>

              {/* Exact Discrepancy Findings */}
              {aiReport.grounding_report?.findings &&
                aiReport.grounding_report.findings.filter((f) => f.status !== 'PASSED').length >
                  0 && (
                  <div className="pt-2 border-t border-rose-200/80 pl-9 space-y-1.5">
                    <p className="font-bold text-[11px] text-rose-900 uppercase tracking-wider">
                      Grounding Rejection Reasons:
                    </p>
                    {aiReport.grounding_report.findings
                      .filter((f) => f.status !== 'PASSED')
                      .map((f, idx) => (
                        <div
                          key={f.target_id || idx}
                          data-testid={`rejected-finding-${idx}`}
                          className="text-[11px] text-rose-800 flex items-start space-x-1.5"
                        >
                          <span className="font-mono font-bold text-rose-900">
                            [{f.check_name}]:
                          </span>
                          <span>
                            {f.reason || 'Assertion contradicts verified evidence bundle.'}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
            </div>
          ) : isFlaggedWithWarnings ? (
            <div
              data-testid="report-status-flagged"
              className="p-5 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-950 space-y-3 shadow-xs"
            >
              <div className="flex items-start space-x-3">
                <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-extrabold text-sm uppercase tracking-wider text-amber-900">
                      FLAGGED WITH WARNINGS
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-200 text-amber-900">
                      {aiReport.grounding_report?.flagged_count ?? 0} FLAGGED CLAIMS
                    </span>
                  </div>
                  <p className="mt-1 text-amber-800 leading-relaxed">
                    Automated claim checks verified most assertions, but detected minor discrepancies or unverified metrics requiring analyst inspection.
                  </p>
                </div>
              </div>

              {aiReport.grounding_report?.findings &&
                aiReport.grounding_report.findings.filter((f) => f.status === 'FLAGGED').length >
                  0 && (
                  <div className="pt-2 border-t border-amber-200/80 pl-9 space-y-1.5">
                    <p className="font-bold text-[11px] text-amber-900 uppercase tracking-wider">
                      Verification Discrepancies:
                    </p>
                    {aiReport.grounding_report.findings
                      .filter((f) => f.status === 'FLAGGED')
                      .map((f, idx) => (
                        <div
                          key={f.target_id || idx}
                          data-testid={`flagged-finding-${idx}`}
                          className="text-[11px] text-amber-800 flex items-start space-x-1.5"
                        >
                          <span className="font-mono font-bold text-amber-900">
                            [{f.check_name}]:
                          </span>
                          <span>{f.reason || 'Flagged assertion metric.'}</span>
                        </div>
                      ))}
                  </div>
                )}
            </div>
          ) : isVerified ? (
            <div
              data-testid="report-status-verified"
              className="p-5 rounded-xl bg-emerald-50 border border-emerald-300 text-xs text-emerald-950 space-y-2 shadow-xs"
            >
              <div className="flex items-start space-x-3">
                <ShieldCheck className="w-6 h-6 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-extrabold text-sm uppercase tracking-wider text-emerald-900">
                      FACT-GROUNDED VERIFIED
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-200 text-emerald-900">
                      {aiReport.grounding_report?.passed_count ?? 0} /{' '}
                      {aiReport.grounding_report?.total_claims_checked ?? 0} CLAIMS CONFIRMED
                    </span>
                  </div>
                  <p className="mt-1 text-emerald-800 leading-relaxed">
                    All assertions in this intelligence report were mathematically cross-examined against ground-truth holdings, valuations, and market data.
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {/* B. Executive Narrative & Provenance */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
                Executive Synthesis
              </span>
              <div className="flex items-center space-x-2 text-[11px] text-gray-500 font-mono">
                <span>Provider: {aiReport.provider_name}</span>
                <span>&bull;</span>
                <span>Model: {aiReport.model_id}</span>
                {aiReport.is_simulated && (
                  <>
                    <span>&bull;</span>
                    <span
                      data-testid="simulated-provenance-badge"
                      className="text-blue-600 font-semibold"
                    >
                      Simulated Demo Reasoner
                    </span>
                  </>
                )}
              </div>
            </div>

            <p
              data-testid="review-executive-summary"
              className="text-sm text-gray-800 leading-relaxed whitespace-pre-line font-serif"
            >
              {aiReport.executive_summary}
            </p>
          </div>

          {/* C. Programmatic Claim Grounding Audit */}
          <div
            data-testid="grounding-audit-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-bold text-gray-900">
                  Programmatic Claim Grounding Audit
                </h3>
                <p className="text-[11px] text-gray-500">
                  Mathematical claim veracity checks executed against underlying evidence bundle (not human review).
                </p>
              </div>

              <span
                data-testid="grounding-acceptable-badge"
                className={`px-2.5 py-1 rounded-full text-xs font-bold self-start sm:self-auto ${
                  aiReport.grounding_report?.is_acceptable
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-rose-100 text-rose-800'
                }`}
              >
                {aiReport.grounding_report?.is_acceptable ? 'ACCEPTABLE' : 'UNACCEPTABLE'}
              </span>
            </div>

            {/* Counts Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Claims Checked
                </span>
                <p
                  data-testid="grounding-count-checked"
                  className="text-xl font-bold text-gray-900 mt-0.5"
                >
                  {aiReport.grounding_report?.total_claims_checked ?? 0}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <span className="text-emerald-700 text-[10px] uppercase font-semibold">
                  Verified Passed
                </span>
                <p
                  data-testid="grounding-count-passed"
                  className="text-xl font-bold text-emerald-700 mt-0.5"
                >
                  {aiReport.grounding_report?.passed_count ?? 0}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                <span className="text-amber-700 text-[10px] uppercase font-semibold">
                  Flagged Discrepant
                </span>
                <p
                  data-testid="grounding-count-flagged"
                  className="text-xl font-bold text-amber-700 mt-0.5"
                >
                  {aiReport.grounding_report?.flagged_count ?? 0}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200">
                <span className="text-rose-700 text-[10px] uppercase font-semibold">
                  Rejected Claims
                </span>
                <p
                  data-testid="grounding-count-rejected"
                  className="text-xl font-bold text-rose-700 mt-0.5"
                >
                  {aiReport.grounding_report?.rejected_count ?? 0}
                </p>
              </div>
            </div>

            {/* Granular Findings List */}
            {aiReport.grounding_report?.findings &&
              aiReport.grounding_report.findings.length > 0 && (
                <div className="space-y-2 pt-2">
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                    Individual Verification Check Results ({aiReport.grounding_report.findings.length})
                  </h4>
                  <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                    {aiReport.grounding_report.findings.map((f, idx) => (
                      <div
                        key={f.target_id || idx}
                        data-testid={`grounding-finding-row-${idx}`}
                        className="p-3 bg-white hover:bg-gray-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs"
                      >
                        <div className="flex items-center space-x-2.5">
                          <span
                            className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                              f.status === 'PASSED'
                                ? 'bg-emerald-500'
                                : f.status === 'FLAGGED'
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                          />
                          <div>
                            <span className="font-mono font-bold text-gray-900">
                              {f.check_name}
                            </span>
                            <span className="text-gray-400 font-mono text-[11px] ml-1.5">
                              target: {f.target_id}
                            </span>
                            {f.reason && (
                              <p className="text-gray-600 text-[11px] mt-0.5">
                                {f.reason}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center space-x-2 self-start sm:self-auto">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                              f.status === 'PASSED'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : f.status === 'FLAGGED'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {f.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
          </div>

          {/* D. Modular Review Cards Section */}
          <div
            data-testid="review-cards-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
          >
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 pb-3 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
                  <span>Reviewable Insight Cards</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-purple-50 text-purple-700 border border-purple-200">
                    {aiReport.review_cards?.length ?? 0} Total
                  </span>
                </h3>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Modular cards representing individual algorithmic findings. Status tags reflect programmatic claim verification.
                </p>
              </div>

              {/* Filter Controls */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center space-x-1.5 text-xs">
                  <Filter className="w-3.5 h-3.5 text-gray-400" />
                  <label htmlFor="filter-status-select" className="sr-only">
                    Filter by Status
                  </label>
                  <select
                    id="filter-status-select"
                    data-testid="filter-status"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="bg-gray-50 border border-gray-200 text-xs rounded-lg px-2.5 py-1 text-gray-700 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="ALL">Status: All</option>
                    <option value="VERIFIED">Verified</option>
                    <option value="FLAGGED_WITH_WARNINGS">Flagged</option>
                    <option value="REJECTED">Rejected</option>
                    <option value="PENDING_REVIEW">Pending Review</option>
                  </select>
                </div>

                {availableCategories.length > 0 && (
                  <div className="flex items-center space-x-1 text-xs">
                    <label htmlFor="filter-category-select" className="sr-only">
                      Filter by Category
                    </label>
                    <select
                      id="filter-category-select"
                      data-testid="filter-category"
                      value={categoryFilter}
                      onChange={(e) => setCategoryFilter(e.target.value)}
                      className="bg-gray-50 border border-gray-200 text-xs rounded-lg px-2.5 py-1 text-gray-700 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="ALL">Category: All</option>
                      {availableCategories.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="flex items-center space-x-1 text-xs">
                  <label htmlFor="filter-severity-select" className="sr-only">
                    Filter by Severity
                  </label>
                  <select
                    id="filter-severity-select"
                    data-testid="filter-severity"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                    className="bg-gray-50 border border-gray-200 text-xs rounded-lg px-2.5 py-1 text-gray-700 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="ALL">Severity: All</option>
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                    <option value="INFO">Info</option>
                  </select>
                </div>

                {hasActiveFilters && (
                  <button
                    onClick={() => {
                      setStatusFilter('ALL');
                      setCategoryFilter('ALL');
                      setSeverityFilter('ALL');
                    }}
                    data-testid="clear-filters-btn"
                    className="text-[11px] text-blue-600 hover:text-blue-800 font-semibold cursor-pointer underline px-1"
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>

            {/* Empty Filter Results */}
            {filteredReviewCards.length === 0 ? (
              <div
                data-testid="no-filtered-cards"
                className="py-10 text-center text-gray-400 text-xs space-y-1.5"
              >
                <HelpCircle className="w-8 h-8 mx-auto text-gray-300" />
                <p className="font-semibold text-gray-600">
                  No review cards match the selected filter criteria.
                </p>
                <p className="text-gray-400">
                  Adjust status, category, or severity filters to view remaining observation cards.
                </p>
              </div>
            ) : (
              /* Review Cards Grid */
              <div
                data-testid="review-cards-grid"
                className="grid grid-cols-1 md:grid-cols-2 gap-4"
              >
                {filteredReviewCards.map((card, idx) => (
                  <div
                    key={card.card_id || `card-${idx}`}
                    data-testid={`review-card-${card.card_id}`}
                    className="bg-white rounded-xl border border-gray-200 p-4 space-y-2.5 shadow-2xs hover:border-gray-300 transition flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                          {getStatusBadge(card.review_status)}
                          {getSeverityBadge(card.severity)}
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-gray-100 text-gray-700">
                            {card.category}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono text-gray-400">
                          {card.card_id}
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-gray-900 leading-snug">
                        {card.title}
                      </h4>

                      <p className="text-xs text-gray-600 leading-relaxed">
                        {card.description}
                      </p>
                    </div>

                    <div className="space-y-2 pt-2 border-t border-gray-100 text-[11px]">
                      {/* Related Symbols */}
                      {card.related_symbols && card.related_symbols.length > 0 && (
                        <div className="flex items-center space-x-1.5">
                          <Tag className="w-3 h-3 text-gray-400" />
                          <span className="text-gray-500">Related Symbols:</span>
                          <div className="flex items-center space-x-1">
                            {card.related_symbols.map((sym) => (
                              <span
                                key={sym}
                                className="px-1.5 py-0.2 rounded font-mono font-bold bg-blue-50 text-blue-700 text-[10px]"
                              >
                                {sym}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Cited Metrics */}
                      {card.cited_metrics &&
                        Object.keys(card.cited_metrics).length > 0 && (
                          <div className="p-2 rounded bg-gray-50 border border-gray-200 text-[10px] font-mono space-y-0.5">
                            <span className="text-gray-400 font-sans uppercase font-semibold block">
                              Cited Grounding Evidence:
                            </span>
                            {Object.entries(card.cited_metrics).map(([k, v]) => (
                              <div
                                key={k}
                                className="flex items-center justify-between text-gray-700"
                              >
                                <span className="text-blue-700 truncate mr-2" title={k}>
                                  {k}:
                                </span>
                                <span className="font-bold text-gray-900">
                                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* E. Key Drivers & Risk Warnings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Key Drivers */}
            {aiReport.key_drivers && aiReport.key_drivers.length > 0 && (
              <div
                data-testid="console-key-drivers"
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-3"
              >
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Verified Performance &amp; Risk Drivers ({aiReport.key_drivers.length})
                </h3>
                <div className="space-y-2.5">
                  {aiReport.key_drivers.map((driver) => (
                    <div
                      key={driver.driver_id}
                      data-testid={`driver-${driver.driver_id}`}
                      className="p-3 rounded-lg border border-gray-200 bg-gray-50/60 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-900">{driver.title}</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-50 text-blue-700">
                          {driver.driver_type}
                        </span>
                      </div>
                      <p className="text-gray-600 text-[11px] leading-relaxed">
                        {driver.statement}
                      </p>
                      <div className="pt-1 text-[10px] font-mono text-gray-400 flex items-center justify-between">
                        <span>Metric: {driver.supporting_metric_key}</span>
                        <span>Source: {driver.source_reference}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Warnings */}
            {aiReport.risk_alerts && aiReport.risk_alerts.length > 0 && (
              <div
                data-testid="console-risk-alerts"
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-3"
              >
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Synthesized Risk Warnings ({aiReport.risk_alerts.length})
                </h3>
                <div className="space-y-2.5">
                  {aiReport.risk_alerts.map((alert) => (
                    <div
                      key={alert.alert_id}
                      data-testid={`alert-${alert.alert_id}`}
                      className="p-3 rounded-lg border border-amber-200 bg-amber-50/60 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-amber-950">{alert.headline}</span>
                        {getSeverityBadge(alert.severity)}
                      </div>
                      <p className="text-amber-800 text-[11px] leading-relaxed">
                        {alert.explanation}
                      </p>
                      {alert.actionable_mitigation && (
                        <p className="text-[10px] text-amber-900 pt-1 font-sans">
                          <strong>Educational Note:</strong> {alert.actionable_mitigation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* F. Confidence, Calibration & Uncertainty Disclosures */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pb-4 border-b border-gray-100">
              {/* Confidence Score */}
              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Confidence Score &amp; Level
                </span>
                <div className="flex items-baseline space-x-2 pt-1">
                  <span
                    data-testid="console-confidence-score"
                    className="text-2xl font-bold text-gray-900"
                  >
                    {(parseFloat(String(aiReport.confidence?.score ?? 0)) * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                    {aiReport.confidence?.level || 'UNRATED'} LEVEL
                  </span>
                </div>
                <div className="pt-2 text-[11px] text-gray-600 space-y-0.5">
                  <p>
                    Data Quality Discount:{' '}
                    <strong>
                      {(
                        parseFloat(String(aiReport.confidence?.data_quality_discount ?? 0)) * 100
                      ).toFixed(0)}%
                    </strong>
                  </p>
                  <p>
                    Staleness Discount:{' '}
                    <strong>
                      {(
                        parseFloat(String(aiReport.confidence?.staleness_discount ?? 0)) * 100
                      ).toFixed(0)}%
                    </strong>
                  </p>
                </div>
              </div>

              {/* Calibration Limitation Disclosure */}
              <div className="md:col-span-2 space-y-1">
                <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Mandatory Calibration Limitation Disclosure
                </span>
                <p
                  data-testid="console-calibration-text"
                  className="text-xs text-gray-700 mt-1 leading-relaxed bg-gray-50 p-3 rounded-lg border border-gray-200"
                >
                  {aiReport.confidence?.calibration_limitation ||
                    'Calibration limited to evidence observed in current snapshot.'}
                </p>
              </div>
            </div>

            {/* Uncertainty and Missing Evidence Disclosures */}
            {aiReport.uncertainty_and_gaps && aiReport.uncertainty_and_gaps.length > 0 && (
              <div
                data-testid="console-uncertainty-gaps"
                className="space-y-2"
              >
                <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                  Uncertainty &amp; Missing Evidence Disclosures ({aiReport.uncertainty_and_gaps.length})
                </h4>
                <div className="space-y-1 pl-4 text-xs text-gray-600">
                  {aiReport.uncertainty_and_gaps.map((gap, i) => (
                    <li key={i} className="list-disc leading-relaxed">
                      {gap}
                    </li>
                  ))}
                </div>
              </div>
            )}

            {/* Mandatory Disclaimers */}
            {aiReport.disclaimers && aiReport.disclaimers.length > 0 && (
              <div
                data-testid="console-disclaimers"
                className="pt-3 border-t border-gray-100 text-[11px] text-gray-500 space-y-1.5"
              >
                <p className="font-bold text-gray-700 uppercase tracking-wider text-[10px]">
                  Compliance &amp; Academic Notice:
                </p>
                {aiReport.disclaimers.map((d, i) => (
                  <p key={i}>&bull; {d}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
