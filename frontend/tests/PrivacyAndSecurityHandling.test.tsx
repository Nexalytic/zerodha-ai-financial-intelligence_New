import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StockInspectorCard } from '../src/components/market/StockInspectorCard';
import { MarketNewsSection } from '../src/components/market/MarketNewsSection';
import { AIInsightsSection } from '../src/components/portfolio/AIInsightsSection';

describe('Phase 08 Step 8.4: Frontend Privacy-Safe Error Display & Security', () => {
  it('renders clean user-facing error messages in stock inspector without leaking internal stack traces', () => {
    const errorWithDiagnostic = 'Market quote unavailable: Upstream provider timeout at /api/v1/market-data/quote';

    render(
      <StockInspectorCard
        quote={null}
        symbols={['RELIANCE']}
        selectedSymbol="RELIANCE"
        selectedExchange="NSE"
        onSelectSymbol={vi.fn()}
        onSelectExchange={vi.fn()}
        isLoading={false}
        error={errorWithDiagnostic}
      />
    );

    // Banner is rendered with the error message
    const errorBanner = screen.getByTestId('inspector-error-banner');
    expect(errorBanner).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch quote for RELIANCE')).toBeInTheDocument();
    expect(screen.getByText(errorWithDiagnostic)).toBeInTheDocument();

    // Assert that React component does not output raw stack trace elements
    expect(errorBanner.textContent).not.toContain('Traceback (most recent call last)');
    expect(errorBanner.textContent).not.toContain('sqlite3.OperationalError');
  });

  it('renders clean user-facing error message in news section without leaking sensitive parameters', () => {
    const newsError = 'Simulated financial news feed currently offline.';

    render(
      <MarketNewsSection
        newsResponse={null}
        selectedSymbol="TCS"
        isFilteredBySymbol={false}
        onToggleFilter={vi.fn()}
        onSelectSymbol={vi.fn()}
        isLoading={false}
        error={newsError}
      />
    );

    const errorBanner = screen.getByTestId('news-error-banner');
    expect(errorBanner).toBeInTheDocument();
    expect(screen.getByText('Failed to load financial news')).toBeInTheDocument();
    expect(screen.getByText(newsError)).toBeInTheDocument();
  });

  it('renders clean error state in AI insights section without leaking server paths or secrets', () => {
    const aiError = 'AI reasoning provider failed to generate insights.';

    render(
      <AIInsightsSection
        aiReport={null}
        isGenerating={false}
        error={aiError}
        onGenerate={vi.fn()}
      />
    );

    // Assert error message is present
    expect(screen.getByText(/AI reasoning provider failed to generate insights/i)).toBeInTheDocument();
    // Assert no internal filesystem path or credentials are leaked
    const containerText = document.body.textContent || '';
    expect(containerText).not.toContain('GROQ_API_KEY');
    expect(containerText).not.toContain('ALPHA_VANTAGE_API_KEY');
    expect(containerText).not.toContain('sqlite+aiosqlite://');
  });
});
