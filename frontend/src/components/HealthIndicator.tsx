import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  WifiOff,
  RefreshCw,
  Database,
  Server,
} from 'lucide-react';
import { fetchHealth } from '../api/health';
import { parseApiError, API_BASE_URL } from '../api/client';
import { HealthResponse, HealthStatusType } from '../types/api';

export const HealthIndicator: React.FC = () => {
  const [status, setStatus] = useState<HealthStatusType>('loading');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  const checkHealth = useCallback(async () => {
    setIsRetrying(true);
    setStatus('loading');
    setErrorMessage(null);

    try {
      const data = await fetchHealth();
      setHealthData(data);
      if (data.status === 'healthy' && data.database?.status === 'connected') {
        setStatus('healthy');
      } else {
        setStatus('degraded');
        setErrorMessage(data.database?.error || 'Database connectivity degraded.');
      }
    } catch (err: unknown) {
      const parsedError = parseApiError(err);
      setHealthData(parsedError.data as HealthResponse | null);
      if (parsedError.isDatabaseError) {
        setStatus('degraded');
        setErrorMessage(parsedError.message);
      } else {
        setStatus('offline');
        setErrorMessage(parsedError.message);
      }
    } finally {
      setLastChecked(new Date());
      setIsRetrying(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return (
    <div
      data-testid="health-indicator-card"
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 max-w-2xl mx-auto"
    >
      <div className="flex items-center justify-between pb-4 border-b border-gray-100">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">System Health & API Status</h2>
            <p className="text-xs text-gray-500 font-mono">Target: {API_BASE_URL}</p>
          </div>
        </div>

        <button
          onClick={checkHealth}
          disabled={isRetrying}
          data-testid="retry-button"
          aria-label="Refresh status"
          className="inline-flex items-center space-x-2 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded-lg transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
          <span>{status === 'offline' || status === 'degraded' ? 'Retry Connection' : 'Refresh'}</span>
        </button>
      </div>

      <div className="mt-5 space-y-4">
        {/* Loading State */}
        {status === 'loading' && (
          <div data-testid="status-loading" className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg text-gray-600">
            <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
            <div>
              <p className="text-sm font-medium">Connecting to backend service...</p>
              <p className="text-xs text-gray-500">Verifying API response and database health</p>
            </div>
          </div>
        )}

        {/* Healthy State */}
        {status === 'healthy' && (
          <div data-testid="status-healthy" className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div className="flex items-start space-x-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-emerald-900">Backend Healthy & Connected</h3>
                  <span className="text-xs px-2 py-0.5 font-medium bg-emerald-100 text-emerald-800 rounded-full">
                    HTTP 200
                  </span>
                </div>
                <p className="text-xs text-emerald-700 mt-1">
                  API server is responsive and SQLite database connection is fully operational.
                </p>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center space-x-1.5 text-emerald-800">
                    <Server className="w-3.5 h-3.5" />
                    <span>Env: <strong>{healthData?.environment}</strong></span>
                  </div>
                  <div className="flex items-center space-x-1.5 text-emerald-800">
                    <Database className="w-3.5 h-3.5" />
                    <span>
                      DB: <strong>{healthData?.database.engine} ({healthData?.database.journal_mode?.toUpperCase()})</strong>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Degraded State */}
        {status === 'degraded' && (
          <div data-testid="status-degraded" className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-amber-900">Service Degraded — Database Disconnected</h3>
                  <span className="text-xs px-2 py-0.5 font-medium bg-amber-100 text-amber-800 rounded-full">
                    HTTP 503
                  </span>
                </div>
                <p className="text-xs text-amber-800 mt-1">
                  {errorMessage || 'The API server responded, but the database connection check failed.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Offline State */}
        {status === 'offline' && (
          <div data-testid="status-offline" className="p-4 bg-rose-50 border border-rose-200 rounded-lg">
            <div className="flex items-start space-x-3">
              <WifiOff className="w-5 h-5 text-rose-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-rose-900">Backend Offline — Connection Failed</h3>
                  <span className="text-xs px-2 py-0.5 font-medium bg-rose-100 text-rose-800 rounded-full">
                    No Response
                  </span>
                </div>
                <p className="text-xs text-rose-700 mt-1">
                  {errorMessage || 'Cannot establish connection to http://127.0.0.1:8000/api/v1.'}
                </p>
                <div className="mt-3 p-2.5 bg-rose-100/60 rounded text-xs text-rose-900">
                  <span className="font-medium">Troubleshooting:</span> Verify that the FastAPI backend is running via{' '}
                  <code className="bg-rose-200/60 px-1 py-0.5 rounded font-mono">
                    uvicorn app.main:app --port 8000
                  </code>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Timestamp Footer */}
        {lastChecked && (
          <div className="pt-2 flex justify-between items-center text-[11px] text-gray-400">
            <span>Last checked: {lastChecked.toLocaleTimeString()}</span>
            <span>Cost: ₹0 (Local Mock Mode)</span>
          </div>
        )}
      </div>
    </div>
  );
};
