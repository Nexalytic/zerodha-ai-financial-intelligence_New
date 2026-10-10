from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from app.providers.base import BaseMarketDataProvider
from app.schemas.market_data import Quote, QuoteStatus

# Fixed reference baselines for popular Indian equities.
# Prices are fixed and deterministic; no random numbers or simulated volatility are introduced.
DEMO_INDIAN_EQUITIES = {
    "RELIANCE": {
        "name": "Reliance Industries Ltd",
        "price": Decimal("2850.50"),
        "change": Decimal("15.20"),
        "change_percent": Decimal("0.54"),
    },
    "TCS": {
        "name": "Tata Consultancy Services Ltd",
        "price": Decimal("3920.00"),
        "change": Decimal("-12.40"),
        "change_percent": Decimal("-0.32"),
    },
    "INFY": {
        "name": "Infosys Ltd",
        "price": Decimal("1520.25"),
        "change": Decimal("8.75"),
        "change_percent": Decimal("0.58"),
    },
    "HDFCBANK": {
        "name": "HDFC Bank Ltd",
        "price": Decimal("1650.00"),
        "change": Decimal("-5.50"),
        "change_percent": Decimal("-0.33"),
    },
    "ICICIBANK": {
        "name": "ICICI Bank Ltd",
        "price": Decimal("1120.00"),
        "change": Decimal("11.80"),
        "change_percent": Decimal("1.06"),
    },
    "ITC": {
        "name": "ITC Ltd",
        "price": Decimal("430.00"),
        "change": Decimal("2.10"),
        "change_percent": Decimal("0.49"),
    },
    "BHARTIARTL": {
        "name": "Bharti Airtel Ltd",
        "price": Decimal("1280.00"),
        "change": Decimal("14.00"),
        "change_percent": Decimal("1.11"),
    },
    "SBIN": {
        "name": "State Bank of India",
        "price": Decimal("760.00"),
        "change": Decimal("-3.20"),
        "change_percent": Decimal("-0.42"),
    },
    "LT": {
        "name": "Larsen & Toubro Ltd",
        "price": Decimal("3540.00"),
        "change": Decimal("22.50"),
        "change_percent": Decimal("0.64"),
    },
    "M&M": {
        "name": "Mahindra & Mahindra Ltd",
        "price": Decimal("2800.00"),
        "change": Decimal("35.00"),
        "change_percent": Decimal("1.27"),
    },
    "BAJAJ-AUTO": {
        "name": "Bajaj Auto Ltd",
        "price": Decimal("9150.00"),
        "change": Decimal("-45.00"),
        "change_percent": Decimal("-0.49"),
    },
}

class DemoMarketDataProvider(BaseMarketDataProvider):
    """
    Deterministic simulated market data provider for testing and demonstration.
    - Prices are fixed to reference Indian equity baselines.
    - Never implies simulated prices are live or real.
    - market_as_of is strictly None.
    - Unknown symbols strictly return current_price=None and QuoteStatus.UNAVAILABLE.
    """

    PROVIDER_NAME = "SIMULATED_DEMO_PROVIDER"
    DISCLAIMER = "Simulated market quote for demonstration purposes only. Not real or live market data."

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        normalized_sym = symbol.strip().upper()
        normalized_ex = exchange.strip().upper()
        now = datetime.now(timezone.utc)

        if normalized_sym in DEMO_INDIAN_EQUITIES:
            data = DEMO_INDIAN_EQUITIES[normalized_sym]
            return Quote(
                symbol=normalized_sym,
                exchange=normalized_ex,
                current_price=data["price"],
                change=data["change"],
                change_percent=data["change_percent"],
                status=QuoteStatus.AVAILABLE,
                is_simulated=True,
                source=self.PROVIDER_NAME,
                generated_at=now,
                market_as_of=None,  # Strictly None for simulated data
                cached_at=None,
                cache_hit=False,
                is_stale=False,
                disclaimer=self.DISCLAIMER,
                explanation=None,
            )

        # Unknown symbol: strictly return None for price and state UNAVAILABLE
        return Quote(
            symbol=normalized_sym,
            exchange=normalized_ex,
            current_price=None,
            change=None,
            change_percent=None,
            status=QuoteStatus.UNAVAILABLE,
            is_simulated=True,
            source=self.PROVIDER_NAME,
            generated_at=now,
            market_as_of=None,
            cached_at=None,
            cache_hit=False,
            is_stale=False,
            disclaimer=self.DISCLAIMER,
            explanation=f"Symbol '{normalized_sym}' not found in demo market universe. No price fabricated.",
        )

    async def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        quotes = {}
        for sym in symbols:
            quotes[sym.strip().upper()] = await self.get_quote(sym, exchange=exchange)
        return quotes
