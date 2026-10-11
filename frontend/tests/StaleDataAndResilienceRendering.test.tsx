import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StockInspectorCard } from '../src/components/market/StockInspectorCard';
import { MarketNewsSection } from '../src/components/market/MarketNewsSection';
import { Quote, NewsResponse } from '../src/types/marketData';

describe('Phase 08 Step 8.3: Frontend Stale Data, Conflicting News & Failure Resilience', () => {
  // =========================================================================
  // 1. StockInspectorCard: Stale Data & Unavailable Resilience
  // =========================================================================
  it('renders an emergency stale cache warning banner when a quote is marked is_stale=true', () => {
    const staleQuote: Quote = {
      symbol: 'TCS',
      exchange: 'NSE',
      current_price: 3920.0,
      change: -12.4,
      change_percent: -0.32,
      status: 'AVAILABLE',
      is_simulated: true,
      source: 'SIMULATED_DEMO_PROVIDER',
      generated_at: '2026-10-10T10:00:00Z',
      market_as_of: null,
      cached_at: '2026-10-10T10:00:00Z',
      cache_hit: false,
      is_stale: true, // Emergency stale fallback
      ttl_remaining_seconds: 0.0,
      disclaimer: 'Simulated quote',
      explanation: 'Provider failed. Serving stale cached quote.',
    };

    render(
      <StockInspectorCard
        quote={staleQuote}
        symbols={['TCS', 'RELIANCE']}
        selectedSymbol="TCS"
        selectedExchange="NSE"
        onSelectSymbol={vi.fn()}
        onSelectExchange={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    // Assert stale warning banner is visible
    const staleWarning = screen.getByTestId('inspector-stale-warning');
    expect(staleWarning).toBeInTheDocument();
    expect(screen.getByText('Emergency Stale Cache Quote')).toBeInTheDocument();
    expect(
      screen.getByText(/emergency cache fallback due to provider limits/i)
    ).toBeInTheDocument();

    // Assert valid pricing is still displayed rather than blank or zero
    expect(screen.getByTestId('inspector-price')).toHaveTextContent('3,920.00');
  });

  it('renders unavailable quote notice with explanation when market data is unavailable', () => {
    const unavailableQuote: Quote = {
      symbol: 'XYZ_UNKNOWN',
      exchange: 'NSE',
      current_price: null,
      change: null,
      change_percent: null,
      status: 'UNAVAILABLE',
      is_simulated: true,
      source: 'SIMULATED_DEMO_PROVIDER',
      generated_at: '2026-10-10T10:00:00Z',
      market_as_of: null,
      cached_at: null,
      cache_hit: false,
      is_stale: false,
      disclaimer: 'Simulated quote',
      explanation: "Symbol 'XYZ_UNKNOWN' not found in market universe. No price fabricated.",
    };

    render(
      <StockInspectorCard
        quote={unavailableQuote}
        symbols={['XYZ_UNKNOWN']}
        selectedSymbol="XYZ_UNKNOWN"
        selectedExchange="NSE"
        onSelectSymbol={vi.fn()}
        onSelectExchange={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    const notice = screen.getByTestId('inspector-unavailable-notice');
    expect(notice).toBeInTheDocument();
    expect(
      screen.getByText(/Quote Unavailable for XYZ_UNKNOWN \(NSE\)/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Symbol 'XYZ_UNKNOWN' not found in market universe/i)
    ).toBeInTheDocument();
  });

  it('renders provider error banner when quote fetch encounters an error', () => {
    render(
      <StockInspectorCard
        quote={null}
        symbols={['RELIANCE']}
        selectedSymbol="RELIANCE"
        selectedExchange="NSE"
        onSelectSymbol={vi.fn()}
        onSelectExchange={vi.fn()}
        isLoading={false}
        error="Network timeout connecting to market provider"
      />
    );

    const errorBanner = screen.getByTestId('inspector-error-banner');
    expect(errorBanner).toBeInTheDocument();
    expect(
      screen.getByText('Failed to fetch quote for RELIANCE')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Network timeout connecting to market provider')
    ).toBeInTheDocument();
  });

  // =========================================================================
  // 2. MarketNewsSection: Conflicting News, Missing Fields & Resilience
  // =========================================================================
  it('renders conflicting news headlines (POSITIVE and NEGATIVE) for the same symbol with source attribution', () => {
    const conflictingNews: NewsResponse = {
      articles: [
        {
          id: 'news-pos-01',
          title: 'Reliance Expands Solar Gigafactory Output',
          summary: 'Green energy capacity expansion accelerated.',
          source: 'Clean Energy Wire',
          published_at: '2026-10-10T09:00:00Z',
          url: null,
          related_symbols: ['RELIANCE'],
          sentiment: 'POSITIVE',
          is_simulated: true,
          disclaimer: 'Simulated financial news',
        },
        {
          id: 'news-neg-01',
          title: 'Refining Margins Contract on Global Glut',
          summary: 'Downstream margins compressed by international supply shifts.',
          source: 'PetroChemicals Daily',
          published_at: '2026-10-10T11:00:00Z',
          url: null,
          related_symbols: ['RELIANCE'],
          sentiment: 'NEGATIVE',
          is_simulated: true,
          disclaimer: 'Simulated financial news',
        },
      ],
      total_count: 2,
      fetched_at: '2026-10-10T11:30:00Z',
      cache_hit: false,
      is_simulated: true,
      disclaimer: 'Simulated financial news response',
    };

    render(
      <MarketNewsSection
        newsResponse={conflictingNews}
        selectedSymbol="RELIANCE"
        isFilteredBySymbol={true}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    // Both headlines rendered simultaneously without collision
    expect(
      screen.getByText('Reliance Expands Solar Gigafactory Output')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Refining Margins Contract on Global Glut')
    ).toBeInTheDocument();

    // Both opposing sentiment badges rendered
    expect(screen.getByTestId('news-sentiment-news-pos-01')).toHaveTextContent(
      'POSITIVE'
    );
    expect(screen.getByTestId('news-sentiment-news-neg-01')).toHaveTextContent(
      'NEGATIVE'
    );

    // Distinct sources preserved
    expect(screen.getByText('Source: Clean Energy Wire')).toBeInTheDocument();
    expect(
      screen.getByText('Source: PetroChemicals Daily')
    ).toBeInTheDocument();
  });

  it('renders sparse news articles with missing optional fields without crashing', () => {
    const sparseNews: NewsResponse = {
      articles: [
        {
          id: 'news-sparse-01',
          title: 'Sparse Headline Without URL or Published Date',
          summary: 'Brief summary text.',
          source: 'Attributed Feed',
          published_at: '',
          url: null,
          related_symbols: ['INFY'],
          sentiment: 'NEUTRAL',
          is_simulated: false,
          disclaimer: 'Standard disclaimer',
        },
      ],
      total_count: 1,
      fetched_at: '2026-10-10T12:00:00Z',
      cache_hit: false,
      is_simulated: false,
      disclaimer: 'Standard response disclaimer',
    };

    render(
      <MarketNewsSection
        newsResponse={sparseNews}
        selectedSymbol="INFY"
        isFilteredBySymbol={false}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    expect(
      screen.getByText('Sparse Headline Without URL or Published Date')
    ).toBeInTheDocument();
    expect(screen.getByText('Brief summary text.')).toBeInTheDocument();
    expect(screen.getByText('Source: Attributed Feed')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument(); // Fallback for missing published_at
  });

  it('renders news error banner when news provider fails', () => {
    render(
      <MarketNewsSection
        newsResponse={null}
        selectedSymbol="RELIANCE"
        isFilteredBySymbol={false}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error="Financial wire service gateway timeout (504)"
      />
    );

    const errorBanner = screen.getByTestId('news-error-banner');
    expect(errorBanner).toBeInTheDocument();
    expect(
      screen.getByText('Failed to load financial news')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Financial wire service gateway timeout (504)')
    ).toBeInTheDocument();
  });

  it('renders empty news message when article list is empty', () => {
    const emptyNews: NewsResponse = {
      articles: [],
      total_count: 0,
      fetched_at: '2026-10-10T12:00:00Z',
      cache_hit: false,
      is_simulated: true,
      disclaimer: 'Empty response',
    };

    render(
      <MarketNewsSection
        newsResponse={emptyNews}
        selectedSymbol="BAJAJ-AUTO"
        isFilteredBySymbol={true}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={null}
      />
    );

    const noNews = screen.getByTestId('no-news-message');
    expect(noNews).toBeInTheDocument();
    expect(
      screen.getByText(/No news articles found for BAJAJ-AUTO/i)
    ).toBeInTheDocument();
  });
});
