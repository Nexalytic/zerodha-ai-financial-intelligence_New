export type QuoteStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'ERROR';

export interface Quote {
  symbol: string;
  exchange: string;
  current_price?: number | string | null;
  change?: number | string | null;
  change_percent?: number | string | null;
  status: QuoteStatus;
  is_simulated: boolean;
  source: string;
  generated_at: string;
  market_as_of?: string | null;
  cached_at?: string | null;
  cache_hit: boolean;
  ttl_remaining_seconds?: number | null;
  is_stale: boolean;
  disclaimer: string;
  explanation?: string | null;
}

export interface BatchQuotesResponse {
  quotes: Record<string, Quote>;
  total_symbols: number;
  cache_hits_count: number;
  cache_misses_count: number;
  fetched_at: string;
}

export type NewsSentiment = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  source: string;
  published_at: string;
  url?: string | null;
  related_symbols: string[];
  sentiment: NewsSentiment;
  is_simulated: boolean;
  disclaimer: string;
}

export interface NewsResponse {
  articles: NewsArticle[];
  total_count: number;
  fetched_at: string;
  cache_hit: boolean;
  is_simulated: boolean;
  disclaimer: string;
}
