import { apiClient } from './client';
import { PortfolioAnalyticsResponse } from '../types/analytics';
import { PortfolioInsightsResponse } from '../types/aiReasoning';

/**
 * Computes and retrieves comprehensive portfolio analytics, valuations,
 * sector exposure, and concentration metrics.
 */
export async function fetchPortfolioAnalytics(
  portfolioId: string
): Promise<PortfolioAnalyticsResponse> {
  const response = await apiClient.get<PortfolioAnalyticsResponse>(
    `/portfolios/${encodeURIComponent(portfolioId)}/analytics`
  );
  return response.data;
}

/**
 * Computes and retrieves deterministic rule-based insights and risk observations.
 */
export async function fetchPortfolioInsights(
  portfolioId: string
): Promise<PortfolioInsightsResponse> {
  const response = await apiClient.get<PortfolioInsightsResponse>(
    `/portfolios/${encodeURIComponent(portfolioId)}/insights`
  );
  return response.data;
}
