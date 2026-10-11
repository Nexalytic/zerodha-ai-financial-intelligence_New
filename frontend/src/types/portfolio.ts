export interface HoldingBase {
  symbol: string;
  exchange: string;
  quantity: number;
  average_buy_price: number | string;
  sector?: string | null;
  asset_class: string;
}

export interface HoldingResponse extends HoldingBase {
  id: string;
  portfolio_id: string;
  created_at: string;
  updated_at: string;
}

export interface HoldingCreate extends HoldingBase {}

export interface PortfolioBase {
  name: string;
  description?: string | null;
  is_sample: boolean;
}

export interface PortfolioResponse extends PortfolioBase {
  id: string;
  created_at: string;
  updated_at: string;
  holdings_count: number;
}

export interface PortfolioDetailResponse extends PortfolioResponse {
  holdings: HoldingResponse[];
}

export interface PortfolioCreate extends PortfolioBase {
  holdings?: HoldingCreate[];
}

export interface PortfolioUpdate {
  name?: string | null;
  description?: string | null;
}

export interface PortfolioImportRequest {
  name: string;
  description?: string | null;
  is_sample?: boolean;
  holdings: HoldingCreate[];
}

export interface SeedDemoResponse {
  portfolio: PortfolioDetailResponse;
  created: boolean;
  message: string;
}

export interface PortfolioDeleteResponse {
  id: string;
  deleted: boolean;
  message: string;
}
