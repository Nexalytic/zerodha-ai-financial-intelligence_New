import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")
VALID_EXCHANGES = {"NSE", "BSE"}


class PriceHistoryInterval(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"


class PriceHistoryPoint(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Timezone-aware UTC timestamp marking the start of the price bar/candle",
    )
    open: Decimal = Field(
        ...,
        description="Opening price for the interval. Must be strictly positive, finite Decimal.",
    )
    high: Decimal = Field(
        ...,
        description="Highest price observed in the interval. Must be strictly positive, finite Decimal.",
    )
    low: Decimal = Field(
        ...,
        description="Lowest price observed in the interval. Must be strictly positive, finite Decimal.",
    )
    close: Decimal = Field(
        ...,
        description="Closing price for the interval. Must be strictly positive, finite Decimal.",
    )
    volume: Optional[int] = Field(
        default=None,
        description="Optional trading volume during the interval. Must be non-negative integer.",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timezone_aware_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except Exception as e:
                raise ValueError(f"Invalid timestamp format: {e}")
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("Timestamp must be a datetime object or ISO-8601 string")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
        return dt.astimezone(timezone.utc)

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def validate_finite_positive_price(cls, v: Any) -> Decimal:
        if isinstance(v, bool):
            raise ValueError("Price cannot be a boolean")
        if isinstance(v, (float, int, str)):
            try:
                dec = Decimal(str(v))
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError("Invalid monetary value format")
        elif isinstance(v, Decimal):
            dec = v
        else:
            raise ValueError("Price must be a valid monetary number")

        if not dec.is_finite():
            raise ValueError("Price values must be finite numbers (not NaN or Infinity)")
        if dec <= Decimal("0"):
            raise ValueError("Price must be strictly greater than 0")

        quantized = dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if quantized <= Decimal("0"):
            raise ValueError(
                f"Price must be strictly positive after quantization to 2 decimal places (minimum 0.01, got {v})"
            )
        return quantized

    @field_validator("volume", mode="before")
    @classmethod
    def validate_volume_int(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("Volume must be an integer, not a boolean")
        if isinstance(v, float):
            if not v.is_integer():
                raise ValueError("Volume cannot be a fractional value")
            v = int(v)
        elif isinstance(v, str):
            cleaned = v.strip()
            if not cleaned.isdigit() and not (cleaned.startswith("+") and cleaned[1:].isdigit()):
                raise ValueError("Volume must be an integer string")
            v = int(cleaned)
        elif isinstance(v, Decimal):
            if v % 1 != 0:
                raise ValueError("Volume cannot be a fractional value")
            v = int(v)
        elif not isinstance(v, int):
            raise ValueError("Volume must be a valid integer")

        if v < 0:
            raise ValueError("Volume must be a non-negative integer (>= 0)")
        return v

    @model_validator(mode="after")
    def validate_ohlc_consistency(self) -> "PriceHistoryPoint":
        if self.high < self.low:
            raise ValueError(
                f"Invalid OHLC candle: high ({self.high}) cannot be less than low ({self.low})"
            )
        if self.open < self.low or self.open > self.high:
            raise ValueError(
                f"Invalid OHLC candle: open ({self.open}) must be between low ({self.low}) and high ({self.high})"
            )
        if self.close < self.low or self.close > self.high:
            raise ValueError(
                f"Invalid OHLC candle: close ({self.close}) must be between low ({self.low}) and high ({self.high})"
            )
        return self

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryResponse(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g. RELIANCE, TCS)")
    exchange: str = Field(default="NSE", description="Exchange identifier (NSE or BSE)")
    interval: PriceHistoryInterval = Field(..., description="Bar time interval (e.g. 1d, 1h)")
    points: List[PriceHistoryPoint] = Field(
        default_factory=list,
        description="Chronologically sorted price points",
    )
    total_points: int = Field(
        default=0,
        description="Total number of price points in this series",
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="Earliest timestamp in the series; null if series is empty",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="Latest timestamp in the series; null if series is empty",
    )
    is_simulated: bool = Field(
        default=True,
        description="Explicit flag indicating simulated/sample history. Never live or certified records.",
    )
    source: str = Field(
        default="SIMULATED_DEMO_PROVIDER",
        description="Provider identifier attribution",
    )
    market_as_of: Optional[datetime] = Field(
        default=None,
        description="Real exchange timestamp. Strictly null for simulated data.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this response was assembled",
    )
    disclaimer: str = Field(
        default="Simulated historical market data for demonstration purposes only. Not real or certified exchange records.",
        description="Informational disclaimer",
    )

    @field_validator("symbol")
    @classmethod
    def validate_and_normalize_symbol(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not SYMBOL_REGEX.match(cleaned):
            raise ValueError("Symbol must be 1-20 alphanumeric characters, &, or -")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_EXCHANGES:
            raise ValueError(f"Exchange must be one of {sorted(VALID_EXCHANGES)}")
        return cleaned

    @field_validator("market_as_of", mode="before")
    @classmethod
    def validate_market_as_of(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except Exception as e:
                raise ValueError(f"Invalid market_as_of timestamp format: {e}")
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("market_as_of must be a datetime object or ISO-8601 string")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("market_as_of must be timezone-aware (e.g. UTC)")
        return dt.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_chronology_and_bounds(self) -> "PriceHistoryResponse":
        if self.is_simulated and self.market_as_of is not None:
            raise ValueError("market_as_of must be null when is_simulated is True")

        self.total_points = len(self.points)

        if not self.points:
            self.start_time = None
            self.end_time = None
            return self

        for i in range(len(self.points) - 1):
            t_curr = self.points[i].timestamp
            t_next = self.points[i + 1].timestamp
            if t_curr >= t_next:
                if t_curr == t_next:
                    raise ValueError(
                        f"Duplicate timestamp in price history points: {t_curr.isoformat()}"
                    )
                raise ValueError(
                    f"Price history points must be in strictly ascending chronological order. "
                    f"Point {i} ({t_curr.isoformat()}) >= Point {i + 1} ({t_next.isoformat()})"
                )

        self.start_time = self.points[0].timestamp
        self.end_time = self.points[-1].timestamp
        return self

    model_config = ConfigDict(from_attributes=True)
