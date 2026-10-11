import React from 'react';
import { PortfolioInsightsResponse } from '../../types/aiReasoning';
import {
  Sparkles,
  AlertTriangle,
  Info,
  AlertCircle,
} from 'lucide-react';

export interface RuleBasedInsightsSectionProps {
  insightsResponse: PortfolioInsightsResponse | null;
  isLoading: boolean;
  error: string | null;
}

export const RuleBasedInsightsSection: React.FC<RuleBasedInsightsSectionProps> = ({
  insightsResponse,
  isLoading,
  error,
}) => {
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3 h-3 text-rose-600" />
            <span>CRITICAL</span>
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            <span>WARNING</span>
          </span>
        );
      case 'INFO':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Info className="w-3 h-3 text-blue-600" />
            <span>INFO</span>
          </span>
        );
    }
  };

  const getCategoryBadge = (category: string) => {
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider bg-gray-100 text-gray-700">
        {category}
      </span>
    );
  };

  const insights = insightsResponse?.insights || [];

  return (
    <div
      data-testid="rule-based-insights-section"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-gray-900 tracking-tight">
              Deterministic Portfolio Observations
            </h3>
            <p className="text-xs text-gray-500">
              Rule-based analytics, concentration checks, and diversification metrics.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-gray-400">
          <span>Source: {insightsResponse ? 'RULE_BASED_ANALYTICS' : '—'}</span>
          {insightsResponse?.is_sample_portfolio && (
            <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-[10px] rounded">
              Demo
            </span>
          )}
        </div>
      </div>

      <div className="p-5">
        {error ? (
          <div
            data-testid="rule-insights-error"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Unable to calculate rule-based insights</p>
              <p className="mt-0.5 text-rose-700">{error}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
              <span>Analyzing portfolio structure against financial rules...</span>
            </div>
          </div>
        ) : insights.length === 0 ? (
          <div
            data-testid="no-insights-indicator"
            className="py-8 text-center text-gray-400 text-xs"
          >
            No risk or concentration observations detected for this portfolio.
          </div>
        ) : (
          <div className="space-y-3.5">
            {insights.map((insight) => (
              <div
                key={insight.id}
                data-testid={`insight-card-${insight.id}`}
                className="p-4 rounded-lg border border-gray-100 bg-gray-50/60 hover:bg-gray-50 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 pb-2">
                  <div className="flex items-center space-x-2">
                    {getSeverityBadge(insight.severity)}
                    {getCategoryBadge(insight.category)}
                    <h4 className="text-sm font-semibold text-gray-900 tracking-tight">
                      {insight.title}
                    </h4>
                  </div>
                  {insight.related_symbols && insight.related_symbols.length > 0 && (
                    <div className="flex items-center space-x-1">
                      <span className="text-[10px] text-gray-400">Related:</span>
                      {insight.related_symbols.map((sym) => (
                        <span
                          key={sym}
                          className="px-1.5 py-0.2 bg-white border border-gray-200 rounded text-[10px] font-mono text-gray-700"
                        >
                          {sym}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <p className="text-xs text-gray-600 leading-relaxed mt-1">
                  {insight.description}
                </p>

                {insight.evidence && Object.keys(insight.evidence).length > 0 && (
                  <div className="mt-2.5 p-2 rounded bg-white border border-gray-200 text-[11px] font-mono text-gray-600">
                    <span className="text-gray-400 text-[10px] font-sans block uppercase font-medium">
                      Supporting Evidence
                    </span>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-0.5">
                      {Object.entries(insight.evidence).map(([k, v]) => (
                        <span key={k}>
                          <strong>{k}:</strong> {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 text-[11px] text-gray-400 flex items-center justify-between">
        <span>Deterministic Rule Engine &bull; Non-Advisory Observations</span>
        <span>Not SEBI-registered investment advice</span>
      </div>
    </div>
  );
};
