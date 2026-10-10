import React from 'react';
import { HealthIndicator } from './components/HealthIndicator';
import { ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-between">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              Z
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">
                Zerodha: AI Financial Intelligence Platform
              </h1>
              <p className="text-xs text-gray-500">
                Phase 02 — Fresh Project Foundation Verification
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
            <ShieldCheck className="w-4 h-4" />
            <span>₹0 Spend Policy Active</span>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col justify-center">
        <HealthIndicator />
      </main>

      <footer className="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-500">
        Zerodha AI Financial Intelligence Platform &bull; Academic & Engineering Platform &bull; No Real API Keys Required
      </footer>
    </div>
  );
};

export default App;
