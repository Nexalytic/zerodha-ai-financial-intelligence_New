import React from 'react';
import {
  PortfolioRiskAssessment,
  ValuationStatus,
} from '../../types/analytics';
import { formatNumber } from '../../utils/formatters';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  Scale,
  Sliders,
} from 'lucide-react';

export interface RiskScoreCardProps {
  riskAssessment: PortfolioRiskAssessment | null | undefined;
  valuationStatus: ValuationStatus | undefined;
  isLoading: boolean;
}

export const RiskScoreCard: React.FC<RiskScoreCardProps> = ({
  riskAssessment,
  valuationStatus,
  isLoading,
}) => {
  const getTierBadge = (
    tier: string | null | undefined,
    testId: string = 'risk-tier-badge'
  ) => {
    switch (tier) {
      case 'LOW':
        return (
          <span
            data-testid={testId}
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>LOW RISK (&le; 30.00)</span>
          </span>
        );
      case 'MODERATE':
        return (
          <span
            data-testid={testId}
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200"
          >
            <ShieldAlert className="w-4 h-4 text-amber-600" />
            <span>MODERATE RISK (30.01 – 55.00)</span>
          </span>
        );
      case 'ELEVATED':
        return (
          <span
            data-testid={testId}
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-orange-50 text-orange-700 border border-orange-200"
          >
            <AlertTriangle className="w-4 h-4 text-orange-600" />
            <span>ELEVATED RISK (55.01 – 75.00)</span>
          </span>
        );
      case 'HIGH':
        return (
          <span
            data-testid={testId}
            className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200"
          >
            <AlertOctagon className="w-4 h-4 text-rose-600" />
            <span>HIGH RISK (&gt; 75.00)</span>
          </span>
        );
      default:
        return (
          <span
            data-testid={testId}
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200"
          >
            <HelpCircle className="w-3.5 h-3.5 text-gray-500" />
            <span>UNCLASSIFIED</span>
          </span>
        );
    }
  };

  const hasScore =
    riskAssessment?.composite_risk_score !== null &&
    riskAssessment?.composite_risk_score !== undefined;

  const components = riskAssessment?.components;

  return (
    <div
      data-testid="risk-score-overview"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header */}
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Deterministic Structural Risk Assessment
            </h2>
            <p className="text-xs text-gray-500">
              Rule-based 4-component risk scoring model combining concentration, sector exposure, breadth, and quote completeness.
            </p>
          </div>
        </div>

        {hasScore && (
          <div className="flex items-center space-x-2">
            {getTierBadge(riskAssessment?.risk_tier, 'risk-header-tier-badge')}
            {riskAssessment?.assessment_status && (
              <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-gray-100 text-gray-700 border border-gray-200">
                {riskAssessment.assessment_status}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="p-5 space-y-6">
        {isLoading ? (
          <div className="py-12 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Calculating structural risk factors and component weights...</span>
            </div>
          </div>
        ) : !hasScore ? (
          <div
            data-testid="risk-score-unavailable"
            className="p-6 rounded-lg bg-gray-50 border border-gray-200 text-center space-y-2"
          >
            <div className="w-10 h-10 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-gray-800">
              Composite Risk Score Unavailable
            </h3>
            <p className="text-xs text-gray-500 max-w-md mx-auto">
              The portfolio is currently{' '}
              <span className="font-semibold text-gray-700">
                {riskAssessment?.assessment_status || valuationStatus || 'UNVALUED'}
              </span>
              . Risk scoring requires at least one priced holding. Scores are intentionally reported as null rather than fabricated.
            </p>
            {riskAssessment?.methodology_scope && (
              <p className="text-[11px] text-gray-400 italic max-w-lg mx-auto pt-2">
                {riskAssessment.methodology_scope}
              </p>
            )}
          </div>
        ) : (
          <>
            {/* Primary Score & Heuristic Callout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
              {/* Score Display */}
              <div className="p-5 rounded-xl bg-gradient-to-br from-gray-50 to-blue-50/40 border border-gray-200 text-center">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Composite Risk Score
                </span>
                <div className="mt-2 flex items-baseline justify-center space-x-1">
                  <span
                    data-testid="composite-risk-score"
                    className="text-4xl font-extrabold text-gray-900 tracking-tight"
                  >
                    {formatNumber(riskAssessment?.composite_risk_score, 2)}
                  </span>
                  <span className="text-sm font-semibold text-gray-400">/ 100.00</span>
                </div>
                <div className="mt-3">
                  {getTierBadge(riskAssessment?.risk_tier)}
                </div>
              </div>

              {/* Heuristic Explanation & Transparency */}
              <div className="lg:col-span-2 space-y-2 text-xs text-gray-600">
                <div className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200">
                  <div className="flex items-start space-x-2">
                    <Sliders className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-blue-900">
                        Deterministic Heuristic Model
                      </p>
                      <p className="text-blue-800 mt-0.5 leading-relaxed">
                        This composite score is a rule-based quantitative calculation of structural portfolio exposure and data completeness, not a market return prediction, risk-free rating, or financial guarantee.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                  <p className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide">
                    Documented Score Bands &amp; Classification Tiers
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2 text-[11px]">
                    <div className="p-1.5 rounded bg-white border border-gray-100">
                      <span className="font-bold text-emerald-700">LOW</span>
                      <p className="text-gray-500">&le; 30.00</p>
                    </div>
                    <div className="p-1.5 rounded bg-white border border-gray-100">
                      <span className="font-bold text-amber-700">MODERATE</span>
                      <p className="text-gray-500">30.01 – 55.00</p>
                    </div>
                    <div className="p-1.5 rounded bg-white border border-gray-100">
                      <span className="font-bold text-orange-700">ELEVATED</span>
                      <p className="text-gray-500">55.01 – 75.00</p>
                    </div>
                    <div className="p-1.5 rounded bg-white border border-gray-100">
                      <span className="font-bold text-rose-700">HIGH</span>
                      <p className="text-gray-500">&gt; 75.00</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 4 Component Scores Breakdown */}
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-gray-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Deterministic Component Breakdown &amp; Weights
                </h3>
                <span className="text-[11px] text-gray-400 font-mono">
                  Sum of Weights = 100%
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
                {/* 1. Single Stock Concentration */}
                <div
                  data-testid="component-stock-concentration"
                  className="p-4 rounded-xl border border-gray-200 bg-white shadow-2xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-800">
                      Single-Stock
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      35% Weight
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatNumber(components?.single_stock_concentration_score, 2)}
                    </span>
                    <span className="text-xs text-gray-400">/ 100</span>
                  </div>
                  <p className="text-[11px] text-gray-500 leading-snug">
                    Evaluates concentration in the largest position (W_top).
                  </p>
                </div>

                {/* 2. Sector Concentration */}
                <div
                  data-testid="component-sector-concentration"
                  className="p-4 rounded-xl border border-gray-200 bg-white shadow-2xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-800">
                      Sector Exposure
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      25% Weight
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatNumber(components?.sector_concentration_score, 2)}
                    </span>
                    <span className="text-xs text-gray-400">/ 100</span>
                  </div>
                  <p className="text-[11px] text-gray-500 leading-snug">
                    Evaluates exposure to the dominant industry sector (S_top).
                  </p>
                </div>

                {/* 3. Diversification Breadth */}
                <div
                  data-testid="component-diversification-breadth"
                  className="p-4 rounded-xl border border-gray-200 bg-white shadow-2xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-800">
                      Breadth &amp; ENH
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      20% Weight
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatNumber(components?.diversification_breadth_score, 2)}
                    </span>
                    <span className="text-xs text-gray-400">/ 100</span>
                  </div>
                  <p className="text-[11px] text-gray-500 leading-snug">
                    Derived from Herfindahl Index (HHI) and Effective Number of Holdings.
                  </p>
                </div>

                {/* 4. Data Quality */}
                <div
                  data-testid="component-data-quality"
                  className="p-4 rounded-xl border border-gray-200 bg-white shadow-2xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-800">
                      Data Quality
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      20% Weight
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatNumber(components?.data_quality_score, 2)}
                    </span>
                    <span className="text-xs text-gray-400">/ 100</span>
                  </div>
                  <p className="text-[11px] text-gray-500 leading-snug">
                    Penalizes missing prices (up to 80 pts) and stale cache usage (+20 pts).
                  </p>
                </div>
              </div>
            </div>

            {/* Scope & Disclaimers */}
            <div className="pt-3 border-t border-gray-100 space-y-1 text-[11px] text-gray-500">
              {riskAssessment?.methodology_scope && (
                <p>
                  <strong className="text-gray-700">Methodology:</strong>{' '}
                  {riskAssessment.methodology_scope}
                </p>
              )}
              {riskAssessment?.disclaimer && (
                <p>
                  <strong className="text-gray-700">Disclaimer:</strong>{' '}
                  {riskAssessment.disclaimer}
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
