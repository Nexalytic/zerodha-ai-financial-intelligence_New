from abc import ABC, abstractmethod
from typing import Dict, List
from app.schemas.market_data import NewsArticle, Quote

class BaseMarketDataProvider(ABC):
    """
    Abstract interface for market data providers.
    All implementations must return Quote instances honoring simulation flags
    and returning null/None prices for missing or unknown symbols.
    """

    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """
        Fetch a market quote for a single symbol.
        Must return Quote with current_price=None if symbol is unknown.
        """
        pass

    @abstractmethod
    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        """
        Fetch market quotes for a batch of symbols.
        """
        pass

class BaseNewsProvider(ABC):
    """
    Abstract interface for financial news providers.
    All implementations must return NewsArticle instances honoring simulation flags
    and explicit attribution.
    """

    @abstractmethod
    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> List[NewsArticle]:
        """
        Fetch news articles relevant to a list of stock symbols.
        """
        pass

    @abstractmethod
    async def get_market_news(self, limit: int = 10) -> List[NewsArticle]:
        """
        Fetch general market news headlines.
        """
        pass
