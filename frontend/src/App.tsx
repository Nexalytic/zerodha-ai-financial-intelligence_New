import React, { useState } from 'react';
import { ShieldCheck, ChevronDown, Briefcase } from 'lucide-react';
import { DashboardView } from './types/navigation';
import { Navigation } from './components/Navigation';
import { ViewPlaceholder } from './components/ViewPlaceholder';
import { PortfolioHub } from './components/portfolio/PortfolioHub';
import { RiskExposurePanel } from './components/risk/RiskExposurePanel';
import { MarketMovementExplainer } from './components/market/MarketMovementExplainer';
import { RecommendationReviewConsole } from './components/recommendation/RecommendationReviewConsole';
import { OperationsDashboard } from './components/operations/OperationsDashboard';
import { ComplianceAuditPanel } from './components/compliance/ComplianceAuditPanel';
import { AdminConfigConsole } from './components/admin/AdminConfigConsole';
import { PortfolioProvider, usePortfolio } from './context/PortfolioContext';

const HeaderPortfolioSelector: React.FC = () => {
  const { portfolios, activePortfolioId, setActivePortfolioId, isLoading } = usePortfolio();

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-xs text-gray-500 bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-200">
        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
        <span>Loading portfolios...</span>
      </div>
    );
  }

  if (portfolios.length === 0) {
    return (
      <div className="flex items-center space-x-2 text-xs text-amber-700 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200">
        <Briefcase className="w-3.5 h-3.5" />
        <span>No portfolios found</span>
      </div>
    );
  }

  return (
    <div className="relative inline-flex items-center">
      <label htmlFor="header-portfolio-select" className="sr-only">
        Select active portfolio
      </label>
      <select
        id="header-portfolio-select"
        aria-label="Select active portfolio"
        value={activePortfolioId || ''}
        onChange={(e) => setActivePortfolioId(e.target.value || null)}
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
  );
};

export const DashboardContent: React.FC = () => {
  const [activeView, setActiveView] = useState<DashboardView>('portfolio');

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-between">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-xs">
              Z
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-gray-900 tracking-tight leading-tight">
                Zerodha: AI Financial Intelligence Platform
              </h1>
              <p className="text-xs text-gray-500 hidden sm:block">
                Governed Financial Intelligence &bull; Evidence-Grounded Analytics
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <HeaderPortfolioSelector />
            <div className="hidden sm:flex items-center space-x-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1.5 rounded-lg border border-emerald-200">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>₹0 Spend Policy Active</span>
            </div>
          </div>
        </div>

        <Navigation activeView={activeView} onViewChange={setActiveView} />
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeView === 'portfolio' ? (
          <PortfolioHub />
        ) : activeView === 'risk' ? (
          <RiskExposurePanel />
        ) : activeView === 'market' ? (
          <MarketMovementExplainer />
        ) : activeView === 'recommendation' ? (
          <RecommendationReviewConsole />
        ) : activeView === 'operations' ? (
          <OperationsDashboard />
        ) : activeView === 'compliance' ? (
          <ComplianceAuditPanel />
        ) : activeView === 'admin' ? (
          <AdminConfigConsole />
        ) : (
          <ViewPlaceholder view={activeView} />
        )}
      </main>

      <footer className="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-500">
        Zerodha AI Financial Intelligence Platform &bull; Academic & Engineering Platform &bull; No Real API Keys Required
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <PortfolioProvider>
      <DashboardContent />
    </PortfolioProvider>
  );
};

export default App;
