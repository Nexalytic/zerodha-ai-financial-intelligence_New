from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.price_history import (
    PriceHistoryInterval,
    PriceHistoryPoint,
    PriceHistoryResponse,
)


def test_valid_price_history_point():
    """Verifies that a valid OHLC point parses correctly with timezone-aware timestamp and Decimal prices."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    point = PriceHistoryPoint(
        timestamp=now_utc,
        open="2450.50",
        high="2480.00",
        low="2445.25",
        close="2475.10",
        volume=150000,
    )
    assert point.timestamp == now_utc
    assert point.open == Decimal("2450.50")
    assert point.high == Decimal("2480.00")
    assert point.low == Decimal("2445.25")
    assert point.close == Decimal("2475.10")
    assert point.volume == 150000


def test_price_history_point_round_half_up_quantization():
    """Verifies ROUND_HALF_UP quantization for prices with fractional cents."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    point = PriceHistoryPoint(
        timestamp=now_utc,
        open="100.555",  # rounds to 100.56
        high="105.000",
        low="100.000",
        close="102.554",  # rounds to 102.55
    )
    assert point.open == Decimal("100.56")
    assert point.close == Decimal("102.55")


def test_price_history_point_rejects_quantization_to_zero():
    """Verifies that positive prices that would quantize to 0.00 are strictly rejected."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    with pytest.raises(ValidationError) as exc:
        PriceHistoryPoint(
            timestamp=now_utc,
            open="0.001",  # quantizes to 0.00
            high="10.00",
            low="0.001",
            close="5.00",
        )
    assert "strictly positive after quantization" in str(exc.value)


def test_price_history_point_rejects_zero_and_negative_prices():
    """Verifies that zero and negative prices are rejected."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc,
            open="0.00",
            high="10.00",
            low="0.00",
            close="5.00",
        )

    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc,
            open="10.00",
            high="15.00",
            low="-5.00",
            close="12.00",
        )


def test_price_history_point_rejects_boolean_and_non_finite_prices():
    """Verifies that booleans and non-finite numbers (NaN, inf) are rejected."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc,
            open=True,
            high=100,
            low=50,
            close=75,
        )

    for bad_val in ["nan", "inf", "-inf", float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            PriceHistoryPoint(
                timestamp=now_utc,
                open=bad_val,
                high=100,
                low=50,
                close=75,
            )


def test_price_history_point_requires_timezone_aware_timestamp():
    """Verifies that naive timestamps are rejected and offset-aware timestamps are normalized to UTC."""
    naive_dt = datetime(2026, 1, 15, 9, 15)
    with pytest.raises(ValidationError) as exc:
        PriceHistoryPoint(
            timestamp=naive_dt,
            open="100.00",
            high="110.00",
            low="95.00",
            close="105.00",
        )
    assert "timezone-aware" in str(exc.value)

    # Offset-aware timestamp should be converted to UTC
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_dt = datetime(2026, 1, 15, 14, 45, tzinfo=ist_tz)
    point = PriceHistoryPoint(
        timestamp=ist_dt,
        open="100.00",
        high="110.00",
        low="95.00",
        close="105.00",
    )
    assert point.timestamp.tzinfo == timezone.utc
    assert point.timestamp.hour == 9
    assert point.timestamp.minute == 15


def test_price_history_point_volume_validation():
    """Verifies volume constraints: non-negative integer, rejects fractional or boolean."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)

    # Valid volumes
    p1 = PriceHistoryPoint(
        timestamp=now_utc, open="10", high="15", low="8", close="12", volume=0
    )
    assert p1.volume == 0

    p2 = PriceHistoryPoint(
        timestamp=now_utc, open="10", high="15", low="8", close="12", volume=None
    )
    assert p2.volume is None

    # Rejects negative
    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc, open="10", high="15", low="8", close="12", volume=-100
        )

    # Rejects boolean
    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc, open="10", high="15", low="8", close="12", volume=True
        )

    # Rejects fractional
    with pytest.raises(ValidationError):
        PriceHistoryPoint(
            timestamp=now_utc, open="10", high="15", low="8", close="12", volume=500.5
        )


