import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { RiskExposurePanel } from '../src/components/risk/RiskExposurePanel';
import { RiskScoreCard } from '../src/components/risk/RiskScoreCard';
import { ConcentrationCard } from '../src/components/risk/ConcentrationCard';
import { SectorAllocationsCard } from '../src/components/risk/SectorAllocationsCard';
import { DataCompletenessCard } from '../src/components/risk/DataCompletenessCard';
import { HistoricalRiskCard } from '../src/components/risk/HistoricalRiskCard';
import { RiskInsightsSection } from '../src/components/risk/RiskInsightsSection';
import { PortfolioProvider, usePortfolio } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import * as analyticsApi from '../src/api/analytics';
import { PortfolioResponse } from '../src/types/portfolio';
import {
  PortfolioAnalyticsResponse,
  PortfolioRiskAssessment,
  HistoricalRiskMetrics,
  SectorAllocation,
} from '../src/types/analytics';
import { PortfolioInsightsResponse } from '../src/types/aiReasoning';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/analytics');

describe('Phase 07 Step 7.3: Risk & Exposure Panel', () => {
  const mockPortfolioA: PortfolioResponse = {
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
    name: 'Aggressive Tech Growth',
    description: 'Concentrated technology assets',
    is_sample: false,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 3,
  };

  const mockRiskAssessment: PortfolioRiskAssessment = {
    composite_risk_score: 42.5,
    risk_tier: 'MODERATE',
    assessment_status: 'COMPLETE',
    components: {
      single_stock_concentration_score: 52.0,
      sector_concentration_score: 45.0,
      diversification_breadth_score: 35.0,
      data_quality_score: 20.0,
    },
    weights: {
      single_stock_concentration: 0.35,
      sector_concentration: 0.25,
      diversification_breadth: 0.2,
      data_quality: 0.2,
    },
    methodology_scope:
      'Measures structural portfolio concentration, sector exposure, breadth (ENH), and valuation completeness.',
    disclaimer: 'Educational and demonstration risk assessment only. Not SEBI-registered investment advice.',
  };

  const mockHistoricalRisk: HistoricalRiskMetrics = {
    annualized_volatility_percent: null,
    maximum_drawdown_percent: null,
    beta: null,
    benchmark_relative_return_percent: null,
    benchmark_symbol: 'NIFTY 50',
    data_status: 'INSUFFICIENT_HISTORY',
    disclaimer:
      'Historical volatility and risk metrics reflect actual chronological price observations when available.',
  };

  const mockSectors: SectorAllocation[] = [
    {
      sector: 'Energy',
      cost_basis: 150000,
      market_value: 175000,
      allocation_percent: 30.43,
      cost_basis_weight_percent: 30.0,
      unrealized_pnl: 25000,
      unrealized_pnl_percent: 16.67,
      cost_basis_weighted_return_contribution_percent: 5.0,
      holdings_count: 1,
      priced_count: 1,
      unpriced_count: 0,
    },
    {
      sector: 'Technology',
      cost_basis: 200000,
      market_value: 230000,
      allocation_percent: 40.0,
      cost_basis_weight_percent: 40.0,
      unrealized_pnl: 30000,
      unrealized_pnl_percent: 15.0,
      cost_basis_weighted_return_contribution_percent: 6.0,
      holdings_count: 2,
      priced_count: 2,
      unpriced_count: 0,
    },
  ];

  const mockAnalyticsA: PortfolioAnalyticsResponse = {
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
    sector_allocations: mockSectors,
    holdings: [],
    historical_risk: mockHistoricalRisk,
    risk_assessment: mockRiskAssessment,
    disclaimer: 'Calculated analytics reflect simulated market quotes.',
  };

  const mockInsights: PortfolioInsightsResponse = {
    portfolio_id: 'demo-portfolio-1',
    total_insights: 2,
    generated_at: '2026-10-10T00:00:00Z',
    is_sample_portfolio: true,
    disclaimer: 'Educational insights only.',
    insights: [
      {
        id: 'ins-risk-1',
        portfolio_id: 'demo-portfolio-1',
        category: 'RISK',
        severity: 'WARNING',
        title: 'Moderate Portfolio Risk Detected (Score: 42.50/100)',
        description: 'Single-stock concentration in RELIANCE contributes 52.00 risk points.',
        evidence: { composite_risk_score: 42.5, top_weight: '28.50%' },
        related_symbols: ['RELIANCE'],
        created_at: '2026-10-10T00:00:00Z',
        is_simulated: true,
        source: 'DETERMINISTIC_RISK_ENGINE',
        disclaimer: 'Educational purposes only.',
      },
      {
        id: 'ins-conc-2',
        portfolio_id: 'demo-portfolio-1',
        category: 'CONCENTRATION',
        severity: 'INFO',
        title: 'Technology Sector Concentration',
        description: 'Technology accounts for 40.00% of priced market value.',
        evidence: { sector: 'Technology', weight: '40.00%' },
        related_symbols: ['TCS', 'INFY'],
        created_at: '2026-10-10T00:00:00Z',
        is_simulated: true,
        source: 'RULE_BASED_ANALYTICS',
        disclaimer: 'Educational purposes only.',
      },
    ],
  };

  const RiskTestHarness: React.FC = () => {
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
        <RiskExposurePanel />
      </div>
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolioA]);
    vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockResolvedValue(mockAnalyticsA);
    vi.mocked(analyticsApi.fetchPortfolioInsights).mockResolvedValue(mockInsights);
  });

  // -------------------------------------------------------------------------
  // Suite 1: RiskScoreCard & Tier Rendering
  // -------------------------------------------------------------------------
  describe('RiskScoreCard', () => {
    it('renders composite risk score, MODERATE tier badge, and component scores', () => {
      render(
        <RiskScoreCard
          riskAssessment={mockRiskAssessment}
          valuationStatus="COMPLETE"
          isLoading={false}
        />
      );

      expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('42.50');
      expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent(/MODERATE RISK/i);
      expect(screen.getByTestId('component-stock-concentration')).toHaveTextContent('52.00');
      expect(screen.getByTestId('component-sector-concentration')).toHaveTextContent('45.00');
      expect(screen.getByTestId('component-diversification-breadth')).toHaveTextContent('35.00');
      expect(screen.getByTestId('component-data-quality')).toHaveTextContent('20.00');
      expect(screen.getByText(/Deterministic Heuristic Model/i)).toBeInTheDocument();
      expect(screen.getByText(/^LOW$/)).toBeInTheDocument();
    });

    it('renders LOW, ELEVATED, and HIGH tier badges according to score bands', () => {
      const { rerender } = render(
        <RiskScoreCard
          riskAssessment={{
            ...mockRiskAssessment,
            composite_risk_score: 22.0,
            risk_tier: 'LOW',
          }}
          valuationStatus="COMPLETE"
          isLoading={false}
        />
      );
      expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent(/LOW RISK/i);

      rerender(
        <RiskScoreCard
          riskAssessment={{
            ...mockRiskAssessment,
            composite_risk_score: 62.0,
            risk_tier: 'ELEVATED',
          }}
          valuationStatus="COMPLETE"
          isLoading={false}
        />
      );
      expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent(/ELEVATED RISK/i);

      rerender(
        <RiskScoreCard
          riskAssessment={{
            ...mockRiskAssessment,
            composite_risk_score: 82.0,
            risk_tier: 'HIGH',
          }}
          valuationStatus="COMPLETE"
          isLoading={false}
        />
      );
      expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent(/HIGH RISK/i);
    });

    it('renders unavailable state when composite risk score is null for unpriced/empty portfolios', () => {
      render(
        <RiskScoreCard
          riskAssessment={{
            ...mockRiskAssessment,
            composite_risk_score: null,
            risk_tier: null,
            assessment_status: 'UNVALUED',
          }}
          valuationStatus="UNVALUED"
          isLoading={false}
        />
      );

      expect(screen.getByTestId('risk-score-unavailable')).toBeInTheDocument();
      expect(screen.getByText(/Composite Risk Score Unavailable/i)).toBeInTheDocument();
      expect(screen.queryByTestId('composite-risk-score')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Suite 2: Concentration & Diversification
  // -------------------------------------------------------------------------
  describe('ConcentrationCard', () => {
    it('renders top holding, top 3 weight, HHI, and ENH metrics', () => {
      render(
        <ConcentrationCard
          concentration={mockAnalyticsA.concentration}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('top-holding-metric')).toHaveTextContent('+28.50%');
      expect(screen.getByTestId('top-holding-metric')).toHaveTextContent('RELIANCE');
      expect(screen.getByTestId('top-3-concentration-metric')).toHaveTextContent('+68.20%');
      expect(screen.getByTestId('hhi-metric')).toHaveTextContent('0.2200');
      expect(screen.getByTestId('enh-metric')).toHaveTextContent('4.5');
      expect(screen.getByTestId('concentration-tier-badge')).toHaveTextContent(/MODERATE CONCENTRATION/i);
      expect(screen.getByText(/Non-Advisory Concentration Disclosure/i)).toBeInTheDocument();
    });

    it('preserves unavailable format (—) rather than fabricating zero for missing values', () => {
      render(
        <ConcentrationCard
          concentration={{
            top_holding_symbol: null,
            top_holding_weight_percent: null,
            top_3_concentration_percent: null,
            herfindahl_index: null,
            effective_holdings_count: null,
            concentration_tier: null,
          }}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('top-holding-metric')).toHaveTextContent('—');
      expect(screen.getByTestId('top-3-concentration-metric')).toHaveTextContent('—');
      expect(screen.getByTestId('hhi-metric')).toHaveTextContent('—');
      expect(screen.getByTestId('enh-metric')).toHaveTextContent('—');
      expect(screen.getByTestId('concentration-tier-badge')).toHaveTextContent('UNCLASSIFIED');
    });
  });

  // -------------------------------------------------------------------------
  // Suite 3: Sector Allocations Card
  // -------------------------------------------------------------------------
  describe('SectorAllocationsCard', () => {
    it('renders sector table rows with allocations, costs, and P/L metrics', () => {
      render(
        <SectorAllocationsCard
          sectors={mockSectors}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('sector-row-Energy')).toBeInTheDocument();
      expect(screen.getByTestId('sector-row-Energy')).toHaveTextContent('₹1,75,000.00');
      expect(screen.getByTestId('sector-row-Energy')).toHaveTextContent('+30.43%');
      expect(screen.getByTestId('sector-row-Technology')).toBeInTheDocument();
      expect(screen.getByTestId('sector-row-Technology')).toHaveTextContent('₹2,30,000.00');
      expect(screen.getByTestId('sector-row-Technology')).toHaveTextContent('+40.00%');
    });

    it('displays empty message when no sector allocations exist', () => {
      render(
        <SectorAllocationsCard
          sectors={[]}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('no-sectors-message')).toBeInTheDocument();
      expect(screen.getByText(/No sector allocation data available/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Suite 4: Data Completeness & Price Quality
  // -------------------------------------------------------------------------
  describe('DataCompletenessCard', () => {
    it('renders complete coverage ratio and indicators', () => {
      render(
        <DataCompletenessCard
          completeness={mockAnalyticsA.completeness}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('completeness-ratio-metric')).toHaveTextContent('+100.00%');
      expect(screen.getByText('100% PRICING COVERAGE')).toBeInTheDocument();
      expect(screen.getByTestId('simulated-price-disclosure')).toBeInTheDocument();
      expect(screen.queryByTestId('stale-price-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('risk-unpriced-positions')).not.toBeInTheDocument();
    });

    it('renders stale-price warning and unpriced positions table when partial', () => {
      const partialCompleteness = {
        is_complete: false,
        completeness_ratio: 0.8,
        total_holdings_count: 5,
        priced_holdings_count: 4,
        unpriced_holdings_count: 1,
        has_stale_prices: true,
        has_simulated_prices: true,
        unpriced_positions: [
          {
            holding_id: 'h-unpriced',
            symbol: 'WIPRO',
            exchange: 'NSE',
            quantity: 50,
            cost_basis: 25000,
            pricing_status: 'UNAVAILABLE',
            price_explanation: 'Provider quote rate limit reached',
          },
        ],
      };

      render(
        <DataCompletenessCard
          completeness={partialCompleteness}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('completeness-ratio-metric')).toHaveTextContent('+80.00%');
      expect(screen.getByText('PARTIAL COVERAGE')).toBeInTheDocument();
      expect(screen.getByTestId('stale-price-warning')).toBeInTheDocument();
      expect(screen.getByTestId('risk-unpriced-positions')).toBeInTheDocument();
      expect(screen.getByText('WIPRO')).toBeInTheDocument();
      expect(screen.getByText(/Provider quote rate limit reached/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Suite 5: Historical Risk & Benchmark Metrics
  // -------------------------------------------------------------------------
  describe('HistoricalRiskCard', () => {
    it('renders INSUFFICIENT_HISTORY status banner and unavailable indicators without fabricating charts', () => {
      render(
        <HistoricalRiskCard
          historicalRisk={mockHistoricalRisk}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('historical-data-status')).toHaveTextContent('STATUS: INSUFFICIENT_HISTORY');
      expect(screen.getByTestId('metric-volatility')).toHaveTextContent('Unavailable');
      expect(screen.getByTestId('metric-drawdown')).toHaveTextContent('Unavailable');
      expect(screen.getByTestId('metric-beta')).toHaveTextContent('Unavailable');
      expect(screen.getByTestId('metric-relative-return')).toHaveTextContent('Unavailable');
      expect(screen.getByTestId('insufficient-history-banner')).toBeInTheDocument();
      expect(screen.getByText(/Historical Integrity & Transparency Guarantee/i)).toBeInTheDocument();
    });

    it('renders valid historical metrics when complete series are provided', () => {
      const completeHistory: HistoricalRiskMetrics = {
        annualized_volatility_percent: 18.5,
        maximum_drawdown_percent: -12.4,
        beta: 1.05,
        benchmark_relative_return_percent: 3.2,
        benchmark_symbol: 'NIFTY 50',
        data_status: 'COMPLETE',
        disclaimer: 'Verified historical price series.',
      };

      render(
        <HistoricalRiskCard
          historicalRisk={completeHistory}
          isLoading={false}
        />
      );

      expect(screen.getByTestId('historical-data-status')).toHaveTextContent('STATUS: COMPLETE');
      expect(screen.getByTestId('metric-volatility')).toHaveTextContent('+18.50%');
      expect(screen.getByTestId('metric-drawdown')).toHaveTextContent('-12.40%');
      expect(screen.getByTestId('metric-beta')).toHaveTextContent('1.05');
      expect(screen.getByTestId('metric-relative-return')).toHaveTextContent('+3.20%');
      expect(screen.queryByTestId('insufficient-history-banner')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Suite 6: Risk Insights Section
  // -------------------------------------------------------------------------
  describe('RiskInsightsSection', () => {
    it('renders deterministic risk observation cards with badges, descriptions, and evidence', () => {
      render(
        <RiskInsightsSection
          insightsResponse={mockInsights}
          isLoading={false}
          error={null}
        />
      );

      expect(screen.getByTestId('risk-insight-card-ins-risk-1')).toBeInTheDocument();
      expect(screen.getByText('Moderate Portfolio Risk Detected (Score: 42.50/100)')).toBeInTheDocument();
      expect(screen.getByText('Single-stock concentration in RELIANCE contributes 52.00 risk points.')).toBeInTheDocument();
      expect(screen.getByText('WARNING')).toBeInTheDocument();
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
      expect(screen.getByText('Provenance: DETERMINISTIC_RISK_ENGINE')).toBeInTheDocument();
    });

    it('renders error banner when insights computation fails', () => {
      render(
        <RiskInsightsSection
          insightsResponse={null}
          isLoading={false}
          error="Failed to evaluate deterministic rules"
        />
      );

      expect(screen.getByTestId('risk-insights-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to evaluate deterministic rules/i)).toBeInTheDocument();
    });

    it('renders empty message when no insights are triggered', () => {
      render(
        <RiskInsightsSection
          insightsResponse={{
            ...mockInsights,
            insights: [],
            total_insights: 0,
          }}
          isLoading={false}
          error={null}
        />
      );

      expect(screen.getByTestId('no-risk-insights')).toBeInTheDocument();
      expect(screen.getByText(/No risk observations triggered/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Suite 7: Integration, Portfolio Switching & Asynchronous Race Protection
  // -------------------------------------------------------------------------
  describe('RiskExposurePanel Integration & Race Conditions', () => {
    it('renders all 6 risk panels within the tabpanel container', async () => {
      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('risk-exposure-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('risk-score-overview')).toBeInTheDocument();
      expect(screen.getByTestId('concentration-metrics-card')).toBeInTheDocument();
      expect(screen.getByTestId('sector-allocations-table')).toBeInTheDocument();
      expect(screen.getByTestId('data-completeness-card')).toBeInTheDocument();
      expect(screen.getByTestId('historical-risk-card')).toBeInTheDocument();
      expect(screen.getByTestId('risk-insights-section')).toBeInTheDocument();
    });

    it('reloads analytics and insights when clicking refresh button', async () => {
      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('risk-exposure-panel')).toBeInTheDocument();
      });

      const refreshBtn = screen.getByTestId('refresh-risk-btn');
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(analyticsApi.fetchPortfolioAnalytics).toHaveBeenCalledTimes(2);
        expect(analyticsApi.fetchPortfolioInsights).toHaveBeenCalledTimes(2);
      });
    });

    it('displays error banner if risk analytics fails to load', async () => {
      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockRejectedValueOnce(
        new Error('Database connectivity timed out')
      );

      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-error-banner')).toBeInTheDocument();
      });

      expect(screen.getByText(/Database connectivity timed out/i)).toBeInTheDocument();
    });

    it('delayed analytics from Portfolio A cannot overwrite Portfolio B data', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolioA, mockPortfolioB]);

      let resolveAnalyticsA!: (value: PortfolioAnalyticsResponse) => void;
      const delayedAnalyticsA = new Promise<PortfolioAnalyticsResponse>((resolve) => {
        resolveAnalyticsA = resolve;
      });

      const mockAnalyticsB: PortfolioAnalyticsResponse = {
        ...mockAnalyticsA,
        portfolio_id: 'demo-portfolio-2',
        portfolio_name: 'Aggressive Tech Growth',
        risk_assessment: {
          ...mockRiskAssessment,
          composite_risk_score: 88.0,
          risk_tier: 'HIGH',
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
          <RiskTestHarness />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('test-portfolio-selector')).toHaveValue('demo-portfolio-1');
      });

      // Switch to Portfolio B before Portfolio A resolves
      const selector = screen.getByTestId('test-portfolio-selector');
      fireEvent.change(selector, { target: { value: 'demo-portfolio-2' } });

      // Portfolio B resolves and renders HIGH risk
      await waitFor(() => {
        expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('88.00');
        expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent(/HIGH RISK/i);
      });

      // Now resolve delayed analytics A with old moderate score
      resolveAnalyticsA({
        ...mockAnalyticsA,
        risk_assessment: {
          ...mockRiskAssessment,
          composite_risk_score: 30.0,
        },
      });

      // Must remain Portfolio B (88.00) and NOT be overwritten by 30.00
      await waitFor(() => {
        expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('88.00');
      });
    });

    it('an older refresh cannot overwrite a newer refresh for the same portfolio', async () => {
      let callCount = 0;
      let resolveFirstRefresh!: (value: PortfolioAnalyticsResponse) => void;
      const delayedFirstRefresh = new Promise<PortfolioAnalyticsResponse>((resolve) => {
        resolveFirstRefresh = resolve;
      });

      const newerRefreshedAnalytics: PortfolioAnalyticsResponse = {
        ...mockAnalyticsA,
        risk_assessment: {
          ...mockRiskAssessment,
          composite_risk_score: 65.5,
          risk_tier: 'ELEVATED',
        },
      };

      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockImplementation(() => {
        callCount++;
        if (callCount === 2) {
          // Slow first refresh
          return delayedFirstRefresh;
        }
        if (callCount === 3) {
          // Fast second refresh
          return Promise.resolve(newerRefreshedAnalytics);
        }
        return Promise.resolve(mockAnalyticsA);
      });

      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('42.50');
      });

      const refreshBtn = screen.getByTestId('refresh-risk-btn');

      // Click refresh 1 (starts slow call)
      fireEvent.click(refreshBtn);

      // Click refresh 2 (starts and completes fast call)
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('65.50');
      });

      // Now resolve older refresh with obsolete 15.00 score
      resolveFirstRefresh({
        ...mockAnalyticsA,
        risk_assessment: {
          ...mockRiskAssessment,
          composite_risk_score: 15.0,
          risk_tier: 'LOW',
        },
      });

      // Must remain newer value (65.50) and NOT revert to 15.00
      await waitFor(() => {
        expect(screen.getByTestId('composite-risk-score')).toHaveTextContent('65.50');
      });
    });

    it('renders empty state with seed demo button when no portfolios exist', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([]);

      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('risk-panel-empty')).toBeInTheDocument();
      });

      expect(screen.getByText(/No Portfolio Available for Risk Analysis/i)).toBeInTheDocument();
      expect(screen.getByTestId('seed-demo-btn')).toBeInTheDocument();
    });

    it('strictly contains no buy/sell execution controls', async () => {
      render(
        <PortfolioProvider>
          <RiskExposurePanel />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('risk-exposure-panel')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /buy|sell|trade|order|execute/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('textbox', { name: /shares|quantity|limit price/i })).not.toBeInTheDocument();
      expect(screen.queryByText(/^Buy$/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/^Sell$/i)).not.toBeInTheDocument();
    });
  });
});
