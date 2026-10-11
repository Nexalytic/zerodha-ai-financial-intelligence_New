import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../src/api/client';
import {
  fetchPortfolios,
  fetchPortfolio,
  seedDemoPortfolio,
  createPortfolio,
  deletePortfolio,
  addHolding,
} from '../src/api/portfolios';
import { fetchQuote, fetchBatchQuotes } from '../src/api/marketData';
import { fetchNews } from '../src/api/news';
import {
  fetchPortfolioAnalytics,
  fetchPortfolioInsights,
} from '../src/api/analytics';
import { generateAIPortfolioInsights } from '../src/api/aiReasoning';

vi.mock('../src/api/client', async () => {
  const actual = await vi.importActual<any>('../src/api/client');
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

describe('Typed API Modules', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Portfolios API', () => {
    it('fetchPortfolios passes query params and returns list', async () => {
      const mockData = [{ id: 'port-1', name: 'Demo', holdings_count: 5 }];
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockData });

      const result = await fetchPortfolios(true);
      expect(apiClient.get).toHaveBeenCalledWith('/portfolios', { params: { is_sample: true } });
      expect(result).toEqual(mockData);
    });

    it('fetchPortfolio queries specific portfolio ID', async () => {
      const mockDetail = { id: 'p-123', name: 'Test', holdings: [] };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockDetail });

      const result = await fetchPortfolio('p-123');
      expect(apiClient.get).toHaveBeenCalledWith('/portfolios/p-123');
      expect(result).toEqual(mockDetail);
    });

    it('seedDemoPortfolio calls POST /portfolios/seed-demo', async () => {
      const mockSeed = { portfolio: { id: 'demo-1' }, created: true, message: 'Seeded' };
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockSeed });

      const result = await seedDemoPortfolio();
      expect(apiClient.post).toHaveBeenCalledWith('/portfolios/seed-demo');
      expect(result).toEqual(mockSeed);
    });

    it('createPortfolio calls POST /portfolios with payload', async () => {
      const payload = { name: 'New Port', is_sample: false };
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { id: 'new-1', ...payload } });

      const result = await createPortfolio(payload);
      expect(apiClient.post).toHaveBeenCalledWith('/portfolios', payload);
      expect(result.id).toBe('new-1');
    });

    it('deletePortfolio calls DELETE /portfolios/:id', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({
        data: { id: 'p-1', deleted: true, message: 'Deleted' },
      });

      const result = await deletePortfolio('p-1');
      expect(apiClient.delete).toHaveBeenCalledWith('/portfolios/p-1');
      expect(result.deleted).toBe(true);
    });

    it('addHolding calls POST /portfolios/:id/holdings with payload', async () => {
      const payload = {
        symbol: 'TCS',
        exchange: 'NSE',
        quantity: 25,
        average_buy_price: 3850.5,
        sector: 'IT',
        asset_class: 'EQUITY',
      };
      const mockResponse = { id: 'h-100', portfolio_id: 'p-1', ...payload };
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockResponse });

      const result = await addHolding('p-1', payload);
      expect(apiClient.post).toHaveBeenCalledWith('/portfolios/p-1/holdings', payload);
      expect(result.id).toBe('h-100');
    });
  });

  describe('Market Data API', () => {
    it('fetchQuote sends uppercase symbol and exchange query params', async () => {
      const mockQuote = { symbol: 'RELIANCE', exchange: 'NSE', current_price: 2850.5 };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockQuote });

      const result = await fetchQuote('reliance', 'nse');
      expect(apiClient.get).toHaveBeenCalledWith('/market-data/quote', {
        params: { symbol: 'RELIANCE', exchange: 'NSE' },
      });
      expect(result).toEqual(mockQuote);
    });

    it('fetchBatchQuotes formats comma-separated symbols', async () => {
      const mockBatch = { quotes: {}, total_symbols: 2, cache_hits_count: 1, cache_misses_count: 1 };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockBatch });

      const result = await fetchBatchQuotes(['tcs', 'infy'], 'nse');
      expect(apiClient.get).toHaveBeenCalledWith('/market-data/quotes', {
        params: { symbols: 'TCS,INFY', exchange: 'NSE' },
      });
      expect(result).toEqual(mockBatch);
    });
  });

  describe('News API', () => {
    it('fetchNews passes symbol filter and limit', async () => {
      const mockNews = { articles: [], total_count: 0 };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockNews });

      const result = await fetchNews(['reliance', 'tcs'], 5);
      expect(apiClient.get).toHaveBeenCalledWith('/news', {
        params: { limit: 5, symbols: 'RELIANCE,TCS' },
      });
      expect(result).toEqual(mockNews);
    });

    it('fetchNews handles call without symbols', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { articles: [] } });

      await fetchNews(undefined, 10);
      expect(apiClient.get).toHaveBeenCalledWith('/news', { params: { limit: 10 } });
    });
  });

  describe('Analytics API', () => {
    it('fetchPortfolioAnalytics calls /portfolios/:id/analytics', async () => {
      const mockAnalytics = { portfolio_id: 'p-1', status: 'COMPLETE' };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockAnalytics });

      const result = await fetchPortfolioAnalytics('p-1');
      expect(apiClient.get).toHaveBeenCalledWith('/portfolios/p-1/analytics');
      expect(result).toEqual(mockAnalytics);
    });

    it('fetchPortfolioInsights calls /portfolios/:id/insights', async () => {
      const mockInsights = { portfolio_id: 'p-1', insights: [], total_insights: 0 };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockInsights });

      const result = await fetchPortfolioInsights('p-1');
      expect(apiClient.get).toHaveBeenCalledWith('/portfolios/p-1/insights');
      expect(result).toEqual(mockInsights);
    });
  });

  describe('AI Reasoning API', () => {
    it('generateAIPortfolioInsights sends POST /portfolios/:id/ai-insights with options', async () => {
      const mockReport = { report_id: 'rep-1', portfolio_id: 'p-1', review_status: 'VERIFIED' };
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockReport });

      const opts = { include_news: true, news_limit: 5, provider_override: 'DETERMINISTIC' };
      const result = await generateAIPortfolioInsights('p-1', opts);

      expect(apiClient.post).toHaveBeenCalledWith('/portfolios/p-1/ai-insights', opts);
      expect(result).toEqual(mockReport);
    });

    it('generateAIPortfolioInsights uses sensible defaults when options not provided', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { report_id: 'rep-default' } });

      await generateAIPortfolioInsights('p-2');
      expect(apiClient.post).toHaveBeenCalledWith('/portfolios/p-2/ai-insights', {
        include_news: true,
        news_limit: 10,
      });
    });
  });
});
