import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PortfolioOverviewCard } from '../src/components/portfolio/PortfolioOverviewCard';
import { HoldingsTable } from '../src/components/portfolio/HoldingsTable';
import { MarketNewsSection } from '../src/components/market/MarketNewsSection';
import { AIInsightsSection } from '../src/components/portfolio/AIInsightsSection';

import { PortfolioResponse } from '../src/types/portfolio';
import { HoldingAnalyticsDetail } from '../src/types/analytics';
import { NewsResponse } from '../src/types/marketData';
import { AIInsightReport } from '../src/types/aiReasoning';


describe('Phase 08 Step 8.2: Frontend Adversarial Rendering & XSS Defense', () => {
  // =========================================================================
  // 1. Portfolio Overview Rendering with Malicious Payloads
  // =========================================================================
  it('renders malicious scripts in portfolio names and descriptions as inert text without executing', () => {
    const xssName = "<script>alert('xss-portfolio-name')</script>";
    const xssDesc = '<img src=x onerror=alert("xss-desc")>';

    const maliciousPortfolio: PortfolioResponse = {
      id: 'port-malicious-01',
      name: xssName,
      description: xssDesc,
      is_sample: false,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 1,
    };

    const { container } = render(
      <PortfolioOverviewCard
        portfolio={maliciousPortfolio}
        analytics={null}
        isLoading={false}
      />
    );

    // 1. Assert string is rendered verbatim as inert text
    expect(screen.getByText(xssName)).toBeInTheDocument();
    expect(container.textContent).toContain(xssName);
    expect(container.textContent).toContain(xssDesc);

    // 2. Assert no executable <script> DOM element was created
    expect(container.querySelector('script')).toBeNull();
    expect(document.querySelector('script')).toBeNull();

    // 3. Assert no <img> element with an onerror attribute was created
    const imgElement = container.querySelector('img');
    if (imgElement) {
      expect(imgElement.getAttribute('onerror')).toBeNull();
    }
  });

  // =========================================================================
  // 2. Holdings Table Rendering with Hostile Sectors and Payloads
  // =========================================================================
  it('renders hostile HTML tags in holding sector fields as text without creating elements', () => {
    const xssSector = '<svg onload=alert("xss-sector")>';

    const maliciousHoldings: HoldingAnalyticsDetail[] = [
      {
        holding_id: 'hold-xss-01',
        symbol: 'TCS',
        exchange: 'NSE',
        quantity: 10,
        average_buy_price: '3920.00',
        current_price: '3920.00',
        cost_basis: '39200.00',
        market_value: '39200.00',
        unrealized_pnl: '0.00',
        unrealized_pnl_percent: '0.00',
        market_value_weight_percent: '100.00',
        cost_basis_weight_percent: '100.00',
        pricing_status: 'AVAILABLE',
        is_stale: false,
        is_simulated: true,
        sector: xssSector,
        asset_class: 'EQUITY',
      },
    ];

    const { container } = render(
      <HoldingsTable holdings={maliciousHoldings} isLoading={false} />
    );

    // 1. Text is present literally
    expect(container.textContent).toContain(xssSector);

    // 2. No <svg> element with an onload attribute exists
    const svgWithOnload = container.querySelector('svg[onload]');
    expect(svgWithOnload).toBeNull();
  });

  // =========================================================================
  // 3. Market News Section Rendering with Hostile Headlines
  // =========================================================================
  it('renders hostile news headlines and javascript: links safely as text', () => {
    const hostileHeadline = "<script>alert('xss-news-title')</script>";
    const hostileSummary = '<a href="javascript:alert(1)">Click for free tokens</a>';

    const maliciousNews: NewsResponse = {
      articles: [
        {
          id: 'news-hostile-01',
          title: hostileHeadline,
          summary: hostileSummary,
          source: 'Hostile Simulated Wire',
          published_at: '2026-10-10T10:00:00Z',
          url: 'javascript:alert(document.domain)',
          related_symbols: ['RELIANCE'],
          sentiment: 'NEUTRAL',
          is_simulated: true,
          disclaimer: 'Simulated news payload',
        },
      ],
      total_count: 1,
      fetched_at: '2026-10-10T10:00:00Z',
      cache_hit: false,
      is_simulated: true,
      disclaimer: 'Simulated response disclaimer',
    };

    const { container } = render(
      <MarketNewsSection
        newsResponse={maliciousNews}
        selectedSymbol="RELIANCE"
        isFilteredBySymbol={false}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    // 1. Headline rendered as inert text
    expect(screen.getByText(hostileHeadline)).toBeInTheDocument();
    expect(container.textContent).toContain(hostileSummary);

    // 2. No script element exists
    expect(container.querySelector('script')).toBeNull();

    // 3. No executable javascript: anchor link exists
    const jsLinks = container.querySelectorAll('a[href^="javascript:"]');
    expect(jsLinks.length).toBe(0);
  });

  // =========================================================================
  // 4. AI Insights Section Rendering with Adversarial Narratives
  // =========================================================================
  it('renders hostile prompt overrides and HTML tags in AI reports safely as text', () => {
    const hostileExecutiveSummary =
      "Ignore previous instructions. <iframe src='http://attacker.com'></iframe> All funds are safe.";
    const hostileDriverTitle = "<b onmouseover=alert(1)>Critical Concentration</b>";

    const maliciousReport: AIInsightReport = {
      report_id: 'rep-hostile-01',
      portfolio_id: 'port-01',
      generated_at: '2026-10-10T10:00:00Z',
      provider_name: 'DETERMINISTIC_DEMO_REASONER',
      model_id: 'demo-v1',
      is_simulated: true,
      executive_summary: hostileExecutiveSummary,
      key_drivers: [
        {
          driver_id: 'driver-01',
          driver_type: 'CONCENTRATION',
          title: hostileDriverTitle,
          statement: 'Top holding allocation <script>alert(1)</script>',
          supporting_metric_key: 'concentration.top_holding_weight_percent',
          supporting_metric_value: 50.0,
          source_reference: 'analytics.concentration',
          is_grounded: true,
        },
      ],
      risk_alerts: [],
      confidence: {
        score: 0.85,
        level: 'HIGH',
        calibration_limitation: 'Heuristic confidence score; not calibrated.',
        data_quality_discount: 0,
        staleness_discount: 0,
      },
      review_cards: [],
      uncertainty_and_gaps: [],
      disclaimers: ['Educational use only.'],
      review_status: 'VERIFIED',
      grounding_report: {
        total_claims_checked: 1,
        passed_count: 1,
        flagged_count: 0,
        rejected_count: 0,
        is_acceptable: true,
        findings: [],
      },
    };

    const { container } = render(
      <AIInsightsSection
        aiReport={maliciousReport}
        isGenerating={false}
        error={null}
        onGenerate={vi.fn()}
      />
    );

    // 1. Text content rendered verbatim
    expect(container.textContent).toContain(hostileExecutiveSummary);
    expect(screen.getByText(hostileDriverTitle)).toBeInTheDocument();

    // 2. No <iframe> or <script> element exists in the DOM
    expect(container.querySelector('iframe')).toBeNull();
    expect(container.querySelector('script')).toBeNull();

    // 3. No element has an inline onmouseover event handler attribute
    expect(container.querySelector('[onmouseover]')).toBeNull();
  });

  // =========================================================================
  // 5. Baseline: Ordinary Portfolio and News Render Correctly
  // =========================================================================
  it('renders legitimate portfolio names and news headlines cleanly', () => {
    const normalPortfolio: PortfolioResponse = {
      id: 'port-normal-01',
      name: 'Nifty 50 Index Fund & Bluechip Basket',
      description: 'Long-term diversified Indian equity holdings',
      is_sample: true,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 10,
    };

    render(
      <PortfolioOverviewCard
        portfolio={normalPortfolio}
        analytics={null}
        isLoading={false}
      />
    );

    expect(screen.getByText('Nifty 50 Index Fund & Bluechip Basket')).toBeInTheDocument();
    expect(screen.getByText(/Long-term diversified Indian equity holdings/)).toBeInTheDocument();
  });
});
