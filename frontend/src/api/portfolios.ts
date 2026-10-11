import { apiClient } from './client';
import {
  HoldingCreate,
  HoldingResponse,
  PortfolioCreate,
  PortfolioDeleteResponse,
  PortfolioDetailResponse,
  PortfolioResponse,
  SeedDemoResponse,
} from '../types/portfolio';

/**
 * Lists all investment portfolios with optional sample filter.
 */
export async function fetchPortfolios(isSample?: boolean): Promise<PortfolioResponse[]> {
  const params: Record<string, any> = {};
  if (isSample !== undefined) {
    params.is_sample = isSample;
  }
  const response = await apiClient.get<PortfolioResponse[]>('/portfolios', { params });
  return response.data;
}

/**
 * Retrieves a single portfolio with all its holdings by ID.
 */
export async function fetchPortfolio(portfolioId: string): Promise<PortfolioDetailResponse> {
  const response = await apiClient.get<PortfolioDetailResponse>(`/portfolios/${encodeURIComponent(portfolioId)}`);
  return response.data;
}

/**
 * Idempotently seeds or retrieves the canonical 'Demo Indian Bluechip Portfolio'.
 */
export async function seedDemoPortfolio(): Promise<SeedDemoResponse> {
  const response = await apiClient.post<SeedDemoResponse>('/portfolios/seed-demo');
  return response.data;
}

/**
 * Creates a new portfolio with optional initial holdings.
 */
export async function createPortfolio(data: PortfolioCreate): Promise<PortfolioDetailResponse> {
  const response = await apiClient.post<PortfolioDetailResponse>('/portfolios', data);
  return response.data;
}

/**
 * Deletes a portfolio by ID.
 */
export async function deletePortfolio(portfolioId: string): Promise<PortfolioDeleteResponse> {
  const response = await apiClient.delete<PortfolioDeleteResponse>(`/portfolios/${encodeURIComponent(portfolioId)}`);
  return response.data;
}

/**
 * Adds a new holding position to an existing investment portfolio.
 */
export async function addHolding(
  portfolioId: string,
  data: HoldingCreate
): Promise<HoldingResponse> {
  const response = await apiClient.post<HoldingResponse>(
    `/portfolios/${encodeURIComponent(portfolioId)}/holdings`,
    data
  );
  return response.data;
}