def test_ohlc_consistency_checks():
    """Verifies that high >= low, low <= open <= high, and low <= close <= high are enforced."""
    now_utc = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)

    # high < low
    with pytest.raises(ValidationError) as exc1:
        PriceHistoryPoint(
            timestamp=now_utc, open="100", high="90", low="95", close="92"
        )
    assert "high" in str(exc1.value) and "low" in str(exc1.value)

    # open > high
    with pytest.raises(ValidationError) as exc2:
        PriceHistoryPoint(
            timestamp=now_utc, open="110", high="105", low="95", close="100"
        )
    assert "open" in str(exc2.value)

    # open < low
    with pytest.raises(ValidationError) as exc3:
        PriceHistoryPoint(
            timestamp=now_utc, open="90", high="105", low="95", close="100"
        )
    assert "open" in str(exc3.value)

    # close > high
    with pytest.raises(ValidationError) as exc4:
        PriceHistoryPoint(
            timestamp=now_utc, open="100", high="105", low="95", close="110"
        )
    assert "close" in str(exc4.value)

    # close < low
    with pytest.raises(ValidationError) as exc5:
        PriceHistoryPoint(
            timestamp=now_utc, open="100", high="105", low="95", close="90"
        )
    assert "close" in str(exc5.value)


def test_price_history_series_chronological_ordering():
    """Verifies ascending order enforcement, bounds computation, and rejection of out-of-order points."""
    t1 = datetime(2026, 1, 15, 9, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 15, 9, 45, tzinfo=timezone.utc)

    p1 = PriceHistoryPoint(timestamp=t1, open="100", high="105", low="98", close="102")
    p2 = PriceHistoryPoint(timestamp=t2, open="102", high="108", low="101", close="106")
    p3 = PriceHistoryPoint(timestamp=t3, open="106", high="110", low="104", close="109")

    # Valid series
    series = PriceHistoryResponse(
        symbol="infy",
        exchange="nse",
        interval=PriceHistoryInterval.FIFTEEN_MINUTES,
        points=[p1, p2, p3],
    )
    assert series.symbol == "INFY"
    assert series.exchange == "NSE"
    assert series.total_points == 3
    assert series.start_time == t1
    assert series.end_time == t3

    # Out of order
    with pytest.raises(ValidationError) as exc_order:
        PriceHistoryResponse(
            symbol="INFY",
            interval=PriceHistoryInterval.FIFTEEN_MINUTES,
            points=[p2, p1, p3],
        )
    assert "strictly ascending chronological order" in str(exc_order.value)

    # Duplicate timestamps
    p2_dup = PriceHistoryPoint(timestamp=t2, open="102", high="108", low="101", close="106")
    with pytest.raises(ValidationError) as exc_dup:
        PriceHistoryResponse(
            symbol="INFY",
            interval=PriceHistoryInterval.FIFTEEN_MINUTES,
            points=[p1, p2, p2_dup],
        )
    assert "Duplicate timestamp" in str(exc_dup.value)


def test_price_history_series_empty_points():
    """Verifies behavior for empty series container."""
    series = PriceHistoryResponse(
        symbol="TCS",
        interval=PriceHistoryInterval.ONE_DAY,
        points=[],
    )
    assert series.total_points == 0
    assert series.start_time is None
    assert series.end_time is None


def test_price_history_simulation_and_provenance_rules():
    """Verifies that simulated series requires market_as_of=None and carries proper disclaimers."""
    series = PriceHistoryResponse(
        symbol="RELIANCE",
        interval=PriceHistoryInterval.ONE_DAY,
    )
    assert series.is_simulated is True
    assert series.source == "SIMULATED_DEMO_PROVIDER"
    assert series.market_as_of is None
    assert "Simulated historical market data" in series.disclaimer

    # market_as_of must not be provided when is_simulated is True
    with pytest.raises(ValidationError) as exc:
        PriceHistoryResponse(
            symbol="RELIANCE",
            interval=PriceHistoryInterval.ONE_DAY,
            is_simulated=True,
            market_as_of=datetime.now(timezone.utc),
        )
    assert "market_as_of must be null when is_simulated is True" in str(exc.value)


def test_price_history_symbol_and_interval_validation():
    """Verifies symbol format and interval enum values."""
    with pytest.raises(ValidationError):
        PriceHistoryResponse(
            symbol="BAD$SYMBOL",
            interval=PriceHistoryInterval.ONE_DAY,
        )

    with pytest.raises(ValidationError):
        PriceHistoryResponse(
            symbol="TCS",
            exchange="NASDAQ",  # only NSE, BSE allowed
            interval=PriceHistoryInterval.ONE_DAY,
        )

    with pytest.raises(ValidationError):
        PriceHistoryResponse(
            symbol="TCS",
            interval="invalid_interval",
        )
