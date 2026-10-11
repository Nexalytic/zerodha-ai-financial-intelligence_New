import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../src/App';
import * as portfoliosApi from '../src/api/portfolios';
import * as healthApi from '../src/api/health';
import * as analyticsApi from '../src/api/analytics';
import * as aiReasoningApi from '../src/api/aiReasoning';
import * as marketDataApi from '../src/api/marketData';
import * as newsApi from '../src/api/news';
import { PortfolioResponse, SeedDemoResponse } from '../src/types/portfolio';
import { HealthResponse } from '../src/types/api';
import { PortfolioAnalyticsResponse } from '../src/types/analytics';
import { PortfolioInsightsResponse, AIInsightReport } from '../src/types/aiReasoning';
import { BatchQuotesResponse, NewsResponse } from '../src/types/marketData';

// Mock all external API modules to prevent live network calls and keep tests deterministic
vi.mock('../src/api/portfolios');
vi.mock('../src/api/health');
vi.mock('../src/api/analytics');
vi.mock('../src/api/aiReasoning');
vi.mock('../src/api/marketData');
vi.mock('../src/api/news');

describe('End-to-End Application Integration Tests (JSDOM)', () => {
  // Mock Portfolios
  const mockPortfolios: PortfolioResponse[] = [
    {
      id: 'port-bluechip',
      name: 'Demo Indian Bluechip Portfolio',
      description: 'Canonical bluechip benchmark',
      is_sample: true,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 5,
    },
    {
      id: 'port-tech-growth',
      name: 'Tech Growth Sandbox',
      description: 'IT and technology exposure portfolio',
      is_sample: false,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 2,
    },
  ];

  // Mock Health Telemetry
  const mockHealthData: HealthResponse = {
    status: 'healthy',
    timestamp: '2026-10-11T10:00:00Z',
    environment: 'development',
    database: {
      status: 'connected',
      engine: 'sqlite',
      journal_mode: 'wal',
      foreign_keys_enabled: true,
      error: null,
    },
  };

  // Mock Analytics for port-bluechip
  const mockBluechipAnalytics: PortfolioAnalyticsResponse = {
    portfolio_id: 'port-bluechip',
    portfolio_name: 'Demo Indian Bluechip Portfolio',
    is_sample: true,
    calculated_at: '2026-10-11T10:00:00Z',
    status: 'COMPLETE',
    valuation: {
      total_cost_basis: 125000,
      total_market_value: 137500,
      priced_cost_basis: 125000,
      unrealized_pnl: 12500,
      unrealized_pnl_percent: 10.0,
    },
    completeness: {
      is_complete: true,
      completeness_ratio: 1.0,
      total_holdings_count: 5,
      priced_holdings_count: 5,
      unpriced_holdings_count: 0,
      has_stale_prices: false,
      has_simulated_prices: true,
      unpriced_positions: [],
    },
    concentration: {
      top_holding_symbol: 'RELIANCE',
      top_holding_weight_percent: 28.5,
      top_3_concentration_percent: 65.2,
      herfindahl_index: 0.245,
      effective_holdings_count: 4.1,
    },
    risk_assessment: {
      composite_risk_score: 42.5,
      risk_tier: 'MODERATE',
      assessment_status: 'COMPLETE',
      components: {
        single_stock_concentration_score: 38.0,
        sector_concentration_score: 45.0,
        diversification_breadth_score: 40.0,
        data_quality_score: 0.0,
      },
      weights: {
        single_stock: 0.35,
        sector: 0.25,
        breadth: 0.25,
        quality: 0.15,
      },
      methodology_scope: 'Deterministic 4-factor scoring model',
      disclaimer: 'Calculated using simulated prices for academic study only.',
    },
    sector_allocations: [
      {
        sector: 'Energy',
        cost_basis: 40000,
        market_value: 45000,
        allocation_percent: 32.7,
        holdings_count: 1,
        priced_count: 1,
        unpriced_count: 0,
      },
      {
        sector: 'Technology',
        cost_basis: 45000,
        market_value: 50000,
        allocation_percent: 36.4,
        holdings_count: 2,
        priced_count: 2,
        unpriced_count: 0,
      },
    ],
    holdings: [
      {
        holding_id: 'h-rel',
        symbol: 'RELIANCE',
        exchange: 'NSE',
        quantity: 15,
        average_buy_price: 2500,
        cost_basis: 37500,
        current_price: 2600,
        market_value: 39000,
        unrealized_pnl: 1500,
        unrealized_pnl_percent: 4.0,
        market_value_weight_percent: 28.5,
        cost_basis_weight_percent: 30.0,
        pricing_status: 'AVAILABLE',
        is_simulated: true,
        is_stale: false,
        sector: 'Energy',
        asset_class: 'EQUITY',
      },
    ],
    disclaimer: 'Calculated using simulated prices for academic evaluation only.',
  };

  // Mock Analytics for port-tech-growth
  const mockTechAnalytics: PortfolioAnalyticsResponse = {
    ...mockBluechipAnalytics,
    portfolio_id: 'port-tech-growth',
    portfolio_name: 'Tech Growth Sandbox',
    is_sample: false,
    valuation: {
      total_cost_basis: 80000,
      total_market_value: 92000,
      priced_cost_basis: 80000,
      unrealized_pnl: 12000,
      unrealized_pnl_percent: 15.0,
    },
    concentration: {
      top_holding_symbol: 'TCS',
      top_holding_weight_percent: 60.0,
      top_3_concentration_percent: 100.0,
      herfindahl_index: 0.52,
      effective_holdings_count: 1.9,
    },
    risk_assessment: {
      composite_risk_score: 68.0,
      risk_tier: 'ELEVATED',
      assessment_status: 'COMPLETE',
      components: {
        single_stock_concentration_score: 72.0,
        sector_concentration_score: 65.0,
        diversification_breadth_score: 60.0,
        data_quality_score: 0.0,
      },
      weights: {
        single_stock: 0.35,
        sector: 0.25,
        breadth: 0.25,
        quality: 0.15,
      },
      methodology_scope: 'Deterministic 4-factor scoring model',
      disclaimer: 'Calculated using simulated prices for academic study only.',
    },
    sector_allocations: [
      {
        sector: 'Technology',
        cost_basis: 80000,
        market_value: 92000,
        allocation_percent: 100.0,
        holdings_count: 2,
        priced_count: 2,
        unpriced_count: 0,
      },
    ],
    holdings: [
      {
        holding_id: 'h-tcs',
        symbol: 'TCS',
        exchange: 'NSE',
        quantity: 20,
        average_buy_price: 3500,
        cost_basis: 70000,
        current_price: 3900,
        market_value: 78000,
        unrealized_pnl: 8000,
        unrealized_pnl_percent: 11.4,
        market_value_weight_percent: 84.8,
        cost_basis_weight_percent: 87.5,
        pricing_status: 'AVAILABLE',
        is_simulated: true,
        is_stale: false,
        sector: 'Technology',
        asset_class: 'EQUITY',
      },
    ],
  };

  // Mock Rule-Based Insights
  const mockInsightsData: PortfolioInsightsResponse = {
    portfolio_id: 'port-bluechip',
    insights: [],
    total_insights: 0,
    generated_at: '2026-10-11T10:00:00Z',
    is_sample_portfolio: true,
    disclaimer: 'Deterministic insights for educational reference.',
  };

  // Mock Market Data Batch Quotes
  const mockBatchQuotes: BatchQuotesResponse = {
    quotes: {
      RELIANCE: {
        symbol: 'RELIANCE',
        exchange: 'NSE',
        current_price: 2600,
        change: 15.0,
        change_percent: 0.58,
        status: 'AVAILABLE',
        source: 'SIMULATED_DEMO_PROVIDER',
        is_simulated: true,
        is_stale: false,
        generated_at: '2026-10-11T10:00:00Z',
        cache_hit: true,
        disclaimer: 'Simulated quote for academic study only.',
      },
    },
    total_symbols: 1,
    cache_hits_count: 1,
    cache_misses_count: 0,
    fetched_at: '2026-10-11T10:00:00Z',
  };

  // Mock News
  const mockNewsData: NewsResponse = {
    articles: [],
    total_count: 0,
    fetched_at: '2026-10-11T10:00:00Z',
    cache_hit: false,
    is_simulated: true,
    disclaimer: 'Educational simulated financial news.',
  };

  // Mock AI Report for Bluechip
  const mockBluechipAIReport: AIInsightReport = {
    report_id: 'rep-bluechip',
    portfolio_id: 'port-bluechip',
    generated_at: '2026-10-11T10:00:00Z',
    provider_name: 'DETERMINISTIC_DEMO_REASONER',
    model_id: 'deterministic-demo-v1',
    is_simulated: true,
    executive_summary: 'Bluechip portfolio exhibits balanced sector diversification.',
    key_drivers: [
      {
        driver_id: 'd-1',
        driver_type: 'CONCENTRATION',
        title: 'Top Holding Diversified',
        statement: 'RELIANCE represents 28.5% of total known market value.',
        supporting_metric_key: 'concentration.top_holding_weight_percent',
        supporting_metric_value: 28.5,
        source_reference: 'analytics.concentration',
        is_grounded: true,
      },
    ],
    risk_alerts: [],
    confidence: {
      score: 0.95,
      level: 'HIGH',
      calibration_limitation: 'Calculated using deterministic heuristic algorithms.',
      data_quality_discount: 0.05,
      staleness_discount: 0.0,
    },
    review_cards: [
      {
        card_id: 'rc-1',
        title: 'Balanced Large Cap Holdings',
        category: 'CONCENTRATION',
        severity: 'LOW',
        description: 'Top holding RELIANCE is under 30% allocation.',
        cited_metrics: { top_weight: '28.5%' },
        related_symbols: ['RELIANCE'],
        review_status: 'VERIFIED',
        created_at: '2026-10-11T10:00:00Z',
      },
    ],
    uncertainty_and_gaps: [
      'Simulated prices used for academic evaluation.',
    ],
    disclaimers: [
      'Educational intelligence only. Not SEBI advice.',
    ],
    review_status: 'VERIFIED',
    grounding_report: {
      total_claims_checked: 5,
      passed_count: 5,
      flagged_count: 0,
      rejected_count: 0,
      is_acceptable: true,
      findings: [
        {
          check_name: 'HOLDING_WEIGHT_CHECK',
          target_id: 'RELIANCE',
          status: 'PASSED',
          reason: 'Verified consistent against portfolio evidence bundle.',
          details: { verified_weight: '28.5%' },
        },
      ],
    },
  };

  // Mock AI Report for Tech Growth
  const mockTechAIReport: AIInsightReport = {
    ...mockBluechipAIReport,
    report_id: 'rep-tech-growth',
    portfolio_id: 'port-tech-growth',
    executive_summary: 'Tech growth portfolio exhibits high sector concentration.',
    review_status: 'FLAGGED_WITH_WARNINGS',
    grounding_report: {
      total_claims_checked: 4,
      passed_count: 3,
      flagged_count: 1,
      rejected_count: 0,
      is_acceptable: true,
      findings: [
        {
          check_name: 'SECTOR_CONCENTRATION_CHECK',
          target_id: 'Technology',
          status: 'FLAGGED',
          reason: '100% technology sector exposure presents single-sector risk.',
          details: { sector_weight: '100%' },
        },
      ],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue(mockPortfolios);
    vi.mocked(healthApi.fetchHealth).mockResolvedValue(mockHealthData);
    vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockImplementation(async (id: string) => {
      if (id === 'port-tech-growth') return mockTechAnalytics;
      return mockBluechipAnalytics;
    });
    vi.mocked(analyticsApi.fetchPortfolioInsights).mockResolvedValue(mockInsightsData);
    vi.mocked(marketDataApi.fetchQuote).mockResolvedValue(mockBatchQuotes.quotes.RELIANCE);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotes);
    vi.mocked(newsApi.fetchNews).mockResolvedValue(mockNewsData);
    vi.mocked(aiReasoningApi.generateAIPortfolioInsights).mockImplementation(async (id: string) => {
      if (id === 'port-tech-growth') return mockTechAIReport;
      return mockBluechipAIReport;
    });
  });

  it('Scenario 1: loads initial portfolio list, selects first portfolio, and renders Portfolio Hub data', async () => {
    render(<App />);

    // 1. Portfolio list is loaded and default first portfolio is selected in header dropdown
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toHaveValue(
        'port-bluechip'
      );
    });

    // 2. Portfolio Hub tabpanel is rendered by default
    expect(
      screen.getByRole('tabpanel', { name: /portfolio intelligence hub/i })
    ).toBeInTheDocument();

    // 3. Portfolio analytics for default portfolio are rendered
    await waitFor(() => {
      expect(screen.getAllByText(/Demo Indian Bluechip Portfolio/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });

    // 4. ₹0 spend policy active badge is visible in header
    expect(screen.getByText(/₹0 Spend Policy Active/i)).toBeInTheDocument();
  });

  it('Scenario 2: preserves active portfolio across all seven navigation views', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toHaveValue(
        'port-bluechip'
      );
    });

    const selector = screen.getByRole('combobox', { name: /select active portfolio/i });

    // 1. Risk & Exposure
    fireEvent.click(screen.getByRole('tab', { name: 'Risk & Exposure' }));
    expect(screen.getByRole('tabpanel', { name: /risk & exposure/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 2. Market Movement
    fireEvent.click(screen.getByRole('tab', { name: 'Market Movement' }));
    expect(screen.getByRole('tabpanel', { name: /market movement/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 3. Recommendation Review
    fireEvent.click(screen.getByRole('tab', { name: 'Recommendation Review' }));
    expect(screen.getByRole('tabpanel', { name: /recommendation review/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 4. Operations
    fireEvent.click(screen.getByRole('tab', { name: 'Operations' }));
    expect(screen.getByRole('tabpanel', { name: /operations/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 5. Compliance & Audit
    fireEvent.click(screen.getByRole('tab', { name: 'Compliance & Audit' }));
    expect(screen.getByRole('tabpanel', { name: /compliance & audit/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 6. Admin Configuration
    fireEvent.click(screen.getByRole('tab', { name: 'Admin Configuration' }));
    expect(screen.getByRole('tabpanel', { name: /admin configuration/i })).toBeInTheDocument();
    expect(selector).toHaveValue('port-bluechip');

    // 7. Return to Portfolio Hub
    fireEvent.click(screen.getByRole('tab', { name: 'Portfolio Intelligence Hub' }));
    await waitFor(() => {
      expect(
        screen.getByRole('tabpanel', { name: /portfolio intelligence hub/i })
      ).toBeInTheDocument();
    });
    expect(selector).toHaveValue('port-bluechip');
  });

  it('Scenario 3: switches portfolio in header and updates Portfolio Hub and Risk & Exposure data', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toHaveValue(
        'port-bluechip'
      );
    });

    const selector = screen.getByRole('combobox', { name: /select active portfolio/i });

    // Switch active portfolio to 'Tech Growth Sandbox'
    fireEvent.change(selector, { target: { value: 'port-tech-growth' } });
    expect(selector).toHaveValue('port-tech-growth');

    // Portfolio Hub immediately requests analytics for port-tech-growth
    await waitFor(() => {
      expect(analyticsApi.fetchPortfolioAnalytics).toHaveBeenCalledWith('port-tech-growth');
      expect(screen.getByText('TCS')).toBeInTheDocument();
    });

    // Switch to Risk & Exposure tab -> displays risk metrics for Tech Growth Sandbox
    fireEvent.click(screen.getByRole('tab', { name: 'Risk & Exposure' }));
    await waitFor(() => {
      expect(screen.getByRole('tabpanel', { name: /risk & exposure/i })).toBeInTheDocument();
      expect(screen.getByText('68.00')).toBeInTheDocument();
    });
  });

  it('Scenario 4: clears AI intelligence & audit reports when switching portfolios to prevent data leaks', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toHaveValue(
        'port-bluechip'
      );
    });

    // 1. Navigate to Recommendation Review
    fireEvent.click(screen.getByRole('tab', { name: 'Recommendation Review' }));
    const recoBtn = await screen.findByTestId('generate-review-btn');
    expect(recoBtn).toBeInTheDocument();

    // Verify initial pre-generation state
    expect(
      screen.getByText(/No Review Report Generated Yet for/i)
    ).toBeInTheDocument();

    // Trigger AI report generation explicitly
    fireEvent.click(recoBtn);

    await waitFor(() => {
      expect(aiReasoningApi.generateAIPortfolioInsights).toHaveBeenCalledWith(
        'port-bluechip',
        expect.anything()
      );
      expect(
        screen.getByText('Bluechip portfolio exhibits balanced sector diversification.')
      ).toBeInTheDocument();
    });

    // Switch portfolio in header dropdown to Tech Growth
    const selector = screen.getByRole('combobox', { name: /select active portfolio/i });
    fireEvent.change(selector, { target: { value: 'port-tech-growth' } });

    // PREVENTS REPORT LEAK: Previous Bluechip report must be completely wiped from the DOM
    await waitFor(() => {
      expect(
        screen.queryByText('Bluechip portfolio exhibits balanced sector diversification.')
      ).not.toBeInTheDocument();
      // Returns to clean pre-generation state
      expect(screen.getByTestId('generate-review-btn')).toBeInTheDocument();
      expect(
        screen.getByText(/No Review Report Generated Yet for/i)
      ).toBeInTheDocument();
    });

    // 2. Navigate to Compliance & Audit
    fireEvent.click(screen.getByRole('tab', { name: 'Compliance & Audit' }));
    const auditBtn = await screen.findByTestId('run-audit-btn');
    expect(auditBtn).toBeInTheDocument();

    // Trigger compliance audit generation on port-tech-growth
    fireEvent.click(auditBtn);

    await waitFor(() => {
      expect(aiReasoningApi.generateAIPortfolioInsights).toHaveBeenCalledWith(
        'port-tech-growth',
        expect.anything()
      );
      expect(
        screen.getByText(/100% technology sector exposure presents single-sector risk/i)
      ).toBeInTheDocument();
    });

    // Switch portfolio back to Bluechip
    fireEvent.change(selector, { target: { value: 'port-bluechip' } });

    // PREVENTS AUDIT LEAK: Tech audit must be completely wiped from DOM
    await waitFor(() => {
      expect(
        screen.queryByText(/100% technology sector exposure presents single-sector risk/i)
      ).not.toBeInTheDocument();
      // Returns to clean pre-audit state
      expect(screen.getByTestId('run-audit-btn')).toBeInTheDocument();
    });
  });

  it('Scenario 5: seeds demo portfolio from Admin Configuration and refreshes shared portfolio context', async () => {
    const mockSeedResponse: SeedDemoResponse = {
      created: true,
      message: 'Demo portfolio seeded successfully.',
      portfolio: {
        id: 'port-bluechip',
        name: 'Demo Indian Bluechip Portfolio',
        description: 'Canonical benchmark portfolio',
        is_sample: true,
        created_at: '2026-10-11T10:00:00Z',
        updated_at: '2026-10-11T10:00:00Z',
        holdings_count: 5,
        holdings: [],
      },
    };

    vi.mocked(portfoliosApi.seedDemoPortfolio).mockResolvedValue(mockSeedResponse);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toBeInTheDocument();
    });

    // Navigate to Admin Configuration
    fireEvent.click(screen.getByRole('tab', { name: 'Admin Configuration' }));
    expect(
      screen.getByRole('tabpanel', { name: /admin configuration/i })
    ).toBeInTheDocument();

    // Locate and trigger the seeding button
    const seedBtn = screen.getByTestId('seed-demo-portfolio-btn');
    expect(seedBtn).toBeInTheDocument();

    // Verify seedDemoPortfolio has not been called automatically
    expect(portfoliosApi.seedDemoPortfolio).not.toHaveBeenCalled();

    // Trigger seed action explicitly
    fireEvent.click(seedBtn);

    await waitFor(() => {
      expect(portfoliosApi.seedDemoPortfolio).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('seed-result-banner')).toBeInTheDocument();
    });

    expect(
      screen.getByText('Demo portfolio seeded successfully.')
    ).toBeInTheDocument();

    // Verifies portfolio list refreshed via fetchPortfolios
    expect(portfoliosApi.fetchPortfolios).toHaveBeenCalledTimes(2);
  });

  it('Scenario 6: maintains consistent navigation state and system governance badge across all views', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /select active portfolio/i })).toBeInTheDocument();
    });

    const spendBadge = screen.getByText(/₹0 Spend Policy Active/i);
    expect(spendBadge).toBeInTheDocument();

    // Cycle through all tabs and ensure spend policy and brand header persist
    const tabs = [
      'Risk & Exposure',
      'Market Movement',
      'Recommendation Review',
      'Operations',
      'Compliance & Audit',
      'Admin Configuration',
      'Portfolio Intelligence Hub',
    ];

    for (const tabName of tabs) {
      fireEvent.click(screen.getByRole('tab', { name: tabName }));
      expect(screen.getByText(/Zerodha: AI Financial Intelligence Platform/i)).toBeInTheDocument();
      expect(screen.getByText(/₹0 Spend Policy Active/i)).toBeInTheDocument();
    }

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });
  });
});
