import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AdminConfigConsole } from '../src/components/admin/AdminConfigConsole';
import * as healthApi from '../src/api/health';
import * as portfoliosApi from '../src/api/portfolios';
import * as portfolioContextModule from '../src/context/PortfolioContext';
import { HealthResponse } from '../src/types/api';
import { SeedDemoResponse } from '../src/types/portfolio';

vi.mock('../src/api/health');
vi.mock('../src/api/portfolios');

describe('AdminConfigConsole Component', () => {
  const mockHealthyResponse: HealthResponse = {
    status: 'healthy',
    timestamp: '2026-10-11T09:00:00Z',
    environment: 'development',
    database: {
      status: 'connected',
      engine: 'sqlite',
      journal_mode: 'wal',
      foreign_keys_enabled: true,
      error: null,
    },
  };

  const mockSeedSuccessResponse: SeedDemoResponse = {
    created: true,
    message: 'Demo portfolio seeded successfully.',
    portfolio: {
      id: 'demo-bluechip-1',
      name: 'Demo Indian Bluechip Portfolio',
      description: 'Canonical benchmark portfolio',
      is_sample: true,
      created_at: '2026-10-11T09:00:00Z',
      updated_at: '2026-10-11T09:00:00Z',
      holdings_count: 5,
      holdings: [],
    },
  };

  const mockRefreshPortfolios = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(portfolioContextModule, 'usePortfolio').mockReturnValue({
      portfolios: [],
      activePortfolio: null,
      activePortfolioId: null,
      setActivePortfolioId: vi.fn(),
      isLoading: false,
      error: null,
      refreshPortfolios: mockRefreshPortfolios,
    });
  });

  it('renders Admin Configuration tabpanel preserving navigation contract', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    render(<AdminConfigConsole />);

    expect(
      screen.getByRole('tabpanel', { name: /admin configuration/i })
    ).toBeInTheDocument();
    expect(screen.getByTestId('admin-config-console')).toBeInTheDocument();
    expect(screen.getByText('Admin Configuration Console')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toBeInTheDocument();
    });
  });

  it('displays live server environment, database engine (SQLite/WAL), and API base URL', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    render(<AdminConfigConsole />);

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toHaveTextContent(
        'development'
      );
    });

    expect(screen.getByTestId('health-db-engine-val')).toHaveTextContent(
      'SQLITE'
    );
    expect(screen.getByTestId('health-db-status-val')).toHaveTextContent(
      'CONNECTED'
    );
    expect(screen.getByTestId('health-service-status-val')).toHaveTextContent(
      'HTTP 200 (HEALTHY)'
    );
    expect(screen.getByText(/API Target:/i)).toBeInTheDocument();
  });

  it('handles degraded or failed health check gracefully with retry capability', async () => {
    vi.mocked(healthApi.fetchHealth).mockRejectedValue(
      new Error('Connection refused on port 8000')
    );

    render(<AdminConfigConsole />);

    const errorBanner = await screen.findByTestId('admin-health-error');
    expect(errorBanner).toBeInTheDocument();
    expect(
      screen.getByText('Connection refused on port 8000')
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /A failed health request indicates server connectivity issues, not a known configuration value/i
      )
    ).toBeInTheDocument();

    // Clicking retry re-invokes fetchHealth
    vi.mocked(healthApi.fetchHealth).mockResolvedValueOnce(mockHealthyResponse);
    fireEvent.click(screen.getByTestId('retry-health-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toBeInTheDocument();
    });
  });

  it('truthfully discloses observed response metadata boundary without claiming access to .env', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    render(<AdminConfigConsole />);

    // Verifies explicit boundary disclosure
    const disclosure = screen.getByTestId('observed-metadata-disclosure');
    expect(disclosure).toBeInTheDocument();
    expect(disclosure).toHaveTextContent(
      /observed response metadata returned by existing API endpoints/i
    );
    expect(disclosure).toHaveTextContent(
      /The frontend has not read, inspected, or verified the server's active .env file/i
    );

    // Verifies provider cards
    expect(screen.getByTestId('observed-market-provider')).toHaveTextContent(
      'SIMULATED_DEMO_PROVIDER'
    );
    expect(screen.getByTestId('observed-ai-provider')).toHaveTextContent(
      'DETERMINISTIC_DEMO_REASONER'
    );
    expect(screen.getByTestId('intended-cost-policy')).toHaveTextContent(
      'Zero-Additional-Spend Policy'
    );

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toBeInTheDocument();
    });
  });

  it('discloses server secrets isolation and asserts no secret entry forms exist', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    const { container } = render(<AdminConfigConsole />);

    const secretsSection = screen.getByTestId('secrets-isolation-section');
    expect(secretsSection).toBeInTheDocument();
    expect(secretsSection).toHaveTextContent(/GROQ_API_KEY/i);
    expect(secretsSection).toHaveTextContent(/ALPHA_VANTAGE_API_KEY/i);
    expect(secretsSection).toHaveTextContent(/never transmitted, logged, or exposed/i);

    // Verify security requirement: zero password, secret, or API-key inputs
    const inputs = container.querySelectorAll('input');
    expect(inputs.length).toBe(0);

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toBeInTheDocument();
    });
  });

  it('discloses runtime configuration immutability and step-by-step reconfiguration instructions', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    render(<AdminConfigConsole />);

    const immutabilitySection = screen.getByTestId(
      'immutability-reconfiguration-section'
    );
    expect(immutabilitySection).toBeInTheDocument();
    expect(immutabilitySection).toHaveTextContent(
      /Server configuration settings are statically resolved from backend\/\.env/i
    );
    expect(immutabilitySection).toHaveTextContent(
      /The backend does not expose REST endpoints to mutate operational parameters at runtime/i
    );
    expect(immutabilitySection).toHaveTextContent(
      /uvicorn app\.main:app --port 8000/i
    );

    await waitFor(() => {
      expect(screen.getByTestId('health-environment-val')).toBeInTheDocument();
    });
  });

  it('executes seedDemoPortfolio on explicit button click and updates context on success', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);
    vi.mocked(portfoliosApi.seedDemoPortfolio).mockResolvedValue(
      mockSeedSuccessResponse
    );

    render(<AdminConfigConsole />);

    const seedBtn = screen.getByTestId('seed-demo-portfolio-btn');
    expect(seedBtn).toBeInTheDocument();

    // Verify seedDemoPortfolio is NOT called automatically on mount
    expect(portfoliosApi.seedDemoPortfolio).not.toHaveBeenCalled();

    // Trigger explicit seed action
    fireEvent.click(seedBtn);

    expect(portfoliosApi.seedDemoPortfolio).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(screen.getByTestId('seed-result-banner')).toBeInTheDocument();
    });

    expect(
      screen.getByText('Demo portfolio seeded successfully.')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Canonical portfolio and default positions created/i)
    ).toBeInTheDocument();

    // Verifies context synchronization
    expect(mockRefreshPortfolios).toHaveBeenCalledTimes(1);
  });

  it('displays existing demo portfolio feedback when created is false (idempotent)', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);
    const mockExistingResponse: SeedDemoResponse = {
      ...mockSeedSuccessResponse,
      created: false,
      message: 'Demo portfolio already exists. Returned existing portfolio.',
    };
    vi.mocked(portfoliosApi.seedDemoPortfolio).mockResolvedValue(
      mockExistingResponse
    );

    render(<AdminConfigConsole />);
    fireEvent.click(screen.getByTestId('seed-demo-portfolio-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('seed-result-banner')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Existing canonical dataset verified intact/i)
    ).toBeInTheDocument();
  });

  it('handles seed demo API failure with localized error banner', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);
    vi.mocked(portfoliosApi.seedDemoPortfolio).mockRejectedValue(
      new Error('Database lock error during seeding.')
    );

    render(<AdminConfigConsole />);
    fireEvent.click(screen.getByTestId('seed-demo-portfolio-btn'));

    const seedError = await screen.findByTestId('seed-error-banner');
    expect(seedError).toBeInTheDocument();
    expect(
      screen.getByText('Database lock error during seeding.')
    ).toBeInTheDocument();
  });

  it('protects against duplicate seed submissions while in flight', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthyResponse);

    let resolveSeed: (data: any) => void;
    const seedPromise = new Promise((resolve) => {
      resolveSeed = resolve;
    });

    vi.mocked(portfoliosApi.seedDemoPortfolio).mockReturnValueOnce(
      seedPromise as any
    );

    render(<AdminConfigConsole />);
    const seedBtn = screen.getByTestId('seed-demo-portfolio-btn');

    // First click initiates request
    fireEvent.click(seedBtn);
    expect(seedBtn).toHaveAttribute('aria-busy', 'true');
    expect(seedBtn).toBeDisabled();

    // Second click while in flight is ignored
    fireEvent.click(seedBtn);
    expect(portfoliosApi.seedDemoPortfolio).toHaveBeenCalledTimes(1);

    // Resolve request
    resolveSeed!(mockSeedSuccessResponse);

    await waitFor(() => {
      expect(screen.getByTestId('seed-result-banner')).toBeInTheDocument();
    });
  });
});
