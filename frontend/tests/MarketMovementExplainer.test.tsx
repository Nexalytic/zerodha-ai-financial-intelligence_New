import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MarketMovementExplainer } from '../src/components/market/MarketMovementExplainer';
import { StockInspectorCard } from '../src/components/market/StockInspectorCard';
import { MarketNewsSection } from '../src/components/market/MarketNewsSection';
import { AIExplanationSection } from '../src/components/market/AIExplanationSection';
import { PortfolioProvider, usePortfolio } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import * as marketDataApi from '../src/api/marketData';
import * as newsApi from '../src/api/news';
import * as aiReasoningApi from '../src/api/aiReasoning';
import { PortfolioResponse, PortfolioDetailResponse } from '../src/types/portfolio';
import { Quote, BatchQuotesResponse, NewsResponse, NewsArticle } from '../src/types/marketData';
import { AIInsightReport } from '../src/types/aiReasoning';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/marketData');
vi.mock('../src/api/news');
vi.mock('../src/api/aiReasoning');

describe('Phase 07 Step 7.4: Market Movement Explainer', () => {
  const mockPortfolioA: PortfolioResponse = {
    id: 'demo-portfolio-1',
    name: 'Demo Indian Bluechip Portfolio',
    description: 'Benchmark portfolio',
    is_sample: true,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 3,
  };

  const mockPortfolioDetailA: PortfolioDetailResponse = {
    ...mockPortfolioA,
    holdings: [
      {
        id: 'h-1',
        portfolio_id: 'demo-portfolio-1',
        symbol: 'RELIANCE',
        exchange: 'NSE',
        quantity: 50,
        average_buy_price: 2400.0,
        sector: 'Energy',
        asset_class: 'EQUITY',
        created_at: '2026-10-10T00:00:00Z',
        updated_at: '2026-10-10T00:00:00Z',
      },
      {
        id: 'h-2',
        portfolio_id: 'demo-portfolio-1',
        symbol: 'TCS',
        exchange: 'NSE',
        quantity: 30,
        average_buy_price: 3500.0,
        sector: 'Technology',
        asset_class: 'EQUITY',
        created_at: '2026-10-10T00:00:00Z',
        updated_at: '2026-10-10T00:00:00Z',
      },
      {
        id: 'h-3',
        portfolio_id: 'demo-portfolio-1',
        symbol: 'INFY',
        exchange: 'NSE',
        quantity: 40,
        average_buy_price: 1450.0,
        sector: 'Technology',
        asset_class: 'EQUITY',
        created_at: '2026-10-10T00:00:00Z',
        updated_at: '2026-10-10T00:00:00Z',
      },
    ],
  };

  const mockPortfolioB: PortfolioResponse = {
    id: 'demo-portfolio-2',
    name: 'Growth & Smallcap Portfolio',
    description: 'Second test portfolio',
    is_sample: false,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 1,
  };

  const mockPortfolioDetailB: PortfolioDetailResponse = {
    ...mockPortfolioB,
    holdings: [
      {
        id: 'h-4',
        portfolio_id: 'demo-portfolio-2',
        symbol: 'HDFCBANK',
        exchange: 'NSE',
        quantity: 100,
        average_buy_price: 1600.0,
        sector: 'Financial Services',
        asset_class: 'EQUITY',
        created_at: '2026-10-10T00:00:00Z',
        updated_at: '2026-10-10T00:00:00Z',
      },
    ],
  };

  const mockQuotesMap: Record<string, Quote> = {
    RELIANCE: {
      symbol: 'RELIANCE',
      exchange: 'NSE',
      current_price: 2550.0,
      change: 35.5,
      change_percent: 1.41,
      status: 'AVAILABLE',
      cache_hit: true,
      ttl_remaining_seconds: 45.2,
      is_stale: false,
      is_simulated: true,
      generated_at: '2026-10-11T07:00:00Z',
      market_as_of: null,
      source: 'SIMULATED_FEED',
      disclaimer: 'Simulated quote',
      explanation: null,
    },
    TCS: {
      symbol: 'TCS',
      exchange: 'NSE',
      current_price: 3620.0,
      change: -15.0,
      change_percent: -0.41,
      status: 'AVAILABLE',
      cache_hit: false,
      ttl_remaining_seconds: 60.0,
      is_stale: false,
      is_simulated: true,
      generated_at: '2026-10-11T07:00:00Z',
      market_as_of: null,
      source: 'SIMULATED_FEED',
      disclaimer: 'Simulated quote',
      explanation: null,
    },
    INFY: {
      symbol: 'INFY',
      exchange: 'NSE',
      current_price: null,
      change: null,
      change_percent: null,
      status: 'UNAVAILABLE',
      cache_hit: false,
      ttl_remaining_seconds: 0,
      is_stale: false,
      is_simulated: false,
      generated_at: '2026-10-11T07:00:00Z',
      market_as_of: null,
      source: 'EXTERNAL_FEED',
      disclaimer: 'External feed quote',
      explanation: 'Exchange connection rate limit exceeded. Value not fabricated.',
    },
  };

  const mockBatchQuotesResponse: BatchQuotesResponse = {
    quotes: mockQuotesMap,
    total_symbols: 3,
    cache_hits_count: 1,
    cache_misses_count: 2,
    fetched_at: '2026-10-11T07:00:00Z',
  };

  const mockNewsArticles: NewsArticle[] = [
    {
      id: 'news-1',
      title: 'Reliance Industries Expands Renewable Energy Pipeline',
      summary: 'Strategic green hydrogen and solar gigafactory milestones announced.',
      source: 'Financial Times India',
      published_at: '2026-10-11T06:30:00Z',
      sentiment: 'POSITIVE',
      related_symbols: ['RELIANCE'],
      is_simulated: true,
      disclaimer: 'Simulated educational news headline.',
    },
    {
      id: 'news-2',
      title: 'IT Sector Faces Near-Term Margin Pressure Amid Extended Deal Cycles',
      summary: 'Tier-1 Indian IT exporters navigate cautious discretionary tech spend.',
      source: 'Economic Market Wire',
      published_at: '2026-10-11T05:45:00Z',
      sentiment: 'NEGATIVE',
      related_symbols: ['TCS', 'INFY'],
      is_simulated: true,
      disclaimer: 'Simulated educational news headline.',
    },
  ];

  const mockNewsResponse: NewsResponse = {
    articles: mockNewsArticles,
    total_count: 2,
    fetched_at: '2026-10-11T07:00:00Z',
    cache_hit: true,
    is_simulated: true,
    disclaimer: 'Simulated financial news for market analytics demonstration.',
  };

  const mockAIInsightReport: AIInsightReport = {
    report_id: 'rep-ai-1',
    portfolio_id: 'demo-portfolio-1',
    generated_at: '2026-10-11T07:05:00Z',
    provider_name: 'DETERMINISTIC_DEMO_REASONER',
    model_id: 'deterministic-demo-v1',
    is_simulated: true,
    executive_summary:
      'Portfolio experienced mild positive momentum led by heavy-weight energy holdings, offsetting mild softness in IT services.',
    key_drivers: [
      {
        driver_id: 'drv-1',
        driver_type: 'SECTOR',
        title: 'Energy Sector Rally',
        statement: 'RELIANCE gained +1.41% following green energy infrastructure updates.',
        supporting_metric_key: 'sector_momentum',
        supporting_metric_value: 1.41,
        source_reference: 'NSE_TICKER_FEED',
        is_grounded: true,
      },
      {
        driver_id: 'drv-2',
        driver_type: 'PERFORMANCE',
        title: 'IT Multiple Contraction',
        statement: 'TCS contracted -0.41% on sector-wide margin consolidation.',
        supporting_metric_key: 'change_percent',
        supporting_metric_value: -0.41,
        source_reference: 'NSE_TICKER_FEED',
        is_grounded: true,
      },
    ],
    risk_alerts: [
      {
        alert_id: 'alt-1',
        severity: 'HIGH',
        category: 'CONCENTRATION',
        headline: 'Energy & IT Concentration Alert',
        explanation: 'Sector concentration remains tilted towards large-cap energy and IT.',
        evidence_reference: 'PORTFOLIO_TELEMETRY',
        actionable_mitigation: null,
      },
    ],
    confidence: {
      score: 0.88,
      level: 'HIGH',
      calibration_limitation:
        'Synthesis is strictly grounded in available quote telemetry and structured news items. No forward guarantees.',
      data_quality_discount: 0.05,
      staleness_discount: 0.0,
    },
    review_cards: [],
    uncertainty_and_gaps: [],
    disclaimers: [
      'Educational AI insights only. Not SEBI-registered investment advice.',
    ],
    review_status: 'VERIFIED',
    grounding_report: {
      total_claims_checked: 2,
      passed_count: 2,
      flagged_count: 0,
      rejected_count: 0,
      findings: [
        {
          check_name: 'price_verification',
          target_id: 'drv-1',
          status: 'PASSED',
          reason: 'All cited percentage changes match verified quotes.',
        },
      ],
      is_acceptable: true,
    },
  };

  const MarketTestHarness: React.FC = () => {
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
        <MarketMovementExplainer />
      </div>
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([
      mockPortfolioA,
      mockPortfolioB,
    ]);
    vi.mocked(portfoliosApi.fetchPortfolio).mockResolvedValue(mockPortfolioDetailA);
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue(mockBatchQuotesResponse);
    vi.mocked(marketDataApi.fetchQuote).mockResolvedValue(mockQuotesMap.RELIANCE);
    vi.mocked(newsApi.fetchNews).mockResolvedValue(mockNewsResponse);
    vi.mocked(aiReasoningApi.generateAIPortfolioInsights).mockResolvedValue(mockAIInsightReport);
  });

  it('renders market movement explainer hub with quote table and overview', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    // Header and description
    expect(await screen.findByText('Market Movement Explainer')).toBeInTheDocument();
    expect(
      screen.getByText(/Simulated price movements, ticker inspector, financial sentiment news/i)
    ).toBeInTheDocument();

    // Verify Market Overview Card
    expect(screen.getByTestId('market-overview-card')).toBeInTheDocument();
    expect(screen.getByText('Market Quote Overview & Movements')).toBeInTheDocument();

    // Available quote rows
    await waitFor(() => {
      expect(screen.getByTestId('quote-row-RELIANCE')).toBeInTheDocument();
      expect(screen.getByTestId('quote-row-TCS')).toBeInTheDocument();
      expect(screen.getByTestId('quote-row-INFY')).toBeInTheDocument();
    });

    // Verify formatted values in overview
    expect(screen.getByTestId('quote-price-RELIANCE')).toHaveTextContent('₹2,550.00');
    expect(screen.getByTestId('quote-price-TCS')).toHaveTextContent('₹3,620.00');
    expect(screen.getByTestId('quote-price-INFY')).toHaveTextContent('—');
    expect(screen.getByTestId('quote-status-INFY')).toHaveTextContent('UNAVAILABLE');

    // Cache hit badge on RELIANCE
    expect(screen.getByTestId('quote-cache-RELIANCE')).toHaveTextContent('HIT');
    expect(screen.getByTestId('quote-cache-TCS')).toHaveTextContent('MISS');
  });

  it('distinguishes simulated demonstration feed with prominent disclaimer badges', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('simulated-feed-banner')).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Demonstration market feeds are active/i)
    ).toBeInTheDocument();

    // Row-level badges
    const relRow = screen.getByTestId('quote-row-RELIANCE');
    expect(relRow).toHaveTextContent('SIMULATED');
  });

  it('handles emergency stale cache quotes with warning indicators', async () => {
    const staleQuote: Quote = {
      ...mockQuotesMap.RELIANCE,
      symbol: 'STALE_STOCK',
      is_stale: true,
      status: 'AVAILABLE',
    };
    vi.mocked(marketDataApi.fetchBatchQuotes).mockResolvedValue({
      ...mockBatchQuotesResponse,
      quotes: { STALE_STOCK: staleQuote },
    });
    vi.mocked(marketDataApi.fetchQuote).mockResolvedValue(staleQuote);

    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('quote-row-STALE_STOCK')).toBeInTheDocument();
    });
    expect(screen.getByTestId('quote-status-STALE_STOCK')).toHaveTextContent('STALE');
    expect(screen.getByTestId('inspector-stale-warning')).toBeInTheDocument();
    expect(
      screen.getByText(/This quote was served from the emergency cache fallback/i)
    ).toBeInTheDocument();
  });

  it('renders single stock inspector with net change, percent change, and latency metrics', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('stock-inspector-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('inspector-price')).toHaveTextContent('₹2,550.00');
    expect(screen.getByTestId('inspector-change')).toHaveTextContent('₹35.50');
    expect(screen.getByTestId('inspector-change-percent')).toHaveTextContent('1.41%');
    expect(screen.getByTestId('inspector-status')).toHaveTextContent('CACHE HIT');
    expect(screen.getByTestId('inspector-source')).toHaveTextContent('SIMULATED_FEED');
  });

  it('handles unavailable quotes in inspector without fabricating zero prices', async () => {
    render(
      <StockInspectorCard
        quote={mockQuotesMap.INFY}
        symbols={['RELIANCE', 'TCS', 'INFY']}
        selectedSymbol="INFY"
        selectedExchange="NSE"
        onSelectSymbol={vi.fn()}
        onSelectExchange={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByTestId('inspector-unavailable-notice')).toBeInTheDocument();
    expect(screen.getByText('Quote Unavailable for INFY (NSE)')).toBeInTheDocument();
    expect(
      screen.getByText(/Exchange connection rate limit exceeded\. Value not fabricated\./i)
    ).toBeInTheDocument();
    expect(screen.queryByTestId('inspector-price')).not.toBeInTheDocument();
  });

  it('allows switching symbol and exchange in the inspector', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('symbol-select')).toBeInTheDocument();
    });

    // Select TCS
    fireEvent.change(screen.getByTestId('symbol-select'), {
      target: { value: 'TCS' },
    });

    await waitFor(() => {
      expect(marketDataApi.fetchQuote).toHaveBeenCalledWith('TCS', 'NSE');
    });

    // Switch exchange to BSE
    fireEvent.change(screen.getByTestId('exchange-select'), {
      target: { value: 'BSE' },
    });

    await waitFor(() => {
      expect(marketDataApi.fetchQuote).toHaveBeenCalledWith('TCS', 'BSE');
    });
  });

  it('renders market news feed with sentiment badges, symbol tags, and source provenance', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('market-news-section')).toBeInTheDocument();
      expect(screen.getByTestId('news-article-card-news-1')).toBeInTheDocument();
      expect(screen.getByTestId('news-article-card-news-2')).toBeInTheDocument();
    });

    // Sentiment badges
    expect(screen.getByTestId('news-sentiment-news-1')).toHaveTextContent('POSITIVE');
    expect(screen.getByTestId('news-sentiment-news-2')).toHaveTextContent('NEGATIVE');

    // Sources
    expect(screen.getByText('Source: Financial Times India')).toBeInTheDocument();
    expect(screen.getByText('Source: Economic Market Wire')).toBeInTheDocument();

    // Related symbol tags
    expect(screen.getByRole('button', { name: 'RELIANCE' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'TCS' })).toBeInTheDocument();
  });

  it('filters news feed when toggling to single symbol news and allows tag-clicking', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-symbol-news-btn')).toBeInTheDocument();
    });

    // Switch filter to selected symbol news
    fireEvent.click(screen.getByTestId('filter-symbol-news-btn'));

    await waitFor(() => {
      expect(newsApi.fetchNews).toHaveBeenCalledWith(['RELIANCE'], 10);
    });

    // Clicking related symbol tag TCS on news item switches the selected inspector symbol
    fireEvent.click(screen.getByRole('button', { name: 'TCS' }));

    await waitFor(() => {
      expect(marketDataApi.fetchQuote).toHaveBeenCalledWith('TCS', 'NSE');
    });
  });

  it('handles empty news feed gracefully with informative message', async () => {
    const emptyResponse: NewsResponse = {
      articles: [],
      total_count: 0,
      fetched_at: '2026-10-11T07:00:00Z',
      cache_hit: true,
      is_simulated: true,
      disclaimer: 'None',
    };

    render(
      <MarketNewsSection
        newsResponse={emptyResponse}
        selectedSymbol="TCS"
        isFilteredBySymbol={true}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByTestId('no-news-message')).toBeInTheDocument();
    expect(screen.getByText(/No news articles found for TCS/i)).toBeInTheDocument();
  });

  it('handles news API fetch failure gracefully', async () => {
    render(
      <MarketNewsSection
        newsResponse={null}
        selectedSymbol="RELIANCE"
        isFilteredBySymbol={false}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error="Network timeout connecting to news provider"
      />
    );

    expect(screen.getByTestId('news-error-banner')).toBeInTheDocument();
    expect(
      screen.getByText('Network timeout connecting to news provider')
    ).toBeInTheDocument();
  });

  it('generates fact-grounded AI movement explanation and displays verified audit results', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('ai-explanation-section')).toBeInTheDocument();
    });

    const generateBtn = screen.getByTestId('generate-ai-explanation-btn');
    expect(generateBtn).toBeInTheDocument();
    fireEvent.click(generateBtn);

    // Verify AI reasoning API triggered with active portfolio ID
    await waitFor(() => {
      expect(aiReasoningApi.generateAIPortfolioInsights).toHaveBeenCalledWith(
        'demo-portfolio-1',
        {
          include_news: true,
          news_limit: 10,
        }
      );
    });

    // AI Insight content rendered
    await waitFor(() => {
      expect(screen.getByTestId('ai-report-content')).toBeInTheDocument();
    });

    expect(screen.getByTestId('ai-summary')).toHaveTextContent(
      'Portfolio experienced mild positive momentum led by heavy-weight energy holdings'
    );
    expect(screen.getByTestId('ai-driver-0')).toHaveTextContent(
      'RELIANCE gained +1.41% following green energy infrastructure updates.'
    );
    expect(screen.getByTestId('ai-risk-alert-0')).toHaveTextContent(
      'Sector concentration remains tilted towards large-cap energy and IT.'
    );

    // Fact grounding verified banner
    expect(screen.getByTestId('grounding-verified-banner')).toBeInTheDocument();
    expect(
      screen.getByText(/Grounding Guardrail Verified \(2\/2 claims confirmed\)/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId('grounding-note-0')).toHaveTextContent(
      'All cited percentage changes match verified quotes.'
    );

    // Model and provider disclosure
    expect(screen.getByText(/Provider: DETERMINISTIC_DEMO_REASONER/i)).toBeInTheDocument();
    expect(screen.getByText(/Model: deterministic-demo-v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Simulated Demo Reasoner/i)).toBeInTheDocument();

    // Portfolio-level synthesis scope disclaimer
    expect(screen.getByTestId('ai-scope-disclaimer')).toBeInTheDocument();
    expect(
      screen.getByText(/Portfolio-level AI synthesis scope: grounded in structural weights/i)
    ).toBeInTheDocument();
  });

  it('displays prominent rejection banner when AI output fails fact-grounding guardrails', async () => {
    const unverifiedReport: AIInsightReport = {
      ...mockAIInsightReport,
      review_status: 'REJECTED',
      grounding_report: {
        total_claims_checked: 3,
        passed_count: 1,
        flagged_count: 2,
        rejected_count: 0,
        findings: [
          {
            check_name: 'dividend_yield_check',
            target_id: 'drv-unverified-1',
            status: 'FLAGGED',
            reason: 'Claimed 15% dividend yield unsupported by company telemetry.',
          },
          {
            check_name: 'acquisition_rumour_check',
            target_id: 'drv-unverified-2',
            status: 'FLAGGED',
            reason: 'Attributed rally to unverified acquisition rumour.',
          },
        ],
        is_acceptable: false,
      },
    };

    render(
      <AIExplanationSection
        aiReport={unverifiedReport}
        portfolioId="demo-portfolio-1"
        portfolioName="Demo Indian Bluechip Portfolio"
        isGenerating={false}
        error={null}
        onGenerate={vi.fn()}
      />
    );

    expect(screen.getByTestId('grounding-rejected-banner')).toBeInTheDocument();
    expect(
      screen.getByText(/AI Output Rejected by Grounding Guardrails/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/2 of 3 statements flagged as ungrounded\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/Claimed 15% dividend yield unsupported by company telemetry\./i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Attributed rally to unverified acquisition rumour\./i)
    ).toBeInTheDocument();
  });

  it('handles AI provider failure gracefully with error banner and retry option', async () => {
    const handleRetry = vi.fn();
    render(
      <AIExplanationSection
        aiReport={null}
        portfolioId="demo-portfolio-1"
        portfolioName="Demo Indian Bluechip Portfolio"
        isGenerating={false}
        error="Groq API credit balance insufficient or rate limit triggered"
        onGenerate={handleRetry}
      />
    );

    expect(screen.getByTestId('ai-error-banner')).toBeInTheDocument();
    expect(
      screen.getByText('Groq API credit balance insufficient or rate limit triggered')
    ).toBeInTheDocument();
    expect(screen.getByTestId('retry-ai-btn')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('retry-ai-btn'));
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('isolates AI report state and cancels late responses when switching portfolios', async () => {
    let resolveFirstAI: any = null;
    const pendingFirstAIPromise = new Promise<AIInsightReport>((resolve) => {
      resolveFirstAI = resolve;
    });

    vi.mocked(aiReasoningApi.generateAIPortfolioInsights).mockReturnValueOnce(
      pendingFirstAIPromise
    );

    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('generate-ai-explanation-btn')).toBeInTheDocument();
    });

    // Start generation for Portfolio A
    fireEvent.click(screen.getByTestId('generate-ai-explanation-btn'));
    expect(screen.getByText(/Synthesizing Movements\.\.\./i)).toBeInTheDocument();

    // Now user switches to Portfolio B while Portfolio A request is in-flight
    vi.mocked(portfoliosApi.fetchPortfolio).mockResolvedValue(mockPortfolioDetailB);
    fireEvent.change(screen.getByTestId('test-portfolio-selector'), {
      target: { value: 'demo-portfolio-2' },
    });

    // Verify AI state immediately cleared
    await waitFor(() => {
      expect(screen.getByTestId('generate-ai-explanation-btn')).toBeInTheDocument();
      expect(
        screen.queryByText(/Synthesizing Movements\.\.\./i)
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId('ai-report-content')).not.toBeInTheDocument();
    });

    // Now resolve the late response from Portfolio A
    if (resolveFirstAI) {
      resolveFirstAI(mockAIInsightReport);
    }

    // Give microtasks time to execute
    await new Promise((r) => setTimeout(r, 20));

    // The late response from Portfolio A MUST NOT render under Portfolio B
    expect(screen.queryByTestId('ai-report-content')).not.toBeInTheDocument();
  });

  it('protects against ticker selection race conditions', async () => {
    let resolveQuoteA: any = null;
    const slowQuotePromise = new Promise<Quote>((resolve) => {
      resolveQuoteA = resolve;
    });

    const fastQuote: Quote = {
      ...mockQuotesMap.TCS,
      symbol: 'TCS',
      current_price: 3620.0,
    };

    // Return slow promise on first call (RELIANCE), fast on second (TCS)
    vi.mocked(marketDataApi.fetchQuote)
      .mockReturnValueOnce(slowQuotePromise)
      .mockResolvedValueOnce(fastQuote);

    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('symbol-select')).toBeInTheDocument();
    });

    // Switch to TCS immediately
    fireEvent.change(screen.getByTestId('symbol-select'), {
      target: { value: 'TCS' },
    });

    // Wait for fast response (TCS) to arrive
    await waitFor(() => {
      expect(screen.getByTestId('inspector-price')).toHaveTextContent('₹3,620.00');
    });

    // Now resolve slow quote for RELIANCE
    if (resolveQuoteA) {
      resolveQuoteA(mockQuotesMap.RELIANCE);
    }

    await new Promise((r) => setTimeout(r, 20));

    // Ticker inspector must still show TCS price (₹3,620.00), not overwritten by slow RELIANCE (₹2,550.00)
    expect(screen.getByTestId('inspector-price')).toHaveTextContent('₹3,620.00');
  });

  it('strictly contains zero trading execution controls', async () => {
    render(
      <PortfolioProvider>
        <MarketTestHarness />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('market-movement-explainer')).toBeInTheDocument();
    });

    // Verify absence of trading buttons and forms
    expect(screen.queryByRole('button', { name: /^buy$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^sell$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /trade/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /execute/i })).not.toBeInTheDocument();

    // Verify absence of trading input fields
    expect(screen.queryByLabelText(/order type/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/limit price/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/quantity to buy/i)).not.toBeInTheDocument();

    // Verify non-trading disclosures are present
    expect(screen.getByTestId('market-explainer-disclaimer')).toBeInTheDocument();
    expect(
      screen.getByText(/Educational market intelligence and attribution analysis only/i)
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/This platform is strictly an educational financial analytics engine/i).length
    ).toBeGreaterThanOrEqual(1);
  });
});
