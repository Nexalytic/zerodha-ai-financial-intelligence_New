import { apiClient } from './client';
import { BatchQuotesResponse, Quote } from '../types/marketData';

/**
 * Fetches a single quote for a ticker symbol and exchange.
 */
export async function fetchQuote(symbol: string, exchange: string = 'NSE'): Promise<Quote> {
  const response = await apiClient.get<Quote>('/market-data/quote', {
    params: {
      symbol: symbol.trim().toUpperCase(),
      exchange: exchange.trim().toUpperCase(),
    },
  });
  return response.data;
}

/**
 * Fetches batch quotes for multiple symbols with cache metrics.
 */
export async function fetchBatchQuotes(
  symbols: string[],
  exchange: string = 'NSE'
): Promise<BatchQuotesResponse> {
  const cleanSymbols = symbols.map((s) => s.trim().toUpperCase()).filter(Boolean);
  const response = await apiClient.get<BatchQuotesResponse>('/market-data/quotes', {
    params: {
      symbols: cleanSymbols.join(','),
      exchange: exchange.trim().toUpperCase(),
    },
  });
  return response.data;
}
