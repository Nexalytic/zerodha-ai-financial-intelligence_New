import React from 'react';
import { AIInsightReport } from '../../types/aiReasoning';
import {
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Layers,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';

export interface AIExplanationSectionProps {
  aiReport: AIInsightReport | null;
  portfolioId: string | null;
  portfolioName?: string;
  isGenerating: boolean;
  error: string | null;
  onGenerate: () => void;
}

export const AIExplanationSection: React.FC<AIExplanationSectionProps> = ({
  aiReport,
  portfolioId,
  portfolioName,
  isGenerating,
  error,
  onGenerate,
}) => {
  const isAcceptable = aiReport?.grounding_report?.is_acceptable ?? true;
  const isRejected =
    aiReport?.review_status === 'REJECTED' || !isAcceptable;
  const isVerified =
    aiReport?.review_status === 'VERIFIED' && isAcceptable;

  return (
    <div
      data-testid="ai-explanation-section"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header */}
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Evidence-Grounded AI Movement Explainer
            </h2>
            <p className="text-xs text-gray-500">
              Deterministic evidence synthesis explaining macro drivers, sector rotation, and portfolio performance.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {aiReport && (
            <div className="flex items-center space-x-2">
              {isRejected ? (
                <span
                  data-testid="ai-status-rejected"
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200"
                >
                  <AlertOctagon className="w-3.5 h-3.5 text-rose-600" />
                  <span>GROUNDING REJECTED</span>
                </span>
              ) : isVerified ? (
                <span
                  data-testid="ai-status-verified"
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>FACT-GROUNDED VERIFIED</span>
                </span>
              ) : (
                <span
                  data-testid="ai-status-flagged"
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  <span>FLAGGED WITH WARNINGS</span>
                </span>
              )}
            </div>
          )}

          <button
            onClick={onGenerate}
            disabled={isGenerating || !portfolioId}
            data-testid="generate-ai-explanation-btn"
            className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Synthesizing Movements...' : 'Synthesize AI Movement Attribution'}</span>
          </button>
        </div>
      </div>

      <div className="p-5 space-y-6">
        {/* Explanatory Callout: Portfolio-Level Scope Limitation */}
        <div
          data-testid="ai-scope-disclaimer"
          className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200 text-xs text-blue-900 flex items-start space-x-2.5"
        >
          <Layers className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-semibold text-blue-950">
              Portfolio-Level AI Synthesis Model
            </p>
            <p className="text-blue-800 leading-relaxed text-[11px]">
              Portfolio-level AI synthesis scope: grounded in structural weights and portfolio telemetry. It does not generate independent ungrounded single-stock forecasts or predictive price targets.
            </p>
          </div>
        </div>

        {error ? (
          <div
            data-testid="ai-error-banner"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">AI Movement Synthesis Failed</p>
              <p className="mt-0.5 text-rose-700">{error}</p>
              <button
                onClick={onGenerate}
                data-testid="retry-ai-btn"
                className="mt-2.5 px-3 py-1 bg-rose-600 text-white rounded text-[11px] font-semibold hover:bg-rose-700 cursor-pointer shadow-2xs"
              >
                Retry Movement Synthesis
              </button>
            </div>
          </div>
        ) : isGenerating ? (
          <div
            data-testid="ai-explanation-loading"
            className="py-12 text-center text-gray-500 text-xs space-y-2"
          >
            <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="font-semibold text-gray-800">
              Generating Fact-Checked Market Movement Attribution...
            </p>
            <p className="text-gray-400 text-[11px]">
              Extracting portfolio price drivers and verifying claims against ground-truth ledger data.
            </p>
          </div>
        ) : !aiReport ? (
          <div
            data-testid="ai-explanation-empty"
            className="py-8 text-center text-gray-400 text-xs flex flex-col items-center justify-center space-y-1.5"
          >
            <HelpCircle className="w-8 h-8 text-gray-300" />
            <p className="font-semibold text-gray-600">
              No movement attribution generated yet {portfolioName ? `for ${portfolioName}` : ''}
            </p>
            <p className="text-gray-400">
              Click &ldquo;Synthesize AI Movement Attribution&rdquo; to analyze market drivers and grounded evidence.
            </p>
          </div>
        ) : (
          <div data-testid="ai-report-content" className="space-y-6">
            {/* Rejection Warning Banner */}
            {isRejected && (
              <div
                data-testid="grounding-rejected-banner"
                className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 space-y-2"
              >
                <div className="flex items-start space-x-2.5">
                  <AlertOctagon className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">AI Output Rejected by Grounding Guardrails</p>
                    <p className="mt-0.5 text-rose-800 leading-relaxed text-[11px]">
                      {aiReport.grounding_report?.flagged_count ?? 0} of{' '}
                      {aiReport.grounding_report?.total_claims_checked ?? 0} statements flagged as ungrounded.
                    </p>
                  </div>
                </div>
                {aiReport.grounding_report?.findings &&
                  aiReport.grounding_report.findings.length > 0 && (
                    <div className="pt-1.5 border-t border-rose-200/60 space-y-1 pl-7">
                      {aiReport.grounding_report.findings
                        .filter((f) => f.status !== 'PASSED')
                        .map((f, idx) => (
                          <p key={f.target_id || idx} className="text-[11px] text-rose-800">
                            &bull; {f.reason || `${f.check_name}: Flagged`}
                          </p>
                        ))}
                    </div>
                  )}
              </div>
            )}

            {/* Verified Banner */}
            {isVerified && (
              <div
                data-testid="grounding-verified-banner"
                className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 space-y-1.5"
              >
                <div className="flex items-start space-x-2.5">
                  <ShieldCheck className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">
                      Grounding Guardrail Verified ({aiReport.grounding_report?.passed_count ?? 0}/
                      {aiReport.grounding_report?.total_claims_checked ?? 0} claims confirmed)
                    </p>
                    <p className="text-emerald-800 text-[11px]">
                      All synthesized statements cross-examined and validated against portfolio telemetry.
                    </p>
                  </div>
                </div>
                {aiReport.grounding_report?.findings &&
                  aiReport.grounding_report.findings.length > 0 && (
                    <div className="pt-1.5 border-t border-emerald-200/60 space-y-1 pl-7">
                      {aiReport.grounding_report.findings.map((f, idx) => (
                        <p
                          key={f.target_id || idx}
                          data-testid={`grounding-note-${idx}`}
                          className="text-[11px] text-emerald-800"
                        >
                          &bull; {f.reason || `${f.check_name}: Verified`}
                        </p>
                      ))}
                    </div>
                  )}
              </div>
            )}

            {/* Executive Summary */}
            <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-200 space-y-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Executive Movement Summary
              </span>
              <p
                data-testid="ai-summary"
                className="text-sm text-gray-800 leading-relaxed font-serif"
              >
                {aiReport.executive_summary}
              </p>
            </div>

            {/* Key Drivers */}
            {aiReport.key_drivers && aiReport.key_drivers.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Verified Key Drivers ({aiReport.key_drivers.length})
                </h3>
                <div
                  data-testid="ai-key-drivers"
                  className="grid grid-cols-1 md:grid-cols-2 gap-3"
                >
                  {aiReport.key_drivers.map((driver, idx) => (
                    <div
                      key={driver.driver_id || `driver-${idx}`}
                      data-testid={`ai-driver-${idx}`}
                      className="p-3.5 rounded-lg border border-gray-200 bg-white space-y-1 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-50 text-blue-700">
                          {driver.driver_type}
                        </span>
                        {driver.is_grounded && (
                          <span className="text-[10px] text-emerald-700 font-semibold inline-flex items-center space-x-0.5">
                            <ShieldCheck className="w-3 h-3 text-emerald-600 inline mr-0.5" />
                            Grounded
                          </span>
                        )}
                      </div>
                      <h4 className="font-semibold text-gray-900 pt-0.5">
                        {driver.title}
                      </h4>
                      <p className="text-gray-600 text-[11px] leading-relaxed">
                        {driver.statement}
                      </p>
                      <div className="pt-1.5 border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                        <span>Metric: {driver.supporting_metric_key}</span>
                        <span>Ref: {driver.source_reference}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Synthesized Risk Alerts */}
            {aiReport.risk_alerts && aiReport.risk_alerts.length > 0 && (
              <div className="space-y-3" data-testid="ai-risk-alerts">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Synthesized Risk Alerts ({aiReport.risk_alerts.length})
                </h3>
                <div className="space-y-2">
                  {aiReport.risk_alerts.map((alert, idx) => (
                    <div
                      key={alert.alert_id || `alert-${idx}`}
                      data-testid={`ai-risk-alert-${idx}`}
                      className="p-3.5 rounded-lg border border-amber-200 bg-amber-50/60 text-xs text-amber-900 flex items-start space-x-2.5"
                    >
                      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 space-y-0.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold">{alert.headline}</span>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-100 text-amber-800">
                            {alert.severity}
                          </span>
                        </div>
                        <p className="text-[11px] text-amber-800 leading-relaxed">
                          {alert.explanation}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Confidence & Grounding Findings */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              {/* Confidence Indicator */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Model Confidence &amp; Limitation
                </span>
                <div className="flex items-baseline space-x-2 pt-1">
                  <span
                    data-testid="ai-confidence-score"
                    className="text-2xl font-bold text-gray-900"
                  >
                    {String(aiReport.confidence?.score ?? '—')}
                  </span>
                  <span className="text-xs font-semibold text-gray-600">
                    ({aiReport.confidence?.level || 'UNRATED'} LEVEL)
                  </span>
                </div>
                <p className="text-[11px] text-gray-500 leading-snug pt-1">
                  {aiReport.confidence?.calibration_limitation ||
                    'Calibration limited to evidence observed in current snapshot.'}
                </p>
              </div>

              {/* Grounding Verification Metrics */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Fact Grounding Audit
                </span>
                <div className="grid grid-cols-3 gap-2 pt-1 text-center font-mono">
                  <div className="p-1.5 bg-white rounded border border-gray-100">
                    <span className="text-lg font-bold text-emerald-600 block">
                      {aiReport.grounding_report?.passed_count ?? 0}
                    </span>
                    <span className="text-[10px] text-gray-500">Passed</span>
                  </div>
                  <div className="p-1.5 bg-white rounded border border-gray-100">
                    <span className="text-lg font-bold text-amber-600 block">
                      {aiReport.grounding_report?.flagged_count ?? 0}
                    </span>
                    <span className="text-[10px] text-gray-500">Flagged</span>
                  </div>
                  <div className="p-1.5 bg-white rounded border border-gray-100">
                    <span className="text-lg font-bold text-rose-600 block">
                      {aiReport.grounding_report?.rejected_count ?? 0}
                    </span>
                    <span className="text-[10px] text-gray-500">Rejected</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Disclaimers & Provenance */}
            <div className="pt-3 border-t border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-[10px] text-gray-400 font-mono">
              <div>
                <span>Provider: {aiReport.provider_name}</span>
                <span className="mx-1">&bull;</span>
                <span>Model: {aiReport.model_id}</span>
                {aiReport.is_simulated && (
                  <>
                    <span className="mx-1">&bull;</span>
                    <span className="text-blue-600">Simulated Demo Reasoner</span>
                  </>
                )}
              </div>
              <p className="text-gray-400 font-sans text-right">
                Educational AI insights only. Not SEBI-registered investment advice.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
