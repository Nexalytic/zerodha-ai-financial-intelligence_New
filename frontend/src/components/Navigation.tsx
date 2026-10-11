import React from 'react';
import {
  PieChart,
  ShieldAlert,
  TrendingUp,
  Sparkles,
  Activity,
  FileCheck,
  Settings,
} from 'lucide-react';
import { DashboardView, DASHBOARD_VIEWS } from '../types/navigation';

export interface NavigationProps {
  activeView: DashboardView;
  onViewChange: (view: DashboardView) => void;
}

const VIEW_ICONS: Record<DashboardView, React.ComponentType<{ className?: string }>> = {
  portfolio: PieChart,
  risk: ShieldAlert,
  market: TrendingUp,
  recommendation: Sparkles,
  operations: Activity,
  compliance: FileCheck,
  admin: Settings,
};

export const Navigation: React.FC<NavigationProps> = ({ activeView, onViewChange }) => {
  return (
    <nav
      aria-label="Main Navigation"
      className="bg-white border-b border-gray-200 sticky top-0 z-20 shadow-xs"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div
          role="tablist"
          aria-label="Dashboard Views"
          className="flex space-x-1 sm:space-x-2 overflow-x-auto py-2.5 scrollbar-none"
        >
          {DASHBOARD_VIEWS.map((view) => {
            const Icon = VIEW_ICONS[view.id];
            const isActive = activeView === view.id;

            return (
              <button
                key={view.id}
                role="tab"
                id={`tab-${view.id}`}
                aria-selected={isActive}
                aria-controls={`tabpanel-${view.id}`}
                aria-label={view.label}
                onClick={() => onViewChange(view.id)}
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all whitespace-nowrap focus:outline-hidden focus:ring-2 focus:ring-blue-500 ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 shadow-xs border border-blue-200'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                <span>{view.shortLabel}</span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
};
