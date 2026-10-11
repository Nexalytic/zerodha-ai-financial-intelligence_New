import { apiClient } from './client';
import { NewsResponse } from '../types/marketData';

/**
 * Fetches simulated financial news articles, optionally filtered by stock symbols.
 */
export async function fetchNews(symbols?: string[], limit: number = 10): Promise<NewsResponse> {
  const params: Record<string, any> = { limit };
  if (symbols && symbols.length > 0) {
    const cleanSymbols = symbols.map((s) => s.trim().toUpperCase()).filter(Boolean);
    if (cleanSymbols.length > 0) {
      params.symbols = cleanSymbols.join(',');
    }
  }
  const response = await apiClient.get<NewsResponse>('/news', { params });
  return response.data;
}
