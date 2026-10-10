import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HealthIndicator } from '../src/components/HealthIndicator';
import * as healthApi from '../src/api/health';
import { HealthResponse } from '../src/types/api';

vi.mock('../src/api/health');

describe('HealthIndicator Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially while checking connection', () => {
    // Return promise that does not resolve immediately
    vi.mocked(healthApi.fetchHealth).mockReturnValue(new Promise(() => {}));

    render(<HealthIndicator />);
    expect(screen.getByTestId('status-loading')).toBeInTheDocument();
    expect(screen.getByText(/Connecting to backend service/i)).toBeInTheDocument();
  });

  it('renders healthy state when API returns 200 OK with connected database', async () => {
    const mockData: HealthResponse = {
      status: 'healthy',
      timestamp: '2026-10-10T00:00:00Z',
      environment: 'development',
      database: {
        status: 'connected',
        engine: 'sqlite',
        journal_mode: 'wal',
        foreign_keys_enabled: true,
      },
    };

    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockData);

    render(<HealthIndicator />);

    const healthyElement = await screen.findByTestId('status-healthy');
    expect(healthyElement).toBeInTheDocument();
    expect(screen.getByText(/Backend Healthy & Connected/i)).toBeInTheDocument();
    expect(screen.getByText('HTTP 200')).toBeInTheDocument();
    expect(screen.getByText(/sqlite \(WAL\)/i)).toBeInTheDocument();
  });

  it('renders degraded state when API returns HTTP 503 database failure', async () => {
    const axiosError503 = {
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
            error: 'Simulated database lock error',
          },
        },
        headers: {},
        config: {} as any,
      },
    };

    vi.mocked(healthApi.fetchHealth).mockRejectedValue(axiosError503);

    render(<HealthIndicator />);

    const degradedElement = await screen.findByTestId('status-degraded');
    expect(degradedElement).toBeInTheDocument();
    expect(screen.getByText(/Service Degraded — Database Disconnected/i)).toBeInTheDocument();
    expect(screen.getByText('HTTP 503')).toBeInTheDocument();
    expect(screen.getByText(/Simulated database lock error/i)).toBeInTheDocument();
  });

  it('renders offline state when server is unreachable and handles retry', async () => {
    const networkError = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Network Error',
      response: undefined,
      config: {} as any,
    };

    // First call rejects with network failure
    vi.mocked(healthApi.fetchHealth).mockRejectedValueOnce(networkError);

    render(<HealthIndicator />);

    const offlineElement = await screen.findByTestId('status-offline');
    expect(offlineElement).toBeInTheDocument();
    expect(screen.getByText(/Backend Offline — Connection Failed/i)).toBeInTheDocument();

    const retryButton = screen.getByTestId('retry-button');
    expect(retryButton).toBeInTheDocument();
    expect(screen.getByText(/Retry Connection/i)).toBeInTheDocument();

    // Now mock recovery to healthy state
    const recoveredData: HealthResponse = {
      status: 'healthy',
      timestamp: '2026-10-10T00:01:00Z',
      environment: 'development',
      database: {
        status: 'connected',
        engine: 'sqlite',
        journal_mode: 'wal',
        foreign_keys_enabled: true,
      },
    };
    vi.mocked(healthApi.fetchHealth).mockResolvedValueOnce(recoveredData);

    // Trigger retry
    fireEvent.click(retryButton);

    const recoveredElement = await screen.findByTestId('status-healthy');
    expect(recoveredElement).toBeInTheDocument();
    expect(screen.getByText(/Backend Healthy & Connected/i)).toBeInTheDocument();
  });
});
