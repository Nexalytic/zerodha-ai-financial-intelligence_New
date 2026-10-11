import { apiClient } from './client';
import { AIInsightReport, GenerateAIInsightsRequest } from '../types/aiReasoning';

/**
 * Generates or retrieves evidence-grounded AI intelligence insights for a portfolio.
 */
export async function generateAIPortfolioInsights(
  portfolioId: string,
  options?: GenerateAIInsightsRequest
): Promise<AIInsightReport> {
  const payload = options || {
    include_news: true,
    news_limit: 10,
  };
  const response = await apiClient.post<AIInsightReport>(
    `/portfolios/${encodeURIComponent(portfolioId)}/ai-insights`,
    payload
  );
  return response.data;
}
