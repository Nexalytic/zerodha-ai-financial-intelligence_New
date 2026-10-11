import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import React from 'react';
import { PortfolioProvider, usePortfolio } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import { PortfolioResponse } from '../src/types/portfolio';

vi.mock('../src/api/portfolios');

const TestConsumer: React.FC = () => {
  const {
    portfolios,
    activePortfolioId,
    activePortfolio,
    isLoading,
    error,
    setActivePortfolioId,
    refreshPortfolios,
  } = usePortfolio();

  return (
    <div>
      <div data-testid="loading-state">{isLoading ? 'loading' : 'idle'}</div>
      {error && <div data-testid="error-state">{error}</div>}
      <div data-testid="portfolio-count">{portfolios.length}</div>
      <div data-testid="active-id">{activePortfolioId || 'none'}</div>
      <div data-testid="active-name">{activePortfolio?.name || 'none'}</div>

      <button
        data-testid="select-second"
        onClick={() => {
          if (portfolios[1]) {
            setActivePortfolioId(portfolios[1].id);
          }
        }}
      >
        Select Second
      </button>

      <button data-testid="refresh-btn" onClick={() => refreshPortfolios()}>
        Refresh
      </button>
    </div>
  );
};

describe('PortfolioContext', () => {
  const mockPortfolios: PortfolioResponse[] = [
    {
      id: 'port-1',
      name: 'Portfolio Alpha',
      is_sample: true,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 3,
    },
    {
      id: 'port-2',
      name: 'Portfolio Beta',
      is_sample: false,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 7,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially while fetching portfolios', () => {
    vi.mocked(portfoliosApi.fetchPortfolios).mockReturnValue(new Promise(() => {}));

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    expect(screen.getByTestId('loading-state')).toHaveTextContent('loading');
    expect(screen.getByTestId('portfolio-count')).toHaveTextContent('0');
  });

  it('loads portfolios and auto-selects the first portfolio when available', async () => {
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue(mockPortfolios);

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('portfolio-count')).toHaveTextContent('2');
    expect(screen.getByTestId('active-id')).toHaveTextContent('port-1');
    expect(screen.getByTestId('active-name')).toHaveTextContent('Portfolio Alpha');
  });

  it('handles empty portfolio list gracefully with active id set to none', async () => {
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([]);

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('portfolio-count')).toHaveTextContent('0');
    expect(screen.getByTestId('active-id')).toHaveTextContent('none');
    expect(screen.getByTestId('active-name')).toHaveTextContent('none');
  });

  it('captures error state when API call rejects', async () => {
    const errorResponse = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Failed to fetch',
      response: {
        status: 500,
        statusText: 'Internal Server Error',
        data: {
          success: false,
          error: {
            code: 'INTERNAL_ERROR',
            message: 'Database query failed',
          },
        },
      },
    };
    vi.mocked(portfoliosApi.fetchPortfolios).mockRejectedValue(errorResponse);

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('error-state')).toHaveTextContent('Database query failed');
    expect(screen.getByTestId('portfolio-count')).toHaveTextContent('0');
  });

  it('allows selecting a different active portfolio', async () => {
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue(mockPortfolios);

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('active-id')).toHaveTextContent('port-1');
    });

    fireEvent.click(screen.getByTestId('select-second'));

    expect(screen.getByTestId('active-id')).toHaveTextContent('port-2');
    expect(screen.getByTestId('active-name')).toHaveTextContent('Portfolio Beta');
  });

  it('refreshes the portfolio list when refreshPortfolios is called', async () => {
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValueOnce([mockPortfolios[0]]);

    render(
      <PortfolioProvider>
        <TestConsumer />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('portfolio-count')).toHaveTextContent('1');
    });

    // On second fetch, returns both portfolios
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValueOnce(mockPortfolios);

    fireEvent.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('portfolio-count')).toHaveTextContent('2');
    });
  });

  it('throws an error when usePortfolio is accessed outside PortfolioProvider', () => {
    // Suppress console.error for expected thrown error test
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      'usePortfolio must be used within a PortfolioProvider'
    );

    consoleError.mockRestore();
  });
});
