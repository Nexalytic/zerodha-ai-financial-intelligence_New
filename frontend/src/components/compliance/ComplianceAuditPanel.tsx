import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  Filter,
  RefreshCw,
  FileText,
  Info,
  Scale,
  Database,
} from 'lucide-react';
import { usePortfolio } from '../../context/PortfolioContext';
import { generateAIPortfolioInsights } from '../../api/aiReasoning';
import { AIInsightReport } from '../../types/aiReasoning';

export const ComplianceAuditPanel: React.FC = () => {
  const { activePortfolio, activePortfolioId } = usePortfolio();

  const [aiReport, setAiReport] = useState<AIInsightReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [findingFilter, setFindingFilter] = useState<string>('ALL');

  // Request counter ref for out-of-order race condition protection
  const requestIdRef = useRef<number>(0);

  // Clear report immediately when active portfolio changes, invalidating in-flight requests
  useEffect(() => {
    setAiReport(null);
    setError(null);
    setIsLoading(false);
    setFindingFilter('ALL');
    requestIdRef.current += 1;
  }, [activePortfolioId]);

  const handleRunAudit = async () => {
    if (!activePortfolioId || isLoading) return;

    const currentRequestId = ++requestIdRef.current;
    setIsLoading(true);
    setError(null);

    try {
      const report = await generateAIPortfolioInsights(activePortfolioId, {
        include_news: true,
        news_limit: 10,
      });

      // Discard response if superseded or if portfolio changed in-flight
      if (requestIdRef.current === currentRequestId) {
        setAiReport(report);
        setIsLoading(false);
      }
    } catch (err: any) {
      if (requestIdRef.current === currentRequestId) {
        const errorMsg =
          err?.response?.data?.message ||
          err?.message ||
          'Failed to run compliance and grounding audit. Check backend connectivity.';
        setError(errorMsg);
        setIsLoading(false);
      }
    }
  };

  // Rejection precedence derivation:
  // Rejection occurs if rejected_count > 0, is_acceptable === false, or review_status === 'REJECTED'
  const isRejected = Boolean(
    aiReport &&
      (aiReport.review_status === 'REJECTED' ||
        aiReport.grounding_report?.is_acceptable === false ||
        (aiReport.grounding_report?.rejected_count ?? 0) > 0)
  );

  // Flagged findings warning exists if not rejected, but flagged_count > 0 or review_status === 'FLAGGED_WITH_WARNINGS'
  const isFlagged = Boolean(
    aiReport &&
      !isRejected &&
      (aiReport.review_status === 'FLAGGED_WITH_WARNINGS' ||
        (aiReport.grounding_report?.flagged_count ?? 0) > 0)
  );

  // Fully verified requires acceptable, zero rejected, zero flagged, and review_status === 'VERIFIED'
  const isFullyVerified = Boolean(
    aiReport &&
      !isRejected &&
      !isFlagged &&
      aiReport.grounding_report?.is_acceptable === true &&
      aiReport.review_status === 'VERIFIED'
  );

  // Filtered grounding findings
  const filteredFindings = useMemo(() => {
    if (!aiReport?.grounding_report?.findings) return [];
    if (findingFilter === 'ALL') return aiReport.grounding_report.findings;
    return aiReport.grounding_report.findings.filter(
      (f) => f.status === findingFilter
    );
  }, [aiReport, findingFilter]);

  return (
    <section
      role="tabpanel"
      aria-label="Compliance & Audit"
      data-testid="compliance-audit-panel"
      className="space-y-6"
    >
      {/* 1. Header & Explicit User Action Control */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
              <Scale className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                  Compliance &amp; Audit Panel
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-100 text-purple-800">
                  Governance
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Automated claim-grounding verification findings, confidence uncertainty disclosures, and zero-spend compliance tracking.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {activePortfolio ? (
              <button
                onClick={handleRunAudit}
                disabled={isLoading}
                aria-busy={isLoading}
                data-testid="run-audit-btn"
                className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`}
                />
                <span>
                  {isLoading
                    ? 'Running Grounding Audit...'
                    : aiReport
                    ? 'Re-Run Grounding Audit'
                    : 'Run Compliance & Grounding Audit'}
                </span>
              </button>
            ) : null}
          </div>
        </div>

        {/* Audit Report Run Metadata (Provenance) */}
        {aiReport && (
          <div
            data-testid="audit-metadata-bar"
            className="mt-4 pt-3.5 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500"
          >
            <div className="flex flex-wrap items-center gap-3">
              <span>
                Report ID:{' '}
                <strong
                  data-testid="audit-report-id"
                  className="font-mono text-gray-800"
                >
                  {aiReport.report_id}
                </strong>
              </span>
              <span className="text-gray-300">&bull;</span>
              <span>
                Engine Provider:{' '}
                <strong
                  data-testid="audit-provider-name"
                  className="font-mono text-gray-800"
                >
                  {aiReport.provider_name}
                </strong>{' '}
                <span className="text-[10px] text-gray-400">
                  ({aiReport.model_id})
                </span>
              </span>
              <span className="text-gray-300">&bull;</span>
              <span>
                Audited At:{' '}
                <span className="font-mono text-gray-700">
                  {new Date(aiReport.generated_at).toLocaleTimeString()}
                </span>
              </span>
            </div>

            <div className="flex items-center space-x-2">
              {aiReport.is_simulated && (
                <span
                  data-testid="audit-simulated-badge"
                  className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200"
                >
                  Simulated Heuristic Intelligence
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div
          role="status"
          aria-busy="true"
          data-testid="compliance-loading-state"
          className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500 text-xs space-y-3 shadow-xs"
        >
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
          <div>
            <p className="text-sm font-bold text-gray-800">
              Executing Claim-Grounding Verification Audit...
            </p>
            <p className="text-gray-400 text-xs mt-1">
              Evaluating numerical veracity, ticker validity, concentration metrics, and evidence citations against verified portfolio state.
            </p>
          </div>
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div
          role="alert"
          data-testid="compliance-error-banner"
          className="p-5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-3 shadow-xs"
        >
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1.5">
            <h3 className="font-bold text-rose-900 text-sm">
              Compliance Audit Execution Failed
            </h3>
            <p className="text-rose-700">{error}</p>
            <div className="pt-2">
              <button
                onClick={handleRunAudit}
                data-testid="retry-audit-btn"
                className="px-3.5 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700 cursor-pointer transition shadow-2xs"
              >
                Retry Grounding Audit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty State (When no portfolio or no audit run yet) */}
      {!isLoading && !error && !aiReport && (
        <div
          data-testid="compliance-empty-state"
          className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500 text-xs space-y-3 shadow-xs"
        >
          <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-800">
              No Active Compliance Audit Loaded
            </h3>
            <p className="text-gray-400 text-xs mt-1 max-w-md mx-auto">
              {activePortfolio
                ? `Click "Run Compliance & Grounding Audit" to trigger programmatic claim verification for ${activePortfolio.name}. Audits are strictly on-demand to enforce zero token waste.`
                : 'Select an active portfolio from the top header to run compliance and grounding verification.'}
            </p>
          </div>
          {activePortfolio && (
            <div className="pt-2">
              <button
                onClick={handleRunAudit}
                data-testid="empty-run-audit-btn"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition cursor-pointer"
              >
                Run Compliance &amp; Grounding Audit
              </button>
            </div>
          )}
        </div>
      )}

      {/* Loaded Audit Report Content */}
      {!isLoading && aiReport && (
        <div className="space-y-6">
          {/* Section 1: Regulatory & Compliance Boundary Notice */}
          <div
            data-testid="compliance-regulatory-notice"
            className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-2 shadow-xs"
          >
            <div className="flex items-center space-x-2 font-bold text-amber-950">
              <ShieldCheck className="w-4 h-4 text-amber-700" />
              <span>
                Regulatory Notice &amp; Automated Verification Boundary
              </span>
            </div>
            <p className="leading-relaxed text-[11px] text-amber-900">
              <strong>Non-Advisory Notice:</strong> This software is an engineering and educational intelligence platform. It is <strong>NOT</strong> registered with SEBI (Securities and Exchange Board of India) as an Investment Adviser (RIA), Research Analyst (RA), or Portfolio Management Service (PMS). All analytics, insights, and risk calculations are non-advisory demonstrations.
            </p>
            <p className="leading-relaxed text-[11px] text-amber-900">
              <strong>Automated Software Boundary:</strong> All claim verification, numerical consistency checks, and grounding audits shown on this panel represent <strong>automated programmatic validation rules</strong>. They do <strong>NOT</strong> constitute human compliance approval, regulatory certification, or professional financial sign-off.
            </p>
          </div>

          {/* Section 2: Verification Status & Claim-Grounding Findings Audit */}
          <div
            data-testid="grounding-verification-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-5"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-600" />
                  <span>Programmatic Grounding Verification Findings</span>
                </h3>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Granular claim veracity checks comparing generated intelligence statements directly against verified evidence.
                </p>
              </div>

              {/* Status Badge */}
              <div>
                {isRejected ? (
                  <span
                    data-testid="verification-status-rejected"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300"
                  >
                    <XCircle className="w-3.5 h-3.5 text-rose-600" />
                    <span>AUDIT REJECTED</span>
                  </span>
                ) : isFlagged ? (
                  <span
                    data-testid="verification-status-flagged"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span>ACCEPTABLE WITH WARNINGS</span>
                  </span>
                ) : isFullyVerified ? (
                  <span
                    data-testid="verification-status-verified"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>PROGRAMMATICALLY VERIFIED</span>
                  </span>
                ) : (
                  <span
                    data-testid="verification-status-acceptable"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-300"
                  >
                    <Info className="w-3.5 h-3.5 text-blue-600" />
                    <span>ACCEPTABLE (PENDING REVIEW)</span>
                  </span>
                )}
              </div>
            </div>

            {/* Prominent Warning if Rejected */}
            {isRejected && (
              <div
                role="alert"
                data-testid="rejected-prominent-warning"
                className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 space-y-1"
              >
                <div className="flex items-center space-x-2 font-bold text-rose-950">
                  <AlertOctagon className="w-4 h-4 text-rose-600" />
                  <span>Grounding Rejection Warning — Hallucinations or Grounding Violations Detected</span>
                </div>
                <p className="leading-relaxed text-[11px] text-rose-800">
                  The automated grounding engine detected{' '}
                  <strong>{aiReport.grounding_report.rejected_count} rejected claims</strong> or determined that the report failed acceptable veracity standards (is_acceptable = false).
                  This intelligence output must <strong>NOT</strong> be relied upon and is rejected by system policy.
                </p>
              </div>
            )}

            {/* Warning if Acceptable with Flagged Discrepancies */}
            {isFlagged && !isRejected && (
              <div
                role="alert"
                data-testid="flagged-discrepancy-warning"
                className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1"
              >
                <div className="flex items-center space-x-2 font-bold text-amber-950">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span>Acceptable with Warnings — Discrepancies Flagged</span>
                </div>
                <p className="leading-relaxed text-[11px] text-amber-800">
                  While the report is deemed acceptable under baseline thresholds (is_acceptable = true), the verification engine flagged{' '}
                  <strong>{aiReport.grounding_report.flagged_count} discrepancy finding(s)</strong>.
                  Inspect the flagged findings below before accepting insights.
                </p>
              </div>
            )}

            {/* KPI Summary Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center text-xs">
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Claims Checked
                </span>
                <p
                  data-testid="grounding-total-checked"
                  className="text-xl font-bold text-gray-800 mt-0.5"
                >
                  {aiReport.grounding_report.total_claims_checked}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Passed / Verified
                </span>
                <p
                  data-testid="grounding-passed-count"
                  className="text-xl font-bold text-emerald-600 mt-0.5"
                >
                  {aiReport.grounding_report.passed_count}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Flagged Warnings
                </span>
                <p
                  data-testid="grounding-flagged-count"
                  className="text-xl font-bold text-amber-600 mt-0.5"
                >
                  {aiReport.grounding_report.flagged_count}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Rejected Claims
                </span>
                <p
                  data-testid="grounding-rejected-count"
                  className="text-xl font-bold text-rose-600 mt-0.5"
                >
                  {aiReport.grounding_report.rejected_count}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 col-span-2 sm:col-span-1">
                <span className="text-gray-500 text-[10px] uppercase font-semibold">
                  Engine Acceptable
                </span>
                <p
                  data-testid="grounding-is-acceptable"
                  className={`text-xl font-bold mt-0.5 font-mono ${
                    aiReport.grounding_report.is_acceptable
                      ? 'text-blue-600'
                      : 'text-rose-600'
                  }`}
                >
                  {aiReport.grounding_report.is_acceptable ? 'TRUE' : 'FALSE'}
                </p>
              </div>
            </div>

            {/* Findings Filter & Table */}
            <div className="space-y-3 pt-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide flex items-center space-x-1.5">
                  <Filter className="w-3.5 h-3.5 text-gray-500" />
                  <span>Validation Findings Audit Log ({filteredFindings.length})</span>
                </h4>

                {/* Status Filter Buttons */}
                <div className="inline-flex rounded-lg border border-gray-200 p-0.5 bg-gray-50 text-[11px]">
                  {(['ALL', 'PASSED', 'FLAGGED', 'REJECTED'] as const).map(
                    (status) => (
                      <button
                        key={status}
                        onClick={() => setFindingFilter(status)}
                        data-testid={`filter-${status.toLowerCase()}`}
                        className={`px-2.5 py-1 rounded font-medium transition cursor-pointer ${
                          findingFilter === status
                            ? 'bg-white text-gray-900 shadow-2xs font-semibold'
                            : 'text-gray-500 hover:text-gray-800'
                        }`}
                      >
                        {status}
                      </button>
                    )
                  )}
                </div>
              </div>

              {filteredFindings.length > 0 ? (
                <div className="border border-gray-200 rounded-lg overflow-x-auto">
                  <table
                    data-testid="grounding-findings-table"
                    className="min-w-full divide-y divide-gray-200 text-xs text-left"
                  >
                    <thead className="bg-gray-50 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                      <tr>
                        <th className="px-3.5 py-2.5">Rule / Check Name</th>
                        <th className="px-3.5 py-2.5">Target Identifier</th>
                        <th className="px-3.5 py-2.5">Status</th>
                        <th className="px-3.5 py-2.5">Finding Details / Discrepancy</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-white">
                      {filteredFindings.map((f, idx) => (
                        <tr
                          key={`${f.check_name}-${f.target_id}-${idx}`}
                          data-testid={`finding-row-${f.check_name}-${f.target_id}`}
                          className="hover:bg-gray-50/70 transition"
                        >
                          <td className="px-3.5 py-2.5 font-mono font-bold text-gray-800">
                            {f.check_name}
                          </td>
                          <td className="px-3.5 py-2.5 font-mono text-[11px] text-gray-600">
                            {f.target_id}
                          </td>
                          <td className="px-3.5 py-2.5">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                                f.status === 'PASSED'
                                  ? 'bg-emerald-50 text-emerald-700'
                                  : f.status === 'FLAGGED'
                                  ? 'bg-amber-50 text-amber-700'
                                  : 'bg-rose-50 text-rose-700'
                              }`}
                            >
                              {f.status}
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5 text-gray-600 text-[11px]">
                            {f.reason ? (
                              <p className="font-semibold text-gray-800">
                                {f.reason}
                              </p>
                            ) : (
                              <p className="text-emerald-700 font-medium">
                                Verified consistent against portfolio evidence bundle.
                              </p>
                            )}
                            {f.details && Object.keys(f.details).length > 0 && (
                              <div className="mt-1 p-1.5 bg-gray-50 rounded border border-gray-100 font-mono text-[10px] text-gray-500 max-w-md truncate">
                                {JSON.stringify(f.details)}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div
                  data-testid="empty-findings-notice"
                  className="py-6 text-center text-gray-400 text-xs bg-gray-50 rounded-lg border border-gray-200"
                >
                  No findings match the selected status filter ({findingFilter}).
                </div>
              )}
            </div>
          </div>

          {/* Section 3: Supported vs. Unsupported Claims & Grounded Key Drivers */}
          <div
            data-testid="grounded-claims-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
          >
            <div className="pb-2 border-b border-gray-100">
              <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
                <FileText className="w-4 h-4 text-purple-600" />
                <span>Evidence-Backed Claims &amp; Metric Verification</span>
              </h3>
              <p className="text-[11px] text-gray-500 mt-0.5">
                Audit trace linking individual intelligence drivers to exact factual metrics in backend storage.
              </p>
            </div>

            {aiReport.key_drivers.length > 0 ? (
              <div className="border border-gray-200 rounded-lg overflow-x-auto">
                <table
                  data-testid="key-drivers-audit-table"
                  className="min-w-full divide-y divide-gray-200 text-xs text-left"
                >
                  <thead className="bg-gray-50 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    <tr>
                      <th className="px-3.5 py-2.5">Driver ID</th>
                      <th className="px-3.5 py-2.5">Claim / Driver Statement</th>
                      <th className="px-3.5 py-2.5">Verification</th>
                      <th className="px-3.5 py-2.5">Cited Metric Key</th>
                      <th className="px-3.5 py-2.5">Cited Value</th>
                      <th className="px-3.5 py-2.5">Source Reference</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {aiReport.key_drivers.map((kd) => (
                      <tr
                        key={kd.driver_id}
                        data-testid={`driver-row-${kd.driver_id}`}
                        className="hover:bg-gray-50/70 transition"
                      >
                        <td className="px-3.5 py-2.5 font-mono font-bold text-gray-800">
                          {kd.driver_id}
                        </td>
                        <td className="px-3.5 py-2.5 max-w-xs text-gray-700">
                          <p className="font-semibold text-gray-900">
                            {kd.title}
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {kd.statement}
                          </p>
                        </td>
                        <td className="px-3.5 py-2.5">
                          <span
                            data-testid={`driver-grounded-${kd.driver_id}`}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                              kd.is_grounded
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {kd.is_grounded ? 'SUPPORTED' : 'UNSUPPORTED'}
                          </span>
                        </td>
                        <td className="px-3.5 py-2.5 font-mono text-[11px] text-gray-600">
                          {kd.supporting_metric_key}
                        </td>
                        <td className="px-3.5 py-2.5 font-mono font-bold text-gray-800">
                          {typeof kd.supporting_metric_value === 'object'
                            ? JSON.stringify(kd.supporting_metric_value)
                            : String(kd.supporting_metric_value)}
                        </td>
                        <td className="px-3.5 py-2.5 font-mono text-[10px] text-gray-500">
                          {kd.source_reference}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-gray-400 py-3">
                No key drivers cited in this intelligence report.
              </p>
            )}
          </div>

          {/* Section 4: Confidence Limitations, Uncertainty Disclosures & Data Gaps */}
          <div
            data-testid="confidence-limitations-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
          >
            <div className="pb-2 border-b border-gray-100">
              <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
                <Info className="w-4 h-4 text-blue-600" />
                <span>Confidence Assessment, Limitations &amp; Uncertainty Disclosures</span>
              </h3>
              <p className="text-[11px] text-gray-500 mt-0.5">
                Heuristic confidence calibration bounds, penalty discounts for missing data, and explicit data gaps.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Confidence Score & Tier */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                  Confidence Score &amp; Tier
                </span>
                <div className="flex items-baseline space-x-2">
                  <span
                    data-testid="confidence-score-val"
                    className="text-2xl font-bold text-gray-900"
                  >
                    {(Number(aiReport.confidence.score) * 100).toFixed(0)}%
                  </span>
                  <span
                    data-testid="confidence-level-tier"
                    className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800"
                  >
                    {aiReport.confidence.level}
                  </span>
                </div>
                <p className="text-[11px] text-gray-500">
                  Heuristic scoring calibrated from 0.00 to 1.00 based on position coverage.
                </p>
              </div>

              {/* Data Quality Deduction */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                  Data Quality Discount
                </span>
                <p
                  data-testid="confidence-data-discount"
                  className="text-2xl font-bold text-amber-600 font-mono"
                >
                  -{(Number(aiReport.confidence.data_quality_discount) * 100).toFixed(0)}%
                </p>
                <p className="text-[11px] text-gray-500">
                  Penalty applied for unpriced holdings or missing valuation snapshots.
                </p>
              </div>

              {/* Staleness Deduction */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                  Staleness Discount
                </span>
                <p
                  data-testid="confidence-stale-discount"
                  className="text-2xl font-bold text-amber-600 font-mono"
                >
                  -{(Number(aiReport.confidence.staleness_discount) * 100).toFixed(0)}%
                </p>
                <p className="text-[11px] text-gray-500">
                  Penalty applied for emergency stale quote fallbacks or outdated cached prices.
                </p>
              </div>
            </div>

            {/* Mandatory Calibration Limitation Notice */}
            <div
              data-testid="calibration-limitation-notice"
              className="p-3.5 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-900 space-y-1"
            >
              <div className="flex items-center space-x-1.5 font-bold text-blue-950">
                <Clock className="w-3.5 h-3.5 text-blue-600" />
                <span>Mandatory Confidence Calibration Limitation</span>
              </div>
              <p className="leading-relaxed text-[11px] text-blue-900">
                {aiReport.confidence.calibration_limitation}
              </p>
            </div>

            {/* Uncertainty and Data Gaps List */}
            <div
              data-testid="uncertainty-gaps-list"
              className="space-y-2 pt-1"
            >
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Explicit Uncertainty Disclosures &amp; Data Gaps ({aiReport.uncertainty_and_gaps.length})
              </h4>
              {aiReport.uncertainty_and_gaps.length > 0 ? (
                <div className="space-y-1.5">
                  {aiReport.uncertainty_and_gaps.map((gap, i) => (
                    <div
                      key={i}
                      data-testid={`uncertainty-gap-item-${i}`}
                      className="p-2.5 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-700 flex items-start space-x-2"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
                      <span className="leading-relaxed text-[11px]">{gap}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 py-2">
                  No explicit data gaps identified in the current evidence bundle.
                </p>
              )}
            </div>
          </div>

          {/* Section 5: Safeguards, Rejection Precedence & Legal Disclaimers */}
          <div
            data-testid="safeguards-and-disclaimers-section"
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
          >
            <div className="pb-2 border-b border-gray-100">
              <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Recommendation Rejection Safeguards &amp; Disclaimers</span>
              </h3>
              <p className="text-[11px] text-gray-500 mt-0.5">
                Deterministic fail-safe enforcement rules preventing hallucinated or ungrounded claims from displaying as verified.
              </p>
            </div>

            {/* Safeguard Precedence Explanation */}
            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-700 space-y-1.5">
              <span className="font-bold text-gray-900 text-xs">
                Grounding Fail-Safe Policy Invariant
              </span>
              <p className="text-[11px] leading-relaxed text-gray-600">
                1. <strong>Precedence Rule:</strong> Any claim that fails numerical veracity, cites an unverified stock ticker, or produces an ungrounded metric triggers an automated rejection. If <code>rejected_count &gt; 0</code> or <code>is_acceptable === false</code>, the entire report review status is forced to <code>REJECTED</code>.
              </p>
              <p className="text-[11px] leading-relaxed text-gray-600">
                2. <strong>Warning Rule:</strong> If discrepancies are flagged (<code>flagged_count &gt; 0</code>), the report status cannot be labeled as fully verified and must display prominent warning banners even if baseline acceptance holds.
              </p>
            </div>

            {/* Disclaimers List */}
            <div className="space-y-2 pt-1">
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Regulatory &amp; Simulation Disclaimers
              </h4>
              <div
                data-testid="disclaimers-list"
                className="space-y-1.5"
              >
                {aiReport.disclaimers.map((disc, idx) => (
                  <div
                    key={idx}
                    data-testid={`disclaimer-item-${idx}`}
                    className="p-2.5 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-600 leading-relaxed flex items-start space-x-2"
                  >
                    <Info className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                    <span>{disc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Section 6: Honest Audit Persistence & Governance Boundaries */}
          <div
            data-testid="persistence-disclosure-section"
            className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-[11px] text-gray-500 space-y-1.5"
          >
            <div className="flex items-center space-x-1.5 text-gray-700 font-bold">
              <Database className="w-3.5 h-3.5 text-gray-500" />
              <span>Audit Trail Storage &amp; Persistence Boundaries</span>
            </div>
            <p className="leading-relaxed">
              The backend generates and evaluates claim grounding dynamically on demand. Audit reports, verification finding logs, and review states are <strong>not persisted</strong> in backend database tables. SQLite retains only investment portfolios and asset holdings. No long-term historical revision audit trail or human approval records exist in backend storage.
            </p>
          </div>
        </div>
      )}
    </section>
  );
};
