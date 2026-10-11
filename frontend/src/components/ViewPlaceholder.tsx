import React from 'react';
import { DashboardView, DASHBOARD_VIEWS } from '../types/navigation';
import { usePortfolio } from '../context/PortfolioContext';
import { HealthIndicator } from './HealthIndicator';
import { Briefcase, AlertCircle, RefreshCw } from 'lucide-react';

export interface ViewPlaceholderProps {
  view: DashboardView;
}

export const ViewPlaceholder: React.FC<ViewPlaceholderProps> = ({ view }) => {
  const { activePortfolio, portfolios, isLoading, error, refreshPortfolios } = usePortfolio();
  const definition = DASHBOARD_VIEWS.find((v) => v.id === view);

  if (view === 'operations') {
    return (
      <section
        role="tabpanel"
        id="tabpanel-operations"
        aria-labelledby="tab-operations"
        className="space-y-6"
      >
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-gray-100 gap-2">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Operations Dashboard</h2>
              <p className="text-sm text-gray-500 mt-1">
                System observability, database status, cache performance, and zero-cost policy verification.
              </p>
            </div>
            <div className="flex items-center space-x-2 text-xs font-mono text-gray-500">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Telemetry Active</span>
            </div>
          </div>

          <div className="mt-6">
            <HealthIndicator />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      role="tabpanel"
      id={`tabpanel-${view}`}
      aria-labelledby={`tab-${view}`}
      className="bg-white rounded-xl border border-gray-200 shadow-xs p-6 sm:p-8"
    >
      <div className="max-w-3xl">
        <div className="inline-flex items-center space-x-2 text-xs font-semibold text-blue-700 bg-blue-50 px-3 py-1 rounded-full mb-3 border border-blue-200">
          <span>Phase 07: Frontend Foundation</span>
          <span>&bull;</span>
          <span>View Ready</span>
        </div>

        <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
          {definition?.label}
        </h2>
        <p className="text-sm text-gray-600 mt-2 leading-relaxed">
          {definition?.description}
        </p>

        {/* Portfolio Context Summary Banner */}
        <div className="mt-6 p-4 rounded-lg bg-gray-50 border border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white rounded-lg border border-gray-200 text-gray-600">
                <Briefcase className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Active Portfolio Context
                </p>
                {isLoading ? (
                  <p className="text-sm font-medium text-gray-600">Loading portfolios...</p>
                ) : activePortfolio ? (
                  <p className="text-sm font-semibold text-gray-900">
                    {activePortfolio.name}{' '}
                    <span className="text-xs font-normal text-gray-500">
                      ({activePortfolio.holdings_count} holdings)
                    </span>
                  </p>
                ) : (
                  <p className="text-sm text-amber-700 font-medium">
                    No portfolio selected ({portfolios.length} available)
                  </p>
                )}
              </div>
            </div>

            <button
              onClick={() => refreshPortfolios()}
              aria-label="Refresh portfolio data"
              disabled={isLoading}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {error && (
            <div className="mt-3 flex items-center space-x-2 text-xs text-rose-700 bg-rose-50 p-2.5 rounded-lg border border-rose-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="mt-6 pt-6 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
          <span>Backend Contracts Connected & Verified</span>
          <span>Zero-Cost Mock Policy Active (₹0 spend)</span>
        </div>
      </div>
    </section>
  );
};
