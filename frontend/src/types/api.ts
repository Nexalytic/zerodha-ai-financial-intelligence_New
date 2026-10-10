export interface DatabaseHealth {
  status: string;
  engine: string;
  journal_mode?: string | null;
  foreign_keys_enabled?: boolean | null;
  error?: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  environment: string;
  database: DatabaseHealth;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Array<{
    location: string;
    message: string;
    type: string;
  }>;
}

export interface ErrorEnvelope {
  success: boolean;
  error: ErrorDetail;
  timestamp: string;
}

export type HealthStatusType = 'loading' | 'healthy' | 'degraded' | 'offline';

export interface HealthState {
  status: HealthStatusType;
  data: HealthResponse | null;
  errorMessage: string | null;
  lastChecked: Date | null;
}
