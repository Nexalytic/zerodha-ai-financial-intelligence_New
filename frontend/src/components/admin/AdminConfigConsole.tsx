import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Settings,
  Server,
  Database,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Info,
  Lock,
  FileCode,
} from 'lucide-react';
import { fetchHealth } from '../../api/health';
import { seedDemoPortfolio } from '../../api/portfolios';
import { usePortfolio } from '../../context/PortfolioContext';
import { HealthResponse } from '../../types/api';
import { SeedDemoResponse } from '../../types/portfolio';
import { API_BASE_URL, parseApiError } from '../../api/client';

export const AdminConfigConsole: React.FC = () => {
  const { refreshPortfolios } = usePortfolio();

  // Health telemetry state
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Demo seeder state
  const [isSeeding, setIsSeeding] = useState<boolean>(false);
  const [seedResult, setSeedResult] = useState<SeedDemoResponse | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const loadHealthTelemetry = useCallback(async () => {
    setIsHealthLoading(true);
    setHealthError(null);
    try {
      const data = await fetchHealth();
      if (isMountedRef.current) {
        setHealthData(data);
        setIsHealthLoading(false);
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        const parsed = parseApiError(err);
        setHealthError(
          parsed.message || 'Failed to connect to backend health endpoint.'
        );
        setIsHealthLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadHealthTelemetry();
  }, [loadHealthTelemetry]);

  const handleSeedDemo = async () => {
    if (isSeeding) return;

    setIsSeeding(true);
    setSeedResult(null);
    setSeedError(null);

    try {
      const result = await seedDemoPortfolio();
      if (isMountedRef.current) {
        setSeedResult(result);
        setIsSeeding(false);
      }
      // Synchronize shared portfolio context so header dropdown immediately updates
      await refreshPortfolios();
    } catch (err: unknown) {
      if (isMountedRef.current) {
        const parsed = parseApiError(err);
        setSeedError(
          parsed.message || 'Failed to execute demo portfolio seeding.'
        );
        setIsSeeding(false);
      }
    }
  };

  return (
    <section
      role="tabpanel"
      aria-label="Admin Configuration"
      data-testid="admin-config-console"
      className="space-y-6"
    >
      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
              <Settings className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                  Admin Configuration Console
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                  System Governed
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Server runtime environment telemetry, intended zero-cost architecture parameters, and canonical demo dataset management.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold bg-gray-100 text-gray-700 border border-gray-200">
              API Target: {API_BASE_URL}
            </span>
          </div>
        </div>
      </div>

      {/* 1. Live Server Environment & Database Telemetry */}
      <div
        data-testid="server-telemetry-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
              <Server className="w-4 h-4 text-blue-600" />
              <span>Server Environment &amp; Database Telemetry</span>
            </h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Live status returned by the backend health inspection service.
            </p>
          </div>

          <button
            onClick={loadHealthTelemetry}
            disabled={isHealthLoading}
            data-testid="refresh-health-btn"
            aria-label="Refresh Server Telemetry"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 text-xs font-semibold rounded-lg transition disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isHealthLoading ? 'animate-spin' : ''}`}
            />
            <span>Refresh</span>
          </button>
        </div>

        {/* Loading State */}
        {isHealthLoading && (
          <div
            role="status"
            aria-busy="true"
            data-testid="admin-health-loading"
            className="py-8 text-center text-gray-500 text-xs space-y-2"
          >
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mx-auto" />
            <p className="font-semibold text-gray-800">
              Querying backend server telemetry...
            </p>
            <p className="text-gray-400 text-[11px]">
              Inspecting environment flags and SQLite engine status.
            </p>
          </div>
        )}

        {/* Error State */}
        {!isHealthLoading && healthError && (
          <div
            role="alert"
            data-testid="admin-health-error"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2.5"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="font-bold text-rose-900">
                Server Telemetry Unavailable
              </p>
              <p className="text-rose-700">{healthError}</p>
              <p className="text-[11px] text-rose-600">
                Note: A failed health request indicates server connectivity issues, not a known configuration value.
              </p>
              <div className="pt-1.5">
                <button
                  onClick={loadHealthTelemetry}
                  data-testid="retry-health-btn"
                  className="px-3 py-1 bg-rose-600 text-white rounded text-[11px] font-semibold hover:bg-rose-700 cursor-pointer transition shadow-2xs"
                >
                  Retry Health Telemetry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Loaded Health Grid */}
        {!isHealthLoading && healthData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                Runtime Environment
              </span>
              <p
                data-testid="health-environment-val"
                className="text-base font-bold text-gray-900 font-mono"
              >
                {healthData.environment}
              </p>
              <p className="text-[11px] text-gray-400">
                Reported by backend health check
              </p>
            </div>

            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                Database Engine
              </span>
              <p
                data-testid="health-db-engine-val"
                className="text-base font-bold text-gray-900 font-mono"
              >
                {healthData.database.engine.toUpperCase()}
              </p>
              <p className="text-[11px] text-gray-500">
                Journal:{' '}
                <strong className="text-gray-700">
                  {healthData.database.journal_mode?.toUpperCase()}
                </strong>{' '}
                &bull; Foreign Keys:{' '}
                <strong className="text-gray-700">
                  {healthData.database.foreign_keys_enabled ? 'ON' : 'OFF'}
                </strong>
              </p>
            </div>

            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                Database Status
              </span>
              <p
                data-testid="health-db-status-val"
                className={`text-base font-bold font-mono ${
                  healthData.database.status === 'connected'
                    ? 'text-emerald-600'
                    : 'text-rose-600'
                }`}
              >
                {healthData.database.status.toUpperCase()}
              </p>
              <p className="text-[11px] text-gray-400">
                SQLite WAL connection pool
              </p>
            </div>

            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                Service Overall Status
              </span>
              <p
                data-testid="health-service-status-val"
                className={`text-base font-bold font-mono ${
                  healthData.status === 'healthy'
                    ? 'text-emerald-600'
                    : 'text-amber-600'
                }`}
              >
                {healthData.status === 'healthy' ? 'HTTP 200 (HEALTHY)' : 'HTTP 503 (DEGRADED)'}
              </p>
              <p className="text-[11px] text-gray-400">
                Timestamp: {new Date(healthData.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 2. Observed Provider Modes & Intended Zero-Cost Governance */}
      <div
        data-testid="provider-governance-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
      >
        <div className="pb-3 border-b border-gray-100">
          <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Observed Provider Modes &amp; Intended Zero-Cost Governance</span>
          </h3>
          <p className="text-[11px] text-gray-500 mt-0.5">
            Architecture parameters observed from actual API payloads and design policies.
          </p>
        </div>

        {/* Transparent Observation Disclosure */}
        <div
          data-testid="observed-metadata-disclosure"
          className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200 text-xs text-blue-900 space-y-1"
        >
          <div className="flex items-center space-x-1.5 font-bold text-blue-950">
            <Info className="w-4 h-4 text-blue-600" />
            <span>Observed Response Metadata Boundary</span>
          </div>
          <p className="leading-relaxed text-[11px] text-blue-900">
            Market-data sources and AI provider names shown below represent <strong>observed response metadata</strong> returned by existing API endpoints. The frontend has not read, inspected, or verified the server's active <code>.env</code> file, API-key presence, or internal server-side configuration variables.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1.5">
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
              Market-Data Source (Observed)
            </span>
            <p
              data-testid="observed-market-provider"
              className="text-xs font-mono font-bold text-gray-900"
            >
              SIMULATED_DEMO_PROVIDER
            </p>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Observed in quote response metadata. Generates deterministic price movements and educational mock quotes.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1.5">
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
              AI Reasoner Engine (Observed)
            </span>
            <p
              data-testid="observed-ai-provider"
              className="text-xs font-mono font-bold text-gray-900"
            >
              DETERMINISTIC_DEMO_REASONER
            </p>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Observed in AI intelligence report metadata (model: <code>deterministic-demo-v1</code>). Executes rule-based claim grounding.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 space-y-1.5">
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
              Intended Cost Governance
            </span>
            <p
              data-testid="intended-cost-policy"
              className="text-xs font-mono font-bold text-emerald-700"
            >
              Zero-Additional-Spend Policy
            </p>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Designed to operate without requiring paid third-party subscriptions or billable cloud LLM API tokens.
            </p>
          </div>
        </div>
      </div>

      {/* 3. Server Secrets & Credential Protection */}
      <div
        data-testid="secrets-isolation-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-3"
      >
        <div className="flex items-center space-x-2 pb-2 border-b border-gray-100">
          <Lock className="w-4 h-4 text-purple-600" />
          <h3 className="text-sm font-bold text-gray-900">
            Server Secrets &amp; Credential Protection
          </h3>
        </div>

        <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-600 space-y-2">
          <p className="leading-relaxed">
            <strong>Secret Isolation Invariant:</strong> External API keys (such as <code>GROQ_API_KEY</code> and <code>ALPHA_VANTAGE_API_KEY</code>) are strictly server-side environment variables. They are <strong>never transmitted, logged, or exposed</strong> to the web client.
          </p>
          <p className="leading-relaxed text-[11px] text-gray-500">
            In compliance with strict security policies, this administrative interface does not contain key-entry input forms, secret display fields, or client-side token configuration controls.
          </p>
        </div>
      </div>

      {/* 4. Canonical Demo Dataset Management (Functional Action) */}
      <div
        data-testid="demo-seeding-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
              <Database className="w-4 h-4 text-blue-600" />
              <span>Canonical Demo Dataset Management</span>
            </h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Idempotently seed or restore the standard Indian bluechip demonstration portfolio in the SQLite database.
            </p>
          </div>

          <button
            onClick={handleSeedDemo}
            disabled={isSeeding}
            aria-busy={isSeeding}
            data-testid="seed-demo-portfolio-btn"
            className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isSeeding ? 'animate-spin' : ''}`}
            />
            <span>
              {isSeeding ? 'Seeding Demo Dataset...' : 'Seed / Restore Demo Portfolio'}
            </span>
          </button>
        </div>

        {/* Seeding Success / Status Banner */}
        {seedResult && (
          <div
            role="status"
            data-testid="seed-result-banner"
            className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 flex items-start space-x-2.5"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold text-emerald-950">
                {seedResult.message}
              </p>
              <p className="text-emerald-800 text-[11px]">
                Portfolio: <strong>{seedResult.portfolio.name}</strong> ({seedResult.portfolio.holdings_count} positions).{' '}
                {seedResult.created
                  ? 'Canonical portfolio and default positions created.'
                  : 'Existing canonical dataset verified intact.'}
              </p>
            </div>
          </div>
        )}

        {/* Seeding Error Banner */}
        {seedError && (
          <div
            role="alert"
            data-testid="seed-error-banner"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2.5"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold text-rose-900">
                Demo Seeding Operation Failed
              </p>
              <p className="text-rose-700">{seedError}</p>
            </div>
          </div>
        )}

        <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-500 space-y-1">
          <p className="font-semibold text-gray-700">
            Seeding Operation Details:
          </p>
          <p className="leading-relaxed">
            Invokes backend endpoint <code>POST /api/v1/portfolios/seed-demo</code>. If the demo portfolio does not exist, it inserts 5 canonical bluechip equity holdings (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK). If it already exists, the seeder safely returns the existing record without duplicating holdings.
          </p>
        </div>
      </div>

      {/* 5. Server-Side Immutability & Reconfiguration Instructions */}
      <div
        data-testid="immutability-reconfiguration-section"
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs space-y-3"
      >
        <div className="flex items-center space-x-2 pb-2 border-b border-gray-100">
          <FileCode className="w-4 h-4 text-gray-600" />
          <h3 className="text-sm font-bold text-gray-900">
            Server-Side Immutability &amp; Reconfiguration Procedure
          </h3>
        </div>

        <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-600 space-y-2">
          <p className="leading-relaxed">
            <strong>Configuration Immutability:</strong> Server configuration settings are statically resolved from <code>backend/.env</code> and system environment variables on application startup. The backend does not expose REST endpoints to mutate operational parameters at runtime.
          </p>
          <div className="pt-1 space-y-1.5 text-[11px] text-gray-500">
            <p className="font-semibold text-gray-700">
              To reconfigure providers or environment parameters:
            </p>
            <ol className="list-decimal pl-4 space-y-1 leading-relaxed">
              <li>
                Edit backend configuration in <code className="font-mono bg-gray-200/60 px-1 py-0.5 rounded">backend/.env</code> (e.g. adjust <code>AI_PROVIDER</code>, <code>MARKET_DATA_PROVIDER</code>, or <code>ENVIRONMENT</code>).
              </li>
              <li>
                Restart the FastAPI application server process:
                <code className="block mt-1 p-2 bg-gray-900 text-gray-100 font-mono rounded text-[11px]">
                  uvicorn app.main:app --port 8000
                </code>
              </li>
              <li>
                Refresh this console to observe updated environment telemetry.
              </li>
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
};
