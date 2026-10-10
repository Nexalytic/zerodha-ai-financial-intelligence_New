import { apiClient } from './client';
import { HealthResponse } from '../types/api';

/**
 * Calls GET /health on the backend API.
 * An HTTP 200 resolves with HealthResponse.
 * An HTTP 503 or network failure rejects with an AxiosError.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
}
