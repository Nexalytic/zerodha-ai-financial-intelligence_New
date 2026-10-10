import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger, sanitize_log_message
from app.providers.base import BaseMarketDataProvider
from app.schemas.market_data import Quote, QuoteStatus


class AlphaVantageMarketDataProvider(BaseMarketDataProvider):
    """
    Market data provider integrating Alpha Vantage GLOBAL_QUOTE API.
    - Accurately maps Alpha Vantage quote fields into Quote schema.
    - Never labels live/provider quotes as simulated (is_simulated=False).
    - Accurately preserves observation timestamps (market_as_of) from latest trading day.
    - Handles missing API keys, rate-limit messages, unknown symbols, and malformed
      responses without inventing prices (strictly returns current_price=None).
    - Masks and redacts API keys and URLs across logs, exceptions, and explanations.
    """

    PROVIDER_NAME = "ALPHA_VANTAGE"
    IS_SIMULATED = False
    DISCLAIMER = "Market data provided by Alpha Vantage. For informational purposes only."

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.ALPHA_VANTAGE_API_KEY
        self.base_url = (base_url or settings.ALPHA_VANTAGE_BASE_URL).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._external_client = http_client
        self._owned_client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._owned_client

    async def aclose(self) -> None:
        """Close internally managed HTTP client if open."""
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()

    def _to_alpha_vantage_symbol(self, symbol: str, exchange: str) -> str:
        """
        Format ticker symbol for Alpha Vantage querying.
        If symbol already contains an exchange suffix (e.g. 'RELIANCE.BSE'), keep as-is.
        If exchange is BSE or NSE and not yet in symbol, append exchange suffix.
        """
        clean_sym = symbol.strip().upper()
        if "." in clean_sym:
            return clean_sym

        clean_ex = exchange.strip().upper() if exchange else ""
        if clean_ex in ("BSE", "NSE"):
            return f"{clean_sym}.{clean_ex}"

        return clean_sym

    def _sanitize(self, text: str) -> str:
        """Sanitize any message or URL to prevent leaking API keys."""
        return sanitize_log_message(text, secret=self.api_key)

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """
        Fetch quote for a single symbol from Alpha Vantage.
        Returns Quote with current_price=None if symbol is unknown, unpriced,
        or on error / rate-limit.
        """
        norm_sym = symbol.strip().upper()
        norm_ex = exchange.strip().upper() if exchange else "NSE"
        now = datetime.now(timezone.utc)

        # 1. Validate API key presence
        if (
            not self.api_key
            or not self.api_key.strip()
            or self.api_key.strip().lower() in ("demo", "none", "null")
        ):
            logger.warning(
                "Alpha Vantage API key is unconfigured or set to placeholder for symbol %s. Returning UNAVAILABLE.",
                norm_sym,
            )
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage API key is not configured. Price unavailable.",
            )

        av_symbol = self._to_alpha_vantage_symbol(norm_sym, norm_ex)
        client = self._get_client()

        # 2. Execute HTTP request with credential-safe error isolation
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": av_symbol,
                "apikey": self.api_key,
            }
            response = await client.get(self.base_url, params=params)
        except (httpx.TimeoutException, httpx.RequestError) as net_err:
            err_type = net_err.__class__.__name__
            logger.warning(
                "Network error querying Alpha Vantage for symbol %s: %s",
                norm_sym,
                err_type,
            )
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=f"Network error querying Alpha Vantage ({err_type}). Price unavailable.",
            )
        except Exception as exc:
            err_type = exc.__class__.__name__
            logger.warning(
                "Unexpected error querying Alpha Vantage for symbol %s: %s",
                norm_sym,
                err_type,
            )
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Unexpected error querying Alpha Vantage. Price unavailable.",
            )

        # 3. Handle non-200 HTTP responses
        if response.status_code != 200:
            logger.warning(
                "Alpha Vantage returned HTTP status %s for symbol %s",
                response.status_code,
                norm_sym,
            )
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=f"Alpha Vantage returned HTTP {response.status_code}. Price unavailable.",
            )

        # 4. Parse JSON payload
        try:
            payload = response.json()
        except Exception:
            logger.warning("Alpha Vantage returned non-JSON response for symbol %s", norm_sym)
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage returned non-JSON payload. Price unavailable.",
            )

        # 5. Check rate-limit notices ("Note" or "Information")
        if "Note" in payload or "Information" in payload:
            logger.warning("Alpha Vantage rate limit message encountered for symbol %s", norm_sym)
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage API rate limit exceeded. Price unavailable.",
            )

        # 6. Check provider error message ("Error Message")
        if "Error Message" in payload:
            logger.warning("Alpha Vantage returned error message for symbol %s", norm_sym)
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage returned an API error. Price unavailable.",
            )

        # 6b. Check for empty response payload
        if not payload:
            logger.warning("Alpha Vantage returned an empty response payload for symbol %s", norm_sym)
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage returned an empty response payload. Price unavailable.",
            )

        # 6c. Check for unrecognized response structure without "Global Quote"
        if "Global Quote" not in payload:
            logger.warning(
                "Alpha Vantage returned unrecognized response structure for symbol %s: %s",
                norm_sym,
                list(payload.keys()) if isinstance(payload, dict) else type(payload),
            )
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation="Alpha Vantage returned an unrecognized response without quote data. Price unavailable.",
            )

        # 7. Check for empty "Global Quote" (explicit symbol not found)
        gq = payload.get("Global Quote")
        if not gq or not isinstance(gq, dict):
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=f"Symbol '{norm_sym}' not found in Alpha Vantage. No price fabricated.",
            )

        # 8. Parse price field
        raw_price = gq.get("05. price")
        if not raw_price:
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.UNAVAILABLE,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=f"Price data missing for symbol '{norm_sym}'. No price fabricated.",
            )

        try:
            current_price = Decimal(str(raw_price).strip())
        except Exception:
            return Quote(
                symbol=norm_sym,
                exchange=norm_ex,
                current_price=None,
                change=None,
                change_percent=None,
                status=QuoteStatus.ERROR,
                is_simulated=False,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=f"Malformed price data for symbol '{norm_sym}'. Price unavailable.",
            )

        # 9. Parse optional fields: change, change_percent, market_as_of
        change_val: Optional[Decimal] = None
        raw_change = gq.get("09. change")
        if raw_change is not None:
            try:
                change_val = Decimal(str(raw_change).strip())
            except Exception:
                change_val = None

        change_pct_val: Optional[Decimal] = None
        raw_change_pct = gq.get("10. change percent")
        if raw_change_pct is not None:
            try:
                clean_pct = str(raw_change_pct).strip().rstrip("%").strip()
                change_pct_val = Decimal(clean_pct)
            except Exception:
                change_pct_val = None

        market_as_of: Optional[datetime] = None
        trading_day_str = gq.get("07. latest trading day")
        if trading_day_str:
            try:
                market_as_of = datetime.strptime(
                    str(trading_day_str).strip(), "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                market_as_of = None

        # 10. Construct valid Quote with accurate provenance
        return Quote(
            symbol=norm_sym,
            exchange=norm_ex,
            current_price=current_price,
            change=change_val,
            change_percent=change_pct_val,
            status=QuoteStatus.AVAILABLE,
            is_simulated=False,
            source=self.PROVIDER_NAME,
            generated_at=now,
            market_as_of=market_as_of,
            cached_at=None,
            cache_hit=False,
            is_stale=False,
            disclaimer=self.DISCLAIMER,
            explanation=None,
        )

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        """Fetch quotes for a batch of symbols."""
        quotes = {}
        for sym in symbols:
            cleaned = sym.strip().upper()
            if cleaned:
                quotes[cleaned] = await self.get_quote(cleaned, exchange=exchange)
        return quotes
