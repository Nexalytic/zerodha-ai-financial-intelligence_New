import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PortfolioHub } from '../src/components/portfolio/PortfolioHub';
import { PortfolioOverviewCard } from '../src/components/portfolio/PortfolioOverviewCard';
import { HoldingsTable } from '../src/components/portfolio/HoldingsTable';
import { RuleBasedInsightsSection } from '../src/components/portfolio/RuleBasedInsightsSection';
import { AIInsightsSection } from '../src/components/portfolio/AIInsightsSection';
import { PortfolioProvider, usePortfolio } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import * as analyticsApi from '../src/api/analytics';
import * as aiReasoningApi from '../src/api/aiReasoning';
import { PortfolioResponse } from '../src/types/portfolio';
import {
  PortfolioAnalyticsResponse,
  HoldingAnalyticsDetail,
} from '../src/types/analytics';
import {
  PortfolioInsightsResponse,
  AIInsightReport,
} from '../src/types/aiReasoning';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/analytics');
vi.mock('../src/api/aiReasoning');

describe('Phase 07 Step 7.2: Portfolio Intelligence Hub', () => {
  const mockPortfolio: PortfolioResponse = {
    id: 'demo-portfolio-1',
    name: 'Demo Indian Bluechip Portfolio',
    description: 'Canonical bluechip benchmark portfolio',
    is_sample: true,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 5,
  };

  const mockPortfolioB: PortfolioResponse = {
    id: 'demo-portfolio-2',
    name: 'Growth Tech Portfolio',
    description: 'High-growth technology focus',
    is_sample: false,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 3,
  };

  const PortfolioTestHarness: React.FC = () => {
    const { portfolios, activePortfolioId, setActivePortfolioId } = usePortfolio();
    return (
      <div>
        <select
          data-testid="test-portfolio-selector"
          value={activePortfolioId || ''}
          onChange={(e) => setActivePortfolioId(e.target.value || null)}
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <PortfolioHub />
      </div>
    );
  };

  const mockCompleteAnalytics: PortfolioAnalyticsResponse = {
    portfolio_id: 'demo-portfolio-1',
    portfolio_name: 'Demo Indian Bluechip Portfolio',
    is_sample: true,
    calculated_at: '2026-10-10T00:00:00Z',
    status: 'COMPLETE',
    valuation: {
      total_cost_basis: 500000,
      total_market_value: 575000,
      priced_cost_basis: 500000,
      unrealized_pnl: 75000,
      unrealized_pnl_percent: 15.0,
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
      top_3_concentration_percent: 68.2,
      herfindahl_index: 0.22,
      effective_holdings_count: 4.5,
      concentration_tier: 'MODERATE',
    },
    sector_allocations: [],
    holdings: [
      {
        holding_id: 'h-1',
        symbol: 'RELIANCE',
        exchange: 'NSE',
        quantity: 100,
        average_buy_price: 2500,
        cost_basis: 250000,
        current_price: 2800,
        market_value: 280000,
        unrealized_pnl: 30000,
        unrealized_pnl_percent: 12.0,
        market_value_weight_percent: 48.7,
        cost_basis_weight_percent: 50.0,
        pricing_status: 'AVAILABLE',
        is_simulated: true,
        is_stale: false,
        sector: 'Energy',
        asset_class: 'EQUITY',
      },
      {
        holding_id: 'h-2',
        symbol: 'TCS',
        exchange: 'NSE',
        quantity: 50,
        average_buy_price: 3500,
        cost_basis: 175000,
        current_price: 3900,
        market_value: 195000,
        unrealized_pnl: 20000,
        unrealized_pnl_percent: 11.43,
        market_value_weight_percent: 33.91,
        cost_basis_weight_percent: 35.0,
        pricing_status: 'AVAILABLE',
        is_simulated: true,
        is_stale: false,
        sector: 'Technology',
        asset_class: 'EQUITY',
      },
    ],
    disclaimer: 'Educational purposes only. Zero spend policy.',
  };

  const mockInsights: PortfolioInsightsResponse = {
    portfolio_id: 'demo-portfolio-1',
    insights: [
      {
        id: 'ins-1',
        portfolio_id: 'demo-portfolio-1',
        category: 'CONCENTRATION',
        severity: 'WARNING',
        title: 'Single-Stock Concentration in RELIANCE',
        description: 'RELIANCE accounts for 48.7% of total portfolio value.',
        evidence: {
          symbol: 'RELIANCE',
          weight_percent: 48.7,
          threshold_percent: 30.0,
        },
        related_symbols: ['RELIANCE'],
        created_at: '2026-10-10T00:00:00Z',
        is_simulated: true,
        source: 'RULE_ENGINE',
        disclaimer: 'Not financial advice',
      },
      {
        id: 'ins-2',
        portfolio_id: 'demo-portfolio-1',
        category: 'RISK',
        severity: 'INFO',
        title: 'Diversification Breadth',
        description: 'Portfolio contains 5 holdings across 3 sectors.',
        evidence: { total_holdings: 5, sectors: 3 },
        related_symbols: [],
        created_at: '2026-10-10T00:00:00Z',
        is_simulated: true,
        source: 'RULE_ENGINE',
        disclaimer: 'Not financial advice',
      },
    ],
    total_insights: 2,
    generated_at: '2026-10-10T00:00:00Z',
    is_sample_portfolio: true,
    disclaimer: 'Deterministic observations only',
  };

  const mockVerifiedAIReport: AIInsightReport = {
    report_id: 'rep-verified-1',
    portfolio_id: 'demo-portfolio-1',
    provider_name: 'demo-deterministic',
    model_id: 'rule-grounded-v1',
    generated_at: '2026-10-10T00:00:00Z',
    is_simulated: true,
    review_status: 'VERIFIED',
    executive_summary:
      'The portfolio demonstrates solid unrealized gains driven by top-tier Indian bluechips with moderate single-stock exposure.',
    confidence: {
      score: 0.92,
      level: 'HIGH',
      data_quality_discount: 0.05,
      staleness_discount: 0.03,
      calibration_limitation:
        'Confidence scores are heuristic estimates calibrated against benchmark baselines and do not guarantee predictive accuracy.',
    },
    key_drivers: [
      {
        driver_id: 'drv-1',
        driver_type: 'CONCENTRATION',
        title: 'Reliance Heavy Weighting',
        statement: 'Reliance drives the majority of unrealized returns.',
        supporting_metric_key: 'holdings.RELIANCE.market_value_weight_percent',
        supporting_metric_value: 48.7,
        source_reference: 'portfolio_analytics.holdings[0]',
        is_grounded: true,
      },
    ],
    risk_alerts: [
      {
        alert_id: 'alt-1',
        category: 'CONCENTRATION',
        severity: 'MEDIUM',
        headline: 'Heavy Reliance Weight',
        explanation: 'Top holding exceeds recommended single-stock threshold of 30%.',
        evidence_reference: 'holdings.RELIANCE.market_value_weight_percent',
        actionable_mitigation: 'Consider monitoring sector exposure.',
      },
    ],
    grounding_report: {
      is_acceptable: true,
      total_claims_checked: 6,
      passed_count: 6,
      flagged_count: 0,
      rejected_count: 0,
      findings: [
        {
          check_name: 'metric_citation_check',
          target_id: 'drv-1',
          status: 'PASSED',
          reason: 'Exact match with underlying analytics.',
        },
      ],
    },
    review_cards: [],
    uncertainty_and_gaps: [],
    disclaimers: [
      'This report is generated for educational and informational purposes only.',
      'Not SEBI-registered investment advice.',
    ],
  };

  const mockRejectedAIReport: AIInsightReport = {
    report_id: 'rep-rejected-1',
    portfolio_id: 'demo-portfolio-1',
    provider_name: 'demo-deterministic',
    model_id: 'rule-grounded-v1',
    generated_at: '2026-10-10T00:00:00Z',
    is_simulated: true,
    review_status: 'REJECTED',
    executive_summary:
      'Hallucinated narrative referencing non-existent positions and unverified returns.',
    confidence: {
      score: 0.35,
      level: 'LOW',
      data_quality_discount: 0.4,
      staleness_discount: 0.25,
      calibration_limitation: 'Severely degraded due to claim grounding failures.',
    },
    key_drivers: [
      {
        driver_id: 'drv-unverified',
        driver_type: 'PERFORMANCE',
        title: 'Fabricated Growth Rate',
        statement: 'TCS generated 45% return this month.',
        supporting_metric_key: 'fabricated.tcs_return',
        supporting_metric_value: 45.0,
        source_reference: 'unverified_claim',
        is_grounded: false,
      },
    ],
    risk_alerts: [],
    grounding_report: {
      is_acceptable: false,
      total_claims_checked: 4,
      passed_count: 1,
      flagged_count: 1,
      rejected_count: 2,
      findings: [
        {
          check_name: 'metric_citation_check',
          target_id: 'drv-unverified',
          status: 'REJECTED',
          reason: 'Claimed metric not found in verified evidence bundle.',
        },
      ],
    },
    review_cards: [],
    uncertainty_and_gaps: ['Data gaps detected due to rejected claims'],
    disclaimers: [
      'This report is generated for educational and informational purposes only.',
      'Report failed strict programmatic claim grounding.',
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio]);
    vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockResolvedValue(mockCompleteAnalytics);
    vi.mocked(analyticsApi.fetchPortfolioInsights).mockResolvedValue(mockInsights);
  });

  // -------------------------------------------------------------
  // Suite 1: PortfolioHub Orchestrator
  // -------------------------------------------------------------
  describe('PortfolioHub Orchestrator', () => {
    it('renders empty state when no portfolios exist and supports seeding demo', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([]);
      vi.mocked(portfoliosApi.seedDemoPortfolio).mockResolvedValue({
        portfolio: { ...mockPortfolio, holdings: [] },
        created: true,
        message: 'Seeded demo portfolio successfully',
      });

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      // Wait for empty state
      await waitFor(() => {
        expect(screen.getByTestId('portfolio-hub-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('No Portfolios Available')).toBeInTheDocument();
      const seedBtn = screen.getByTestId('seed-demo-btn');
      expect(seedBtn).toBeInTheDocument();

      // Trigger seed action
      fireEvent.click(seedBtn);

      await waitFor(() => {
        expect(portfoliosApi.seedDemoPortfolio).toHaveBeenCalledTimes(1);
      });
    });

    it('renders the main hub when an active portfolio is loaded', async () => {
      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('portfolio-intelligence-hub')).toBeInTheDocument();
      });

      expect(screen.getByText('Portfolio Intelligence Hub')).toBeInTheDocument();
      expect(screen.getByTestId('portfolio-overview-card')).toBeInTheDocument();
      expect(screen.getByTestId('holdings-table-container')).toBeInTheDocument();
      expect(screen.getByTestId('rule-based-insights-section')).toBeInTheDocument();
      expect(screen.getByTestId('ai-insights-section')).toBeInTheDocument();
    });

    it('reloads analytics and insights when clicking the refresh button', async () => {
      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('portfolio-intelligence-hub')).toBeInTheDocument();
      });

      const refreshBtn = screen.getByTestId('refresh-hub-btn');
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(analyticsApi.fetchPortfolioAnalytics).toHaveBeenCalledTimes(2);
        expect(analyticsApi.fetchPortfolioInsights).toHaveBeenCalledTimes(2);
      });
    });

    it('displays error banner if analytics fails to load', async () => {
      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockRejectedValueOnce(
        new Error('Network transport error occurred')
      );

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-error-banner')).toBeInTheDocument();
      });

      expect(screen.getByText(/Network transport error occurred/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------
  // Suite 2: PortfolioOverviewCard
  // -------------------------------------------------------------
  describe('PortfolioOverviewCard', () => {
    it('displays COMPLETE valuation badge and metrics', () => {
      render(
        <PortfolioOverviewCard
          portfolio={mockPortfolio}
          analytics={mockCompleteAnalytics}
          isLoading={false}
        />
      );

      expect(screen.getByText('Demo Indian Bluechip Portfolio')).toBeInTheDocument();
      expect(screen.getByText('COMPLETE')).toBeInTheDocument();
      expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹5,75,000.00');
      expect(screen.getByTestId('total-cost-basis')).toHaveTextContent('₹5,00,000.00');
      expect(screen.getByTestId('unrealized-pnl')).toHaveTextContent('₹75,000.00');
      expect(screen.getByTestId('completeness-ratio')).toHaveTextContent('100%');
    });

    it('displays PARTIAL valuation badge and unpriced positions banner', () => {
      const partialAnalytics: PortfolioAnalyticsResponse = {
        ...mockCompleteAnalytics,
        status: 'PARTIAL',
        completeness: {
          is_complete: false,
          completeness_ratio: 0.8,
          total_holdings_count: 5,
          priced_holdings_count: 4,
          unpriced_holdings_count: 1,
          has_stale_prices: false,
          has_simulated_prices: true,
          unpriced_positions: [
            {
              holding_id: 'h-missing',
              symbol: 'WIPRO',
              exchange: 'NSE',
              quantity: 20,
              cost_basis: 10000,
              pricing_status: 'UNAVAILABLE',
              price_explanation: 'Provider quote rate limit reached',
            },
          ],
        },
      };

      render(
        <PortfolioOverviewCard
          portfolio={mockPortfolio}
          analytics={partialAnalytics}
          isLoading={false}
        />
      );

      expect(screen.getByText('PARTIAL VALUATION')).toBeInTheDocument();
      expect(screen.getByTestId('completeness-ratio')).toHaveTextContent('80%');
      expect(screen.getByTestId('unpriced-positions-banner')).toBeInTheDocument();
      expect(screen.getByText(/1 Unpriced Position Excluded/i)).toBeInTheDocument();
      expect(screen.getByText('WIPRO')).toBeInTheDocument();
      expect(screen.getByText(/Provider quote rate limit reached/i)).toBeInTheDocument();
    });

    it('displays warning banner when stale market quotes are present', () => {
      const staleAnalytics: PortfolioAnalyticsResponse = {
        ...mockCompleteAnalytics,
        completeness: {
          ...mockCompleteAnalytics.completeness,
          has_stale_prices: true,
        },
      };

      render(
        <PortfolioOverviewCard
          portfolio={mockPortfolio}
          analytics={staleAnalytics}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('stale-price-banner')).toBeInTheDocument();
      expect(screen.getByText(/Stale Market Quotes Detected/i)).toBeInTheDocument();
    });

    it('displays UNVALUED status badge when completeness is 0', () => {
      const unvaluedAnalytics: PortfolioAnalyticsResponse = {
        ...mockCompleteAnalytics,
        status: 'UNVALUED',
        completeness: {
          ...mockCompleteAnalytics.completeness,
          is_complete: false,
          completeness_ratio: 0.0,
          priced_holdings_count: 0,
          unpriced_holdings_count: 5,
        },
      };

      render(
        <PortfolioOverviewCard
          portfolio={mockPortfolio}
          analytics={unvaluedAnalytics}
          isLoading={false}
        />
      );

      expect(screen.getByText('UNVALUED')).toBeInTheDocument();
      expect(screen.getByTestId('completeness-ratio')).toHaveTextContent('0%');
    });
  });

  // -------------------------------------------------------------
  // Suite 3: HoldingsTable
  // -------------------------------------------------------------
  describe('HoldingsTable', () => {
    it('renders holdings rows with symbol, sector, prices, weights, and simulated badges', () => {
      render(
        <HoldingsTable holdings={mockCompleteAnalytics.holdings} isLoading={false} />
      );

      expect(screen.getByRole('table', { name: /portfolio holdings/i })).toBeInTheDocument();
      expect(screen.getByTestId('holding-row-RELIANCE')).toBeInTheDocument();
      expect(screen.getByTestId('holding-row-TCS')).toBeInTheDocument();

      const relianceRow = screen.getByTestId('holding-row-RELIANCE');
      expect(relianceRow).toHaveTextContent('RELIANCE');
      expect(relianceRow).toHaveTextContent('NSE');
      expect(relianceRow).toHaveTextContent('Energy');
      expect(relianceRow).toHaveTextContent('₹2,500.00'); // avg buy price
      expect(relianceRow).toHaveTextContent('₹2,800.00'); // current market price
      expect(relianceRow).toHaveTextContent('48.70%'); // weight

      // Simulated badge
      expect(screen.getAllByTestId('simulated-price-badge').length).toBeGreaterThan(0);
    });

    it('renders unpriced position with "Unavailable" and handles stale badge', () => {
      const mixedHoldings: HoldingAnalyticsDetail[] = [
        {
          holding_id: 'h-unpriced',
          symbol: 'INFY',
          exchange: 'NSE',
          quantity: 40,
          average_buy_price: 1500,
          cost_basis: 60000,
          current_price: null,
          market_value: null,
          unrealized_pnl: null,
          unrealized_pnl_percent: null,
          market_value_weight_percent: null,
          cost_basis_weight_percent: 12.0,
          pricing_status: 'UNAVAILABLE',
          price_explanation: 'Provider quote unavailable',
          is_simulated: false,
          is_stale: false,
          sector: 'Technology',
          asset_class: 'EQUITY',
        },
        {
          holding_id: 'h-stale',
          symbol: 'HDFCBANK',
          exchange: 'NSE',
          quantity: 25,
          average_buy_price: 1600,
          cost_basis: 40000,
          current_price: 1650,
          market_value: 41250,
          unrealized_pnl: 1250,
          unrealized_pnl_percent: 3.125,
          market_value_weight_percent: 8.25,
          cost_basis_weight_percent: 8.0,
          pricing_status: 'AVAILABLE',
          is_simulated: true,
          is_stale: true,
          sector: 'Financial Services',
          asset_class: 'EQUITY',
        },
      ];

      render(<HoldingsTable holdings={mixedHoldings} isLoading={false} />);

      // Unpriced holding cell shows Unavailable
      expect(screen.getByTestId('missing-price-cell')).toHaveTextContent('Unavailable');
      expect(screen.getByTestId('unavailable-price-badge')).toBeInTheDocument();

      // Stale holding badge
      expect(screen.getByTestId('stale-price-badge')).toBeInTheDocument();
    });

    it('renders empty table notice when holdings array is empty', () => {
      render(<HoldingsTable holdings={[]} isLoading={false} />);
      expect(screen.getByText('No positions held in this portfolio.')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------
  // Suite 4: RuleBasedInsightsSection
  // -------------------------------------------------------------
  describe('RuleBasedInsightsSection', () => {
    it('renders deterministic rule observations with categories and evidence', () => {
      render(
        <RuleBasedInsightsSection
          insightsResponse={mockInsights}
          isLoading={false}
          error={null}
        />
      );

      expect(screen.getByText('Deterministic Portfolio Observations')).toBeInTheDocument();
      expect(screen.getByText('Single-Stock Concentration in RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('WARNING')).toBeInTheDocument();
      expect(screen.getByText('CONCENTRATION')).toBeInTheDocument();
      expect(screen.getByText(/48.7% of total portfolio value/i)).toBeInTheDocument();
      expect(screen.getByText(/threshold_percent:/i)).toBeInTheDocument();
    });

    it('renders empty state when no insights were generated', () => {
      const emptyInsights: PortfolioInsightsResponse = {
        ...mockInsights,
        insights: [],
        total_insights: 0,
      };

      render(
        <RuleBasedInsightsSection
          insightsResponse={emptyInsights}
          isLoading={false}
          error={null}
        />
      );

      expect(screen.getByTestId('no-insights-indicator')).toBeInTheDocument();
    });

    it('renders error state when rule calculation failed', () => {
      render(
        <RuleBasedInsightsSection
          insightsResponse={null}
          isLoading={false}
          error="Failed to connect to rule evaluation service"
        />
      );

      expect(screen.getByTestId('rule-insights-error')).toBeInTheDocument();
      expect(
        screen.getByText('Failed to connect to rule evaluation service')
      ).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------
  // Suite 5: AIInsightsSection
  // -------------------------------------------------------------
  describe('AIInsightsSection', () => {
    it('renders initial state with Generate AI Report button and triggers generation', () => {
      const onGenerateMock = vi.fn();
      render(
        <AIInsightsSection
          aiReport={null}
          isGenerating={false}
          error={null}
          onGenerate={onGenerateMock}
          portfolioId="demo-portfolio-1"
        />
      );

      expect(screen.getByTestId('ai-uninitialized-state')).toBeInTheDocument();
      const generateBtn = screen.getByTestId('generate-ai-btn');
      expect(generateBtn).toHaveTextContent('Generate AI Report');

      fireEvent.click(generateBtn);
      expect(onGenerateMock).toHaveBeenCalledTimes(1);
    });

    it('renders loading state when synthesis is in progress', () => {
      render(
        <AIInsightsSection
          aiReport={null}
          isGenerating={true}
          error={null}
          onGenerate={vi.fn()}
          portfolioId="demo-portfolio-1"
        />
      );

      expect(screen.getByTestId('ai-loading-state')).toBeInTheDocument();
      expect(
        screen.getByText(/Gathering Evidence & Executing Grounded Reasoning.../i)
      ).toBeInTheDocument();
    });

    it('renders error banner when AI generation fails', () => {
      render(
        <AIInsightsSection
          aiReport={null}
          isGenerating={false}
          error="Groq API key not configured or provider unavailable"
          onGenerate={vi.fn()}
          portfolioId="demo-portfolio-1"
        />
      );

      expect(screen.getByTestId('ai-error-banner')).toBeInTheDocument();
      expect(
        screen.getByText(/Groq API key not configured or provider unavailable/i)
      ).toBeInTheDocument();
    });

    it('renders verified grounded AI report with executive summary, confidence disclosures, drivers, and audit findings', () => {
      render(
        <AIInsightsSection
          aiReport={mockVerifiedAIReport}
          isGenerating={false}
          error={null}
          onGenerate={vi.fn()}
          portfolioId="demo-portfolio-1"
        />
      );

      // Status badge is VERIFIED GROUNDED
      expect(screen.getByTestId('ai-status-verified')).toHaveTextContent('VERIFIED GROUNDED');

      // Executive narrative
      expect(screen.getByTestId('ai-executive-summary')).toHaveTextContent(
        'The portfolio demonstrates solid unrealized gains'
      );

      // Confidence & Calibration limitation
      expect(screen.getByTestId('ai-confidence-score')).toHaveTextContent('92%');
      expect(screen.getByTestId('calibration-limitation-text')).toHaveTextContent(
        'Confidence scores are heuristic estimates calibrated against benchmark baselines'
      );

      // Key drivers with metric citations
      expect(screen.getByTestId('key-driver-drv-1')).toHaveTextContent(
        'Reliance Heavy Weighting'
      );
      expect(screen.getByTestId('key-driver-drv-1')).toHaveTextContent(
        'holdings.RELIANCE.market_value_weight_percent'
      );

      // Grounding report badge
      expect(screen.getByTestId('grounding-acceptable-badge')).toHaveTextContent(
        'ACCEPTABLE'
      );
    });

    it('STRICT REJECTION HANDLING: clearly rejects ungrounded report and never displays it as verified', () => {
      render(
        <AIInsightsSection
          aiReport={mockRejectedAIReport}
          isGenerating={false}
          error={null}
          onGenerate={vi.fn()}
          portfolioId="demo-portfolio-1"
        />
      );

      // Must display CLAIM GROUNDING REJECTED badge
      expect(screen.getByTestId('ai-status-rejected')).toHaveTextContent(
        'CLAIM GROUNDING REJECTED'
      );

      // Must NOT display verified status
      expect(screen.queryByTestId('ai-status-verified')).not.toBeInTheDocument();

      // Must display prominent rejection warning notice
      const rejectionNotice = screen.getByTestId('rejected-warning-notice');
      expect(rejectionNotice).toBeInTheDocument();
      expect(rejectionNotice).toHaveTextContent(
        'CRITICAL: REPORT REJECTED — Do not display or act on ungrounded claims!'
      );

      // Grounding report status must be UNACCEPTABLE
      expect(screen.getByTestId('grounding-acceptable-badge')).toHaveTextContent(
        'UNACCEPTABLE'
      );
    });
  });

  // -------------------------------------------------------------
  // Suite 6: Regression Tests (Audit Remediation)
  // -------------------------------------------------------------
  describe('Audit Remediation Regressions', () => {
    it('AI report for Portfolio A disappears immediately when Portfolio B is selected', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio, mockPortfolioB]);
      vi.mocked(aiReasoningApi.generateAIPortfolioInsights).mockResolvedValue(mockVerifiedAIReport);

      render(
        <PortfolioProvider>
          <PortfolioTestHarness />
        </PortfolioProvider>
      );

      // Wait for Portfolio A to load
      await waitFor(() => {
        expect(screen.getByTestId('test-portfolio-selector')).toHaveValue('demo-portfolio-1');
      });

      // Generate AI Report for Portfolio A
      const generateBtn = screen.getByTestId('generate-ai-btn');
      fireEvent.click(generateBtn);

      await waitFor(() => {
        expect(screen.getByTestId('ai-status-verified')).toBeInTheDocument();
        expect(screen.getByTestId('ai-executive-summary')).toBeInTheDocument();
      });

      // Now switch to Portfolio B
      const selector = screen.getByTestId('test-portfolio-selector');
      fireEvent.change(selector, { target: { value: 'demo-portfolio-2' } });

      // AI report for Portfolio A must disappear immediately
      await waitFor(() => {
        expect(screen.queryByTestId('ai-status-verified')).not.toBeInTheDocument();
        expect(screen.queryByTestId('ai-executive-summary')).not.toBeInTheDocument();
        expect(screen.getByTestId('ai-uninitialized-state')).toBeInTheDocument();
      });
    });

    it('a late AI result from Portfolio A cannot appear while Portfolio B is active', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio, mockPortfolioB]);

      let resolveAIPromise!: (value: AIInsightReport) => void;
      const delayedAIPromise = new Promise<AIInsightReport>((resolve) => {
        resolveAIPromise = resolve;
      });
      vi.mocked(aiReasoningApi.generateAIPortfolioInsights).mockReturnValue(delayedAIPromise);

      render(
        <PortfolioProvider>
          <PortfolioTestHarness />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('test-portfolio-selector')).toHaveValue('demo-portfolio-1');
      });

      // Start AI generation for Portfolio A
      const generateBtn = screen.getByTestId('generate-ai-btn');
      fireEvent.click(generateBtn);

      expect(screen.getByTestId('ai-loading-state')).toBeInTheDocument();

      // Before AI completes, switch to Portfolio B
      const selector = screen.getByTestId('test-portfolio-selector');
      fireEvent.change(selector, { target: { value: 'demo-portfolio-2' } });

      // Loading state stops, uninitialized state shown
      await waitFor(() => {
        expect(screen.queryByTestId('ai-loading-state')).not.toBeInTheDocument();
        expect(screen.getByTestId('ai-uninitialized-state')).toBeInTheDocument();
      });

      // Now resolve Portfolio A's late AI promise
      resolveAIPromise(mockVerifiedAIReport);

      // Verify Portfolio A's report is discarded and does not appear
      await waitFor(() => {
        expect(screen.queryByTestId('ai-status-verified')).not.toBeInTheDocument();
        expect(screen.getByTestId('ai-uninitialized-state')).toBeInTheDocument();
      });
    });

    it('a demo-seeding failure is visible and the action can be retried', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([]);
      vi.mocked(portfoliosApi.seedDemoPortfolio).mockRejectedValueOnce(
        new Error('Database lock error during demo seeding')
      );

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('portfolio-hub-empty')).toBeInTheDocument();
      });

      const seedBtn = screen.getByTestId('seed-demo-btn');
      fireEvent.click(seedBtn);

      // Error message should appear in empty state
      await waitFor(() => {
        expect(screen.getByTestId('seed-demo-error')).toBeInTheDocument();
      });
      expect(screen.getByText(/Database lock error during demo seeding/i)).toBeInTheDocument();

      // Button is still clickable / enabled after failure
      expect(seedBtn).not.toBeDisabled();

      // Now configure successful seed and retry
      vi.mocked(portfoliosApi.seedDemoPortfolio).mockResolvedValueOnce({
        portfolio: { ...mockPortfolio, holdings: [] },
        created: true,
        message: 'Seeded successfully',
      });

      fireEvent.click(seedBtn);

      await waitFor(() => {
        expect(portfoliosApi.seedDemoPortfolio).toHaveBeenCalledTimes(2);
      });
    });

    it('a delayed analytics response for Portfolio A cannot overwrite Portfolio B analytics', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio, mockPortfolioB]);

      let resolveAnalyticsA!: (value: PortfolioAnalyticsResponse) => void;
      const delayedAnalyticsA = new Promise<PortfolioAnalyticsResponse>((resolve) => {
        resolveAnalyticsA = resolve;
      });

      const mockAnalyticsB: PortfolioAnalyticsResponse = {
        ...mockCompleteAnalytics,
        portfolio_id: 'demo-portfolio-2',
        portfolio_name: 'Growth Tech Portfolio',
        valuation: {
          ...mockCompleteAnalytics.valuation,
          total_market_value: 999999,
        },
      };

      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockImplementation((id: string) => {
        if (id === 'demo-portfolio-1') {
          return delayedAnalyticsA;
        }
        return Promise.resolve(mockAnalyticsB);
      });

      render(
        <PortfolioProvider>
          <PortfolioTestHarness />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('test-portfolio-selector')).toHaveValue('demo-portfolio-1');
      });

      // Switch to Portfolio B before Portfolio A analytics resolves
      const selector = screen.getByTestId('test-portfolio-selector');
      fireEvent.change(selector, { target: { value: 'demo-portfolio-2' } });

      // Portfolio B resolves and renders its value
      await waitFor(() => {
        expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹9,99,999.00');
      });

      // Now resolve delayed analytics A with Portfolio A's old value
      resolveAnalyticsA({
        ...mockCompleteAnalytics,
        valuation: {
          ...mockCompleteAnalytics.valuation,
          total_market_value: 111111,
        },
      });

      // Portfolio B's value must NOT be overwritten by Portfolio A
      await waitFor(() => {
        expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹9,99,999.00');
      });
    });

    it('a delayed insights response for Portfolio A cannot overwrite Portfolio B insights', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio, mockPortfolioB]);

      let resolveInsightsA!: (value: PortfolioInsightsResponse) => void;
      const delayedInsightsA = new Promise<PortfolioInsightsResponse>((resolve) => {
        resolveInsightsA = resolve;
      });

      const mockInsightsB: PortfolioInsightsResponse = {
        ...mockInsights,
        portfolio_id: 'demo-portfolio-2',
        insights: [
          {
            ...mockInsights.insights[0],
            id: 'ins-b',
            title: 'Portfolio B Exclusive Sector Alert',
          },
        ],
      };

      vi.mocked(analyticsApi.fetchPortfolioInsights).mockImplementation((id: string) => {
        if (id === 'demo-portfolio-1') {
          return delayedInsightsA;
        }
        return Promise.resolve(mockInsightsB);
      });

      render(
        <PortfolioProvider>
          <PortfolioTestHarness />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('test-portfolio-selector')).toHaveValue('demo-portfolio-1');
      });

      // Switch to Portfolio B
      const selector = screen.getByTestId('test-portfolio-selector');
      fireEvent.change(selector, { target: { value: 'demo-portfolio-2' } });

      // Portfolio B insight is displayed
      await waitFor(() => {
        expect(screen.getByText('Portfolio B Exclusive Sector Alert')).toBeInTheDocument();
      });

      // Now resolve delayed insights A with a stale title
      resolveInsightsA({
        ...mockInsights,
        portfolio_id: 'demo-portfolio-1',
        insights: [
          {
            ...mockInsights.insights[0],
            id: 'ins-a-stale',
            title: 'Portfolio A Obsolete Stale Observation',
          },
        ],
      });

      // Stale observation must NOT overwrite or appear in Portfolio B
      await waitFor(() => {
        expect(screen.getByText('Portfolio B Exclusive Sector Alert')).toBeInTheDocument();
        expect(
          screen.queryByText('Portfolio A Obsolete Stale Observation')
        ).not.toBeInTheDocument();
      });
    });

    it('an older refresh cannot overwrite a newer refresh for the same portfolio', async () => {
      let callCount = 0;
      let resolveFirstRefresh!: (value: PortfolioAnalyticsResponse) => void;
      const delayedFirstRefresh = new Promise<PortfolioAnalyticsResponse>((resolve) => {
        resolveFirstRefresh = resolve;
      });

      const refreshedAnalytics: PortfolioAnalyticsResponse = {
        ...mockCompleteAnalytics,
        valuation: {
          ...mockCompleteAnalytics.valuation,
          total_market_value: 888888,
        },
      };

      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockImplementation(() => {
        callCount++;
        if (callCount === 2) {
          // First refresh call: slow response
          return delayedFirstRefresh;
        }
        if (callCount === 3) {
          // Second refresh call: fast response
          return Promise.resolve(refreshedAnalytics);
        }
        return Promise.resolve(mockCompleteAnalytics);
      });

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹5,75,000.00');
      });

      const refreshBtn = screen.getByTestId('refresh-hub-btn');

      // Click refresh 1 (starts slow call)
      fireEvent.click(refreshBtn);

      // Click refresh 2 (starts and completes fast call)
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹8,88,888.00');
      });

      // Now resolve the older refresh with an obsolete value
      resolveFirstRefresh({
        ...mockCompleteAnalytics,
        valuation: {
          ...mockCompleteAnalytics.valuation,
          total_market_value: 222222,
        },
      });

      // Value must remain the newer refresh value (888888) and NOT be overwritten by 222222
      await waitFor(() => {
        expect(screen.getByTestId('total-market-value')).toHaveTextContent('₹8,88,888.00');
      });
    });
  });
});
