import React from 'react';
import { ConcentrationMetrics } from '../../types/analytics';
import { formatNumber, formatPercent } from '../../utils/formatters';
import { PieChart, Info, ShieldCheck, AlertTriangle, AlertCircle } from 'lucide-react';

export interface ConcentrationCardProps {
  concentration: ConcentrationMetrics | undefined;
  isLoading: boolean;
}

export const ConcentrationCard: React.FC<ConcentrationCardProps> = ({
  concentration,
  isLoading,
}) => {
  const getConcentrationTierBadge = (tier: string | null | undefined) => {
    switch (tier) {
      case 'LOW':
        return (
          <span
            data-testid="concentration-tier-badge"
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>LOW CONCENTRATION</span>
          </span>
        );
      case 'MODERATE':
        return (
          <span
            data-testid="concentration-tier-badge"
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>MODERATE CONCENTRATION</span>
          </span>
        );
      case 'HIGH':
        return (
          <span
            data-testid="concentration-tier-badge"
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200"
          >
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            <span>HIGH CONCENTRATION</span>
          </span>
        );
      default:
        return (
          <span
            data-testid="concentration-tier-badge"
            className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200"
          >
            <span>UNCLASSIFIED</span>
          </span>
        );
    }
  };

  return (
    <div
      data-testid="concentration-metrics-card"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <PieChart className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Concentration &amp; Diversification Profile
            </h2>
            <p className="text-xs text-gray-500">
              Quantitative measures of single-asset dependence and portfolio breadth (HHI &amp; ENH).
            </p>
          </div>
        </div>

        <div>{getConcentrationTierBadge(concentration?.concentration_tier)}</div>
      </div>

      <div className="p-5 space-y-6">
        {isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Computing concentration metrics and effective holdings...</span>
            </div>
          </div>
        ) : (
          <>
            {/* Primary Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* 1. Top Holding Concentration */}
              <div
                data-testid="top-holding-metric"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Top Holding Weight
                </span>
                <div className="flex items-baseline space-x-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {formatPercent(concentration?.top_holding_weight_percent)}
                  </span>
                  {concentration?.top_holding_symbol && (
                    <span className="px-1.5 py-0.5 rounded text-xs font-mono font-bold bg-white text-gray-800 border border-gray-200">
                      {concentration.top_holding_symbol}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-gray-500">
                  {concentration?.top_holding_symbol
                    ? `Dominant asset in total priced market value`
                    : 'No priced holding identified'}
                </p>
              </div>

              {/* 2. Top 3 Holdings Weight */}
              <div
                data-testid="top-3-concentration-metric"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Top 3 Combined Weight
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatPercent(concentration?.top_3_concentration_percent)}
                </div>
                <p className="text-[11px] text-gray-500">
                  Cumulative allocation of three largest positions
                </p>
              </div>

              {/* 3. Herfindahl-Hirschman Index (HHI) */}
              <div
                data-testid="hhi-metric"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Herfindahl Index (HHI)
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatNumber(concentration?.herfindahl_index, 4)}
                </div>
                <p className="text-[11px] text-gray-500">
                  Normalized 0.0000 (diffuse) to 1.0000 (single asset)
                </p>
              </div>

              {/* 4. Effective Number of Holdings (ENH) */}
              <div
                data-testid="enh-metric"
                className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 space-y-1"
              >
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Effective Holdings (ENH)
                </span>
                <div className="text-2xl font-bold text-gray-900">
                  {formatNumber(concentration?.effective_holdings_count, 1)}
                </div>
                <p className="text-[11px] text-gray-500">
                  Equivalent equal-weighted positions (ENH = 1 / HHI)
                </p>
              </div>
            </div>

            {/* Classification Thresholds & Non-Advisory Callout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
              {/* Thresholds Table */}
              <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-2">
                <span className="font-semibold text-gray-800 text-[11px] uppercase tracking-wide block">
                  Concentration Classification Guidelines
                </span>
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex items-center justify-between p-1.5 bg-white rounded border border-gray-100">
                    <span className="font-semibold text-emerald-700">LOW</span>
                    <span className="text-gray-600 font-mono">HHI &lt; 0.1500 (ENH &gt; 6.7)</span>
                    <span className="text-gray-500">Well-diversified</span>
                  </div>
                  <div className="flex items-center justify-between p-1.5 bg-white rounded border border-gray-100">
                    <span className="font-semibold text-amber-700">MODERATE</span>
                    <span className="text-gray-600 font-mono">0.1500 &le; HHI &le; 0.2500</span>
                    <span className="text-gray-500">Moderate clustering</span>
                  </div>
                  <div className="flex items-center justify-between p-1.5 bg-white rounded border border-gray-100">
                    <span className="font-semibold text-rose-700">HIGH</span>
                    <span className="text-gray-600 font-mono">HHI &gt; 0.2500 (ENH &lt; 4.0)</span>
                    <span className="text-gray-500">High single-cluster risk</span>
                  </div>
                </div>
              </div>

              {/* Non-Advisory / Educational Callout */}
              <div className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200 flex items-start space-x-2.5">
                <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold text-blue-900 text-xs">
                    Non-Advisory Concentration Disclosure
                  </p>
                  <p className="text-blue-800 leading-relaxed text-[11px]">
                    Concentration metrics illustrate mathematical dependency on individual positions or clusters. Higher concentration indicates structural vulnerability to single-firm events rather than an automatic suggestion to liquidate or rebalance.
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
