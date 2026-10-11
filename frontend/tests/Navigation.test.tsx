import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../src/App';
import * as portfoliosApi from '../src/api/portfolios';
import * as healthApi from '../src/api/health';
import { PortfolioResponse } from '../src/types/portfolio';
import { HealthResponse } from '../src/types/api';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/health');
vi.mock('../src/api/analytics', () => ({
  fetchPortfolioAnalytics: vi.fn().mockResolvedValue({
    portfolio_id: 'demo-portfolio-1',
    portfolio_name: 'Demo Indian Bluechip Portfolio',
    is_sample: true,
    calculated_at: '2026-10-10T00:00:00Z',
    status: 'COMPLETE',
    valuation: {
      total_cost_basis: 100000,
      total_market_value: 125000,
      priced_cost_basis: 100000,
      unrealized_pnl: 25000,
      unrealized_pnl_percent: 25.0,
    },
    completeness: {
      is_complete: true,
      completeness_ratio: 1.0,
      total_holdings_count: 5,
      priced_holdings_count: 5,
      unpriced_holdings_count: 0,
      has_stale_prices: false,
      has_simulated_prices: false,
      unpriced_positions: [],
    },
    concentration: {},
    sector_allocations: [],
    holdings: [],
    disclaimer: 'Educational purposes only',
  }),
  fetchPortfolioInsights: vi.fn().mockResolvedValue({
    portfolio_id: 'demo-portfolio-1',
    insights: [],
    total_insights: 0,
    generated_at: '2026-10-10T00:00:00Z',
    is_sample_portfolio: true,
    disclaimer: 'Educational purposes only',
  }),
}));
vi.mock('../src/api/aiReasoning', () => ({
  generateAIPortfolioInsights: vi.fn().mockResolvedValue({}),
}));
vi.mock('../src/api/marketData', () => ({
  fetchQuote: vi.fn().mockResolvedValue({
    symbol: 'RELIANCE',
    exchange: 'NSE',
    price: 2500,
    change: 15.5,
    change_percent: 0.62,
    day_high: 2520,
    day_low: 2490,
    volume: 1000000,
    source: 'SIMULATED_DEMO_PROVIDER',
    is_simulated: true,
    is_stale: false,
    timestamp: '2026-10-10T00:00:00Z',
  }),
  fetchBatchQuotes: vi.fn().mockResolvedValue({
    quotes: {
      RELIANCE: {
        symbol: 'RELIANCE',
        exchange: 'NSE',
        price: 2500,
        change: 15.5,
        change_percent: 0.62,
        day_high: 2520,
        day_low: 2490,
        volume: 1000000,
        source: 'SIMULATED_DEMO_PROVIDER',
        is_simulated: true,
        is_stale: false,
        timestamp: '2026-10-10T00:00:00Z',
      },
    },
    total_symbols: 1,
    cache_hits_count: 1,
    cache_misses_count: 0,
    generated_at: '2026-10-10T00:00:00Z',
  }),
}));
vi.mock('../src/api/news', () => ({
  fetchNews: vi.fn().mockResolvedValue({
    articles: [],
    total_articles: 0,
    generated_at: '2026-10-10T00:00:00Z',
    source: 'SIMULATED_NEWS_ENGINE',
    disclaimer: 'Educational simulated news only',
  }),
}));

describe('Navigation Shell and Dashboard Views', () => {
  const mockPortfolios: PortfolioResponse[] = [
    {
      id: 'demo-portfolio-1',
      name: 'Demo Indian Bluechip Portfolio',
      description: 'Canonical bluechip portfolio',
      is_sample: true,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 5,
    },
  ];

  const mockHealthData: HealthResponse = {
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

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue(mockPortfolios);
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthData);
  });

  it('renders all seven dashboard view tabs with correct accessible roles and initial state', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('tablist', { name: /dashboard views/i })).toBeInTheDocument();
    });

    const tabList = screen.getByRole('tablist', { name: /dashboard views/i });
    expect(tabList).toBeInTheDocument();

    const expectedViews = [
      { id: 'portfolio', label: 'Portfolio Intelligence Hub' },
      { id: 'risk', label: 'Risk & Exposure' },
      { id: 'market', label: 'Market Movement' },
      { id: 'recommendation', label: 'Recommendation Review' },
      { id: 'operations', label: 'Operations' },
      { id: 'compliance', label: 'Compliance & Audit' },
      { id: 'admin', label: 'Admin Configuration' },
    ];

    for (const view of expectedViews) {
      const tab = screen.getByRole('tab', { name: view.label });
      expect(tab).toBeInTheDocument();
      expect(tab).toHaveAttribute('id', `tab-${view.id}`);
      expect(tab).toHaveAttribute('aria-controls', `tabpanel-${view.id}`);
    }

    // By default, the Portfolio tab is active
    const portfolioTab = screen.getByRole('tab', { name: 'Portfolio Intelligence Hub' });
    expect(portfolioTab).toHaveAttribute('aria-selected', 'true');

    // Default view panel is rendered
    expect(screen.getByRole('tabpanel', { name: /portfolio intelligence hub/i })).toBeInTheDocument();
  });

  it('switches between all seven views when clicking tabs and updates aria-selected', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('tablist', { name: /dashboard views/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toHaveValue('demo-portfolio-1');
    });

    // 1. Switch to Risk & Exposure
    const riskTab = screen.getByRole('tab', { name: 'Risk & Exposure' });
    fireEvent.click(riskTab);
    expect(riskTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /risk & exposure/i })).toBeInTheDocument();

    // 2. Switch to Market Movement
    const marketTab = screen.getByRole('tab', { name: 'Market Movement' });
    fireEvent.click(marketTab);
    expect(marketTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /market movement/i })).toBeInTheDocument();

    // 3. Switch to Recommendation Review
    const recoTab = screen.getByRole('tab', { name: 'Recommendation Review' });
    fireEvent.click(recoTab);
    expect(recoTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /recommendation review/i })).toBeInTheDocument();

    // 4. Switch to Operations
    const opsTab = screen.getByRole('tab', { name: 'Operations' });
    fireEvent.click(opsTab);
    expect(opsTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /operations/i })).toBeInTheDocument();
    // Operations panel includes HealthIndicator
    expect(await screen.findByTestId('health-indicator-card')).toBeInTheDocument();

    // 5. Switch to Compliance & Audit
    const compTab = screen.getByRole('tab', { name: 'Compliance & Audit' });
    fireEvent.click(compTab);
    expect(compTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /compliance & audit/i })).toBeInTheDocument();

    // 6. Switch to Admin Configuration
    const adminTab = screen.getByRole('tab', { name: 'Admin Configuration' });
    fireEvent.click(adminTab);
    expect(adminTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: /admin configuration/i })).toBeInTheDocument();

    // 7. Switch back to Portfolio Hub
    const portfolioTab = screen.getByRole('tab', { name: 'Portfolio Intelligence Hub' });
    fireEvent.click(portfolioTab);
    expect(portfolioTab).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => {
      expect(screen.getByRole('tabpanel', { name: /portfolio intelligence hub/i })).toBeInTheDocument();
    });
  });

  it('displays the active portfolio context in header selector and view panel', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toBeInTheDocument();
    });

    const selector = screen.getByRole('combobox', { name: /select active portfolio/i });
    expect(selector).toHaveValue('demo-portfolio-1');

    // Both the header selector and the active panel display the portfolio name
    const portfolioMatches = screen.getAllByText(/Demo Indian Bluechip Portfolio/i);
    expect(portfolioMatches.length).toBeGreaterThanOrEqual(2);
  });
});
