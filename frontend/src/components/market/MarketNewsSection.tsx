import React from 'react';
import { NewsArticle, NewsResponse, NewsSentiment } from '../../types/marketData';
import {
  FileText,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  Tag,
} from 'lucide-react';

export interface MarketNewsSectionProps {
  newsResponse: NewsResponse | null;
  selectedSymbol: string;
  isFilteredBySymbol: boolean;
  onToggleFilter: (filterBySymbol: boolean) => void;
  onSelectSymbol: (symbol: string) => void;
  isLoading: boolean;
  error: string | null;
}

export const MarketNewsSection: React.FC<MarketNewsSectionProps> = ({
  newsResponse,
  selectedSymbol,
  isFilteredBySymbol,
  onToggleFilter,
  onSelectSymbol,
  isLoading,
  error,
}) => {
  const articles: NewsArticle[] = newsResponse?.articles || [];

  const getSentimentBadge = (sentiment: NewsSentiment) => {
    switch (sentiment) {
      case 'POSITIVE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <TrendingUp className="w-3 h-3 text-emerald-600" />
            <span>POSITIVE</span>
          </span>
        );
      case 'NEGATIVE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <TrendingDown className="w-3 h-3 text-rose-600" />
            <span>NEGATIVE</span>
          </span>
        );
      case 'NEUTRAL':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-700 border border-gray-200">
            <Minus className="w-3 h-3 text-gray-500" />
            <span>NEUTRAL</span>
          </span>
        );
    }
  };

  return (
    <div
      data-testid="market-news-section"
      className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden"
    >
      {/* Header with Filter Toggles */}
      <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 tracking-tight">
              Financial News &amp; Market Sentiment
            </h2>
            <p className="text-xs text-gray-500">
              Simulated financial news feed and sentiment tags linked to portfolio securities.
            </p>
          </div>
        </div>

        {/* Filter Toggle Buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onToggleFilter(false)}
            data-testid="filter-all-news-btn"
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              !isFilteredBySymbol
                ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs'
                : 'text-gray-600 hover:bg-gray-50 border border-gray-200'
            }`}
          >
            All Market News
          </button>
          <button
            onClick={() => onToggleFilter(true)}
            data-testid="filter-symbol-news-btn"
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              isFilteredBySymbol
                ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs'
                : 'text-gray-600 hover:bg-gray-50 border border-gray-200'
            }`}
          >
            {selectedSymbol} News
          </button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {error ? (
          <div
            data-testid="news-error-banner"
            className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Failed to load financial news</p>
              <p className="mt-0.5 text-rose-700">{error}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="py-8 text-center text-gray-500 text-xs">
            <div className="inline-flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping" />
              <span>Fetching financial news articles and sentiment feed...</span>
            </div>
          </div>
        ) : articles.length === 0 ? (
          <div
            data-testid="no-news-message"
            className="py-8 text-center text-gray-400 text-xs flex flex-col items-center justify-center space-y-1.5"
          >
            <FileText className="w-8 h-8 text-gray-300" />
            <p className="font-semibold text-gray-600">
              No news articles found {isFilteredBySymbol ? `for ${selectedSymbol}` : ''}
            </p>
            <p className="text-gray-400">
              Try viewing &ldquo;All Market News&rdquo; or select another symbol.
            </p>
          </div>
        ) : (
          <div className="space-y-3.5">
            {articles.map((article) => (
              <div
                key={article.id}
                data-testid={`news-article-card-${article.id}`}
                className="p-4 rounded-xl border border-gray-100 bg-gray-50/60 hover:bg-gray-50 transition-colors space-y-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
                  <div className="flex items-center space-x-2">
                    <span data-testid={`news-sentiment-${article.id}`}>
                      {getSentimentBadge(article.sentiment)}
                    </span>
                    <h3 className="text-sm font-semibold text-gray-900 tracking-tight">
                      {article.title}
                    </h3>
                  </div>

                  <span className="text-[11px] font-mono text-gray-400">
                    {article.published_at || '—'}
                  </span>
                </div>

                <p className="text-xs text-gray-600 leading-relaxed">
                  {article.summary}
                </p>

                {/* Symbols, Source and Provenance */}
                <div className="pt-2 border-t border-gray-200/50 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                  {article.related_symbols && article.related_symbols.length > 0 && (
                    <div className="flex items-center space-x-1.5">
                      <Tag className="w-3 h-3 text-gray-400" />
                      <div className="flex items-center space-x-1">
                        {article.related_symbols.map((sym) => (
                          <button
                            key={sym}
                            onClick={() => onSelectSymbol(sym)}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold transition cursor-pointer ${
                              sym.toUpperCase() === selectedSymbol.toUpperCase()
                                ? 'bg-blue-600 text-white'
                                : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-100'
                            }`}
                          >
                            {sym}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center space-x-2 text-gray-400 font-mono text-[10px]">
                    <span>Source: {article.source}</span>
                    {article.is_simulated && (
                      <span className="px-1.5 py-0.2 bg-blue-50 text-blue-700 rounded">
                        Simulated
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
