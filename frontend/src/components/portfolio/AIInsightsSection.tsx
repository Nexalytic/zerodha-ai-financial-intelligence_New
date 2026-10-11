import React from 'react';
import {
  AIInsightReport,
  ReviewStatus,
  AlertSeverity,
} from '../../types/aiReasoning';
import {
  Brain,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  AlertCircle,
} from 'lucide-react';

export interface AIInsightsSectionProps {
  aiReport: AIInsightReport | null;
  isGenerating: boolean;
  error: string | null;
  onGenerate: () => void;
  portfolioId?: string | null;
}

export const AIInsightsSection: React.FC<AIInsightsSectionProps> = ({
  aiReport,
  isGenerating,
  error,
  onGenerate,
}) => {
  const isRejected =
    aiReport?.review_status === 'REJECTED' ||
    aiReport?.grounding_report?.is_acceptable === false ||
    (aiReport?.grounding_report?.rejected_count ?? 0) > 0;

  const getReviewStatusBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span
            data-testid="ai-status-verified"
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>VERIFIED GROUNDED</span>
          </span>
        );
      case 'FLAGGED_WITH_WARNINGS':
        return (
          <span
            data-testid="ai-status-flagged"
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300"
          >
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>FLAGGED WITH WARNINGS</span>
          </span>
        );
      case 'REJECTED':
      default:
        return (
          <span
            data-testid="ai-status-rejected"
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-900 border border-rose-300"
          >
            <XCircle className="w-4 h-4 text-rose-600" />
            <span>CLAIM GROUNDING REJECTED</span>
          </span>
        );
    }
  };

  const getAlertSeverityBadge = (severity: AlertSeverity) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-orange-100 text-orange-800 border border-orange-200">
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            MEDIUM
          </span>
        );
      case 'LOW':
      case 'INFO':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            {severity}
          </span>
        );
    }
  };

  return (
    <div
      data-testid="ai-insights-section"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header Banner */}
      <div className="p-6 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-purple-50 text-purple-600 rounded-xl">
            <Brain className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-lg font-bold text-gray-900 tracking-tight">
                Evidence-Grounded AI Intelligence
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
                Grounding Engine v2
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Strictly verifiable narrative synthesis backed by quantitative evidence citations and claim validation.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={onGenerate}
            disabled={isGenerating}
            data-testid="generate-ai-btn"
            className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Synthesizing Evidence...' : 'Generate AI Report'}</span>
          </button>
        </div>
      </div>

      <div className="p-6">
        {/* Error State */}
        {error && (
          <div
            data-testid="ai-error-banner"
            className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 mb-6 flex items-start space-x-3"
          >
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-rose-900">AI Intelligence Generation Failed</p>
              <p className="mt-1 text-rose-700 leading-relaxed">{error}</p>
              <p className="mt-2 text-[11px] text-rose-600">
                Ensure provider settings are valid and that network transport or rate limit quotas are not exceeded.
              </p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div data-testid="ai-loading-state" className="py-12 text-center text-gray-600">
            <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold text-gray-800">
              Gathering Evidence & Executing Grounded Reasoning...
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Verifying 4-component risk scores, assembling market snapshots, and checking claim grounding.
            </p>
          </div>
        )}

        {/* Initial Empty State before generation */}
        {!aiReport && !isGenerating && !error && (
          <div data-testid="ai-uninitialized-state" className="py-12 text-center text-gray-500">
            <div className="w-12 h-12 rounded-full bg-purple-50 text-purple-600 flex items-center justify-center mx-auto mb-3">
              <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-gray-800">
              No AI Intelligence Report Generated Yet
            </h4>
            <p className="text-xs text-gray-500 max-w-md mx-auto mt-1 leading-relaxed">
              Click &ldquo;Generate AI Report&rdquo; to assemble the structured evidence bundle and trigger verifiable,
              deterministic heuristic intelligence.
            </p>
          </div>
        )}

        {/* Rendered AI Insight Report */}
        {aiReport && !isGenerating && (
          <div className="space-y-6">
            {/* Top Review Status Banner */}
            <div
              className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                isRejected
                  ? 'bg-rose-50 border-rose-300'
                  : aiReport.review_status === 'FLAGGED_WITH_WARNINGS'
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-emerald-50 border-emerald-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                {getReviewStatusBadge(aiReport.review_status)}
                <div>
                  <p className="text-xs font-bold text-gray-900">
                    Provider: {aiReport.provider_name} &bull; Model: {aiReport.model_id}
                  </p>
                  <p className="text-[11px] text-gray-500">
                    Generated: {new Date(aiReport.generated_at).toLocaleString()} &bull;{' '}
                    {aiReport.is_simulated ? 'Simulated Intelligence Engine' : 'Live Engine'}
                  </p>
                </div>
              </div>

              {isRejected && (
                <div
                  data-testid="rejected-warning-notice"
                  className="p-2.5 rounded bg-rose-100 text-rose-900 font-bold text-xs border border-rose-300"
                >
                  CRITICAL: REPORT REJECTED — Do not display or act on ungrounded claims!
                </div>
              )}
            </div>

            {/* Executive Summary */}
            <div className="p-5 rounded-xl bg-gray-50 border border-gray-200">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Executive Narrative Summary
              </h4>
              <p
                data-testid="ai-executive-summary"
                className="text-sm text-gray-800 leading-relaxed whitespace-pre-line"
              >
                {aiReport.executive_summary}
              </p>
            </div>

            {/* Confidence & Calibration Limitations */}
            <div className="p-5 rounded-xl bg-blue-50/50 border border-blue-200 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs font-semibold text-blue-900 uppercase tracking-wider">
                  Confidence Score
                </p>
                <div className="flex items-baseline space-x-2 mt-1">
                  <span
                    data-testid="ai-confidence-score"
                    className="text-2xl font-bold text-blue-950"
                  >
                    {(parseFloat(String(aiReport.confidence.score)) * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                    {aiReport.confidence.level}
                  </span>
                </div>
              </div>

              <div className="md:col-span-2">
                <p className="text-xs font-semibold text-blue-900 uppercase tracking-wider">
                  Mandatory Calibration Limitation Disclosure
                </p>
                <p
                  data-testid="calibration-limitation-text"
                  className="text-xs text-blue-800 mt-1 leading-relaxed"
                >
                  {aiReport.confidence.calibration_limitation}
                </p>
                <div className="flex items-center space-x-3 mt-2 text-[11px] text-blue-700">
                  <span>
                    Quality Discount:{' '}
                    <strong>
                      {(parseFloat(String(aiReport.confidence.data_quality_discount)) * 100).toFixed(0)}%
                    </strong>
                  </span>
                  <span>
                    Staleness Discount:{' '}
                    <strong>
                      {(parseFloat(String(aiReport.confidence.staleness_discount)) * 100).toFixed(0)}%
                    </strong>
                  </span>
                </div>
              </div>
            </div>

            {/* Key Drivers with Evidence Citations */}
            <div>
              <h4 className="text-sm font-bold text-gray-900 tracking-tight mb-3">
                Key Performance & Concentration Drivers
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {aiReport.key_drivers.map((driver) => (
                  <div
                    key={driver.driver_id}
                    data-testid={`key-driver-${driver.driver_id}`}
                    className="p-4 rounded-xl border border-gray-200 bg-white hover:bg-gray-50/50 transition"
                  >
                    <div className="flex items-center justify-between pb-2 border-b border-gray-100 mb-2">
                      <span className="text-xs font-bold text-gray-900">{driver.title}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-gray-100 text-gray-700">
                        {driver.driver_type}
                      </span>
                    </div>

                    <p className="text-xs text-gray-600 leading-relaxed mb-3">
                      {driver.statement}
                    </p>

                    <div className="p-2 rounded bg-gray-50 text-[11px] font-mono text-gray-700 border border-gray-200">
                      <div className="text-[10px] text-gray-400 font-sans uppercase font-medium">
                        Cited Evidence Path
                      </div>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-blue-700 truncate" title={driver.supporting_metric_key}>
                          {driver.supporting_metric_key}
                        </span>
                        <span className="font-bold text-gray-900 ml-2">
                          {String(driver.supporting_metric_value)}
                        </span>
                      </div>
                      <div className="text-[10px] text-gray-500 mt-1">
                        Source: {driver.source_reference}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Prioritized Risk Alerts */}
            {aiReport.risk_alerts.length > 0 && (
              <div>
                <h4 className="text-sm font-bold text-gray-900 tracking-tight mb-3">
                  Prioritized Risk Warnings
                </h4>
                <div className="space-y-3">
                  {aiReport.risk_alerts.map((alert) => (
                    <div
                      key={alert.alert_id}
                      data-testid={`risk-alert-${alert.alert_id}`}
                      className="p-4 rounded-xl border border-gray-200 bg-white"
                    >
                      <div className="flex items-center space-x-2 mb-1.5">
                        {getAlertSeverityBadge(alert.severity)}
                        <span className="text-xs font-semibold text-gray-500 uppercase">
                          {alert.category}
                        </span>
                        <h5 className="text-sm font-bold text-gray-900">{alert.headline}</h5>
                      </div>
                      <p className="text-xs text-gray-600 leading-relaxed">{alert.explanation}</p>
                      {alert.actionable_mitigation && (
                        <div className="mt-2 text-xs text-gray-700 bg-amber-50/70 p-2.5 rounded-lg border border-amber-200">
                          <span className="font-semibold text-amber-900">
                            Educational Observation:{' '}
                          </span>
                          {alert.actionable_mitigation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Claim Grounding Audit Summary */}
            <div className="p-5 rounded-xl bg-gray-50 border border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-5 h-5 text-gray-700" />
                  <h4 className="text-sm font-bold text-gray-900">
                    Programmatic Claim Grounding Audit
                  </h4>
                </div>
                <span
                  data-testid="grounding-acceptable-badge"
                  className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                    aiReport.grounding_report.is_acceptable
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  {aiReport.grounding_report.is_acceptable ? 'ACCEPTABLE' : 'UNACCEPTABLE'}
                </span>
              </div>

              <div className="grid grid-cols-4 gap-2 text-center text-xs mb-4">
                <div className="p-2.5 rounded-lg bg-white border border-gray-200">
                  <p className="text-gray-500 text-[10px]">Claims Checked</p>
                  <p className="text-base font-bold text-gray-900 mt-0.5">
                    {aiReport.grounding_report.total_claims_checked}
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-white border border-gray-200">
                  <p className="text-gray-500 text-[10px]">Passed</p>
                  <p className="text-base font-bold text-emerald-700 mt-0.5">
                    {aiReport.grounding_report.passed_count}
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-white border border-gray-200">
                  <p className="text-gray-500 text-[10px]">Flagged</p>
                  <p className="text-base font-bold text-amber-700 mt-0.5">
                    {aiReport.grounding_report.flagged_count}
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-white border border-gray-200">
                  <p className="text-gray-500 text-[10px]">Rejected</p>
                  <p className="text-base font-bold text-rose-700 mt-0.5">
                    {aiReport.grounding_report.rejected_count}
                  </p>
                </div>
              </div>

              {/* Granular checks findings */}
              {aiReport.grounding_report.findings.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    Detailed Verification Findings
                  </p>
                  {aiReport.grounding_report.findings.map((f, i) => (
                    <div
                      key={i}
                      className="p-2 rounded bg-white border border-gray-200 text-[11px] flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            f.status === 'PASSED'
                              ? 'bg-emerald-500'
                              : f.status === 'FLAGGED'
                              ? 'bg-amber-500'
                              : 'bg-rose-500'
                          }`}
                        />
                        <span className="font-mono text-gray-800">{f.check_name}</span>
                        <span className="text-gray-400">({f.target_id})</span>
                      </div>
                      <span
                        className={`font-semibold ${
                          f.status === 'PASSED'
                            ? 'text-emerald-700'
                            : f.status === 'FLAGGED'
                            ? 'text-amber-700'
                            : 'text-rose-700'
                        }`}
                      >
                        {f.status}
                        {f.reason && <span className="font-normal text-gray-500 ml-1.5">— {f.reason}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Disclaimers */}
            <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-[11px] text-gray-500 space-y-1">
              <p className="font-semibold text-gray-700">Compliance & Regulatory Notice:</p>
              {aiReport.disclaimers.map((d, i) => (
                <p key={i}>&bull; {d}</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
