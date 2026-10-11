export type InsightCategory =
  | 'CONCENTRATION'
  | 'DIVERSIFICATION'
  | 'RISK'
  | 'PERFORMANCE'
  | 'ALLOCATION';

export type InsightSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface PortfolioInsight {
  id: string;
  portfolio_id: string;
  category: InsightCategory;
  severity: InsightSeverity;
  title: string;
  description: string;
  evidence?: Record<string, any> | null;
  related_symbols: string[];
  created_at: string;
  is_simulated: boolean;
  source: string;
  disclaimer: string;
}

export interface PortfolioInsightsResponse {
  portfolio_id: string;
  insights: PortfolioInsight[];
  total_insights: number;
  generated_at: string;
  is_sample_portfolio: boolean;
  disclaimer: string;
}

export type DriverType =
  | 'CONCENTRATION'
  | 'SECTOR'
  | 'PERFORMANCE'
  | 'RISK'
  | 'DATA_QUALITY'
  | 'DIVERSIFICATION'
  | 'NEWS';

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW';

export type ReviewStatus =
  | 'PENDING_REVIEW'
  | 'VERIFIED'
  | 'FLAGGED_WITH_WARNINGS'
  | 'REJECTED';

export type FindingStatus = 'PASSED' | 'FLAGGED' | 'REJECTED';

export interface EvidenceKeyDriver {
  driver_id: string;
  driver_type: DriverType;
  title: string;
  statement: string;
  supporting_metric_key: string;
  supporting_metric_value: any;
  source_reference: string;
  is_grounded: boolean;
}

export interface AIRiskAlert {
  alert_id: string;
  severity: AlertSeverity;
  category: string;
  headline: string;
  explanation: string;
  evidence_reference: string;
  actionable_mitigation?: string | null;
}

export interface AIConfidenceIndicator {
  score: number | string;
  level: ConfidenceLevel;
  calibration_limitation: string;
  data_quality_discount: number | string;
  staleness_discount: number | string;
}

export interface ReviewableInsightCard {
  card_id: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  cited_metrics: Record<string, any>;
  related_symbols: string[];
  review_status: ReviewStatus;
  created_at: string;
}

export interface GroundingFinding {
  check_name: string;
  target_id: string;
  status: FindingStatus;
  reason?: string | null;
  details?: Record<string, any>;
}

export interface GroundingValidationReport {
  total_claims_checked: number;
  passed_count: number;
  flagged_count: number;
  rejected_count: number;
  findings: GroundingFinding[];
  is_acceptable: boolean;
}

export interface AIInsightReport {
  report_id: string;
  portfolio_id: string;
  generated_at: string;
  provider_name: string;
  model_id: string;
  is_simulated: boolean;
  executive_summary: string;
  key_drivers: EvidenceKeyDriver[];
  risk_alerts: AIRiskAlert[];
  confidence: AIConfidenceIndicator;
  review_cards: ReviewableInsightCard[];
  uncertainty_and_gaps: string[];
  disclaimers: string[];
  review_status: ReviewStatus;
  grounding_report: GroundingValidationReport;
}

export interface GenerateAIInsightsRequest {
  include_news?: boolean;
  news_limit?: number;
  provider_override?: string;
}
