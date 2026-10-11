import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OperationsDashboard } from '../src/components/operations/OperationsDashboard';
import * as healthApi from '../src/api/health';
import * as marketDataApi from '../src/api/marketData';
import { HealthResponse } from '../src/types/api';
import { BatchQuotesResponse } from '../src/types/marketData';

vi.mock('../src/api/health');
vi.mock('../src/api/marketData');

describe('OperationsDashboard Component', () => {
  const mockHealthHealthy: HealthResponse = {
    status: 'healthy',
    timestamp: '2026-10-11T08:00:00Z',
    environment: 'development',
    database: {
      status: 'connected',
      engine: 'sqlite',
      journal_mode: 'wal',
      foreign_keys_enabled: true,
      error: null,
    },
  };

  const mockBatchQuotes: BatchQuotesResponse = {
    total_symbols: 5,
    cache_hits_count: 3,
    cache_misses_count: 2,
    fetched_at: '2026-10-11T08:30:00Z',
    quotes: {
      RELIANCE: {
        symbol: 'RELIANCE',
        exchange: 'NSE',
        current_price: 2850.5,
        change: 15.2,
        change_percent: 0.54,
        status: 'AVAILABLE',
        is_simulated: true,
        source: 'SIMULATED_DEMO_PROVIDER',
        generated_at: '2026-10-11T08:29:00Z',
        cached_at: '2026-10-11T08:29:05Z',
        cache_hit: true,
        ttl_remaining_seconds: 45.2,
        is_stale: false,
        disclaimer: 'Simulated quote for demonstration only.',
      },
      TCS: {
        symbol: 'TCS',
        exchange: 'NSE',
        current_price: 4120.0,
        change: -12.0,
        change_percent: -0.29,
        status: 'AVAILABLE',
        is_simulated: true,
        source: 'SIMULATED_DEMO_PROVIDER',
        generated_at: '2026-10-11T08:29:00Z',
        cached_at: '2026-10-11T08:29:05Z',
        cache_hit: true,
        ttl_remaining_seconds: 52.0,
        is_stale: false,
        disclaimer: 'Simulated quote for demonstration only.',
      },
      INFY: {
        symbol: 'INFY',
        exchange: 'NSE',
        current_price: 1845.25,
        change: 8.5,
        change_percent: 0.46,
        status: 'AVAILABLE',
        is_simulated: true,
        source: 'SIMULATED_DEMO_PROVIDER',
        generated_at: '2026-10-11T08:28:00Z',
        cached_at: '2026-10-11T08:28:05Z',
        cache_hit: false,
        ttl_remaining_seconds: null,
        is_stale: true, // Emergency stale fallback
        disclaimer: 'Simulated quote for demonstration only.',
      },
      HDFCBANK: {
        symbol: 'HDFCBANK',
        exchange: 'NSE',
        current_price: null,
        change: null,
        change_percent: null,
        status: 'UNAVAILABLE',
        explanation: 'Simulated upstream rate limit reached for symbol.',
        is_simulated: true,
        source: 'SIMULATED_DEMO_PROVIDER',
        generated_at: '2026-10-11T08:28:00Z',
        cache_hit: false,
        ttl_remaining_seconds: null,
        is_stale: false,
        disclaimer: 'Simulated quote for demonstration only.',
      },
      ICICIBANK: {
        symbol: 'ICICIBANK',
        exchange: 'NSE',
        current_price: 1250.75,
        change: 5.0,
        change_percent: 0.4,
        status: 'AVAILABLE',
        is_simulated: true,
        source: 'SIMULATED_DEMO_PROVIDER',
        generated_at: '2026-10-11T08:29:00Z',
        cached_at: '2026-10-11T08:29:05Z',
        cache_hit: true,
        ttl_remaining_seconds: 30.5,
        is_stale: false,
        disclaimer: 'Simulated quote for demonstration only.',
      },
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders healthy API and database telemetry, preserving health-indicator-card testid', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    expect(screen.getByRole('tabpanel', { name: 'Operations' })).toBeInTheDocument();
    expect(screen.getByTestId('operations-dashboard')).toBeInTheDocument();

    // Verify preservation of HealthIndicator card
    const healthCard = await screen.findByTestId('health-indicator-card');
    expect(healthCard).toBeInTheDocument();
    expect(await screen.findByTestId('status-healthy')).toBeInTheDocument();
    expect(screen.getByText(/Backend Healthy & Connected/i)).toBeInTheDocument();
    expect(screen.getByText('HTTP 200')).toBeInTheDocument();
    expect(screen.getByText(/sqlite \(WAL\)/i)).toBeInTheDocument();
  });

  it('handles degraded database health state (HTTP 503)', async () => {
    const degradedError = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Request failed with status code 503',
      response: {
        status: 503,
        statusText: 'Service Unavailable',
        data: {
          status: 'unhealthy',
          environment: 'development',
          database: {
            status: 'disconnected',
            engine: 'sqlite',
            error: 'Database lock timeout during ping',
          },
        },
      },
    };

    vi.mocked(healthApi.fetchHealth).mockRejectedValue(degradedError);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    const degradedCard = await screen.findByTestId('status-degraded');
    expect(degradedCard).toBeInTheDocument();
    expect(screen.getByText(/Service Degraded — Database Disconnected/i)).toBeInTheDocument();
    expect(screen.getByText('HTTP 503')).toBeInTheDocument();
    expect(screen.getByText(/Database lock timeout during ping/i)).toBeInTheDocument();
  });

  it('handles offline backend state with retry button', async () => {
    const networkError = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Network Error',
      response: undefined,
    };

    vi.mocked(healthApi.fetchHealth).mockRejectedValue(networkError);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    const offlineCard = await screen.findByTestId('status-offline');
    expect(offlineCard).toBeInTheDocument();
    expect(screen.getByText(/Backend Offline — Connection Failed/i)).toBeInTheDocument();
    expect(screen.getByText(/uvicorn app.main:app --port 8000/i)).toBeInTheDocument();
  });

  it('renders market-data cache metrics and calculates hit ratio properly', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('cache-hits-count')).toHaveTextContent('3');
    });

    expect(screen.getByTestId('cache-misses-count')).toHaveTextContent('2');
    // Hit ratio: 3 / 5 * 100 = 60.0%
    expect(screen.getByTestId('cache-hit-ratio')).toHaveTextContent('60.0%');
    expect(screen.getByTestId('active-provider-name')).toHaveTextContent('SIMULATED_DEMO_PROVIDER');
  });

  it('safely handles zero-denominator hit ratio when total symbols is 0', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    const zeroSymbolsBatch: BatchQuotesResponse = {
      total_symbols: 0,
      cache_hits_count: 0,
      cache_misses_count: 0,
      fetched_at: '2026-10-11T08:30:00Z',
      quotes: {},
    };
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(zeroSymbolsBatch);

    render(<OperationsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('cache-hit-ratio')).toHaveTextContent('—');
    });
    expect(screen.getByTestId('empty-quotes-notice')).toBeInTheDocument();
  });

  it('renders benchmark quote table with prices, cache status, TTL, and stale flag', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('quotes-telemetry-table')).toBeInTheDocument();
    });

    // RELIANCE quote
    expect(screen.getByTestId('quote-row-RELIANCE')).toBeInTheDocument();
    expect(screen.getByTestId('quote-price-RELIANCE')).toHaveTextContent('₹2,850.50');
    expect(screen.getByTestId('quote-cache-RELIANCE')).toHaveTextContent('HIT');
    expect(screen.getByTestId('quote-ttl-RELIANCE')).toHaveTextContent('45s');

    // INFY with stale emergency fallback
    expect(screen.getByTestId('quote-row-INFY')).toBeInTheDocument();
    expect(screen.getByTestId('quote-stale-INFY')).toHaveTextContent('STALE');
    expect(screen.getByTestId('stale-fallback-status')).toHaveTextContent('Stale Fallback Active');
  });

  it('renders unavailable quote safely without fabricating zero price', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('quote-row-HDFCBANK')).toBeInTheDocument();
    });

    // Price must be '—', NEVER ₹0.00
    expect(screen.getByTestId('quote-price-HDFCBANK')).toHaveTextContent('—');
    expect(screen.getByTestId('quote-price-HDFCBANK')).not.toHaveTextContent('₹0.00');
    expect(screen.getByTestId('quote-status-HDFCBANK')).toHaveTextContent('UNAVAILABLE');
    expect(screen.getByText(/Simulated upstream rate limit reached for symbol/i)).toBeInTheDocument();
  });

  it('keeps health and market telemetry independently loadable when market call fails', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockRejectedValue(
      new Error('Market quote provider timeout.')
    );

    render(<OperationsDashboard />);

    // Health card succeeds independently
    expect(await screen.findByTestId('status-healthy')).toBeInTheDocument();

    // Market section shows localized error
    const errorBanner = await screen.findByTestId('market-error-banner');
    expect(errorBanner).toBeInTheDocument();
    expect(screen.getByText('Market quote provider timeout.')).toBeInTheDocument();
    expect(screen.getByTestId('retry-market-btn')).toBeInTheDocument();
  });

  it('honestly displays AI runtime config disclosure without calling AI reasoning API', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    expect(screen.getByTestId('ai-governance-section')).toBeInTheDocument();
    expect(screen.getByTestId('ai-runtime-config-notice')).toHaveTextContent(
      'Runtime configuration not exposed by the current API'
    );
    expect(screen.getByTestId('operational-limitations-notice')).toBeInTheDocument();
    expect(await screen.findByTestId('cache-scope-notice')).toBeInTheDocument();
  });

  it('refreshes all telemetry on global refresh button click', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);

    render(<OperationsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('global-refresh-btn')).toBeInTheDocument();
    });

    expect(healthApi.fetchHealth).toHaveBeenCalledTimes(1);
    expect(marketDataApi.fetchBatchQuotes).toHaveBeenCalledTimes(1);

    // Click global refresh
    fireEvent.click(screen.getByTestId('global-refresh-btn'));

    await waitFor(() => {
      expect(healthApi.fetchHealth).toHaveBeenCalledTimes(2);
      expect(marketDataApi.fetchBatchQuotes).toHaveBeenCalledTimes(2);
    });
  });

  it('discards out-of-order market data responses when superseded', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthHealthy);

    let resolveFirst: (data: any) => void;
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    let resolveSecond: (data: any) => void;
    const secondPromise = new Promise((resolve) => {
      resolveSecond = resolve;
    });

    // First call returns pending promise
    vi.mocked(marketDataApi.fetchBatchQuotes).mockReturnValueOnce(firstPromise as any);

    render(<OperationsDashboard />);

    // Trigger second refresh while first is in flight
    vi.mocked(marketDataApi.fetchBatchQuotes).mockReturnValueOnce(secondPromise as any);
    fireEvent.click(screen.getByTestId('global-refresh-btn'));

    // Second call resolves first with updated data
    const updatedBatch: BatchQuotesResponse = {
      ...mockBatchQuotes,
      cache_hits_count: 5,
    };
    resolveSecond!(updatedBatch);

    await waitFor(() => {
      expect(screen.getByTestId('cache-hits-count')).toHaveTextContent('5');
    });

    // Late first call resolves afterwards with stale data
    resolveFirst!(mockBatchQuotes);

    // Counter guard ensures updated data ('5') remains intact and is not overwritten by stale '3'
    expect(screen.getByTestId('cache-hits-count')).toHaveTextContent('5');
  });
});
