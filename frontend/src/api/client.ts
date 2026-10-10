import axios, { AxiosError } from 'axios';
import { HealthResponse, ErrorEnvelope } from '../types/api';

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ApiClientError {
  isNetworkError: boolean;
  isDatabaseError: boolean;
  statusCode?: number;
  message: string;
  data?: HealthResponse | ErrorEnvelope | null;
}

export function parseApiError(error: unknown): ApiClientError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<any>;

    // Case 1: Response received from server with error status code (e.g. 503, 500, 404, 422)
    if (axiosError.response) {
      const status = axiosError.response.status;
      const data = axiosError.response.data;

      // 503: Database connectivity failure / degraded service
      if (status === 503) {
        const dbErrorMsg =
          data?.database?.error ||
          data?.error?.message ||
          'Database connectivity is currently unavailable.';
        return {
          isNetworkError: false,
          isDatabaseError: true,
          statusCode: 503,
          message: dbErrorMsg,
          data,
        };
      }

      // Standard ErrorEnvelope from backend
      if (data?.error?.message) {
        return {
          isNetworkError: false,
          isDatabaseError: false,
          statusCode: status,
          message: data.error.message,
          data,
        };
      }

      return {
        isNetworkError: false,
        isDatabaseError: false,
        statusCode: status,
        message: `Server returned error (${status}): ${axiosError.response.statusText || 'Error'}`,
        data,
      };
    }

    // Case 2: Request made but no response (Timeout or Connection Refused)
    if (axiosError.code === 'ECONNABORTED' || (axiosError.message && axiosError.message.includes('timeout'))) {
      return {
        isNetworkError: true,
        isDatabaseError: false,
        message: 'Request timed out after 10 seconds. Please verify the backend server is responsive.',
      };
    }

    return {
      isNetworkError: true,
      isDatabaseError: false,
      message: 'Backend server is unreachable. Please verify that the API is running on 127.0.0.1:8000.',
    };
  }

  return {
    isNetworkError: false,
    isDatabaseError: false,
    message: error instanceof Error ? error.message : 'An unexpected error occurred.',
  };
}
