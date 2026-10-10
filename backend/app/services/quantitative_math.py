from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any, List, Optional, Sequence

# Standard precision for quantitative financial calculations
DECIMAL_CALCULATION_PRECISION = 28

MIN_OBSERVATIONS_FOR_VOLATILITY = 10
MIN_OBSERVATIONS_FOR_BETA = 10
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def validate_finite_positive_price(val: Any, name: str = "price") -> Decimal:
    """
    Validates that a price value is a finite, strictly positive Decimal.
    Rejects booleans, non-finite values (NaN, Infinity), zero, and negative values.
    Raises ValueError on any invalid input.
    """
    if isinstance(val, bool):
        raise ValueError(f"{name} cannot be a boolean")

    if isinstance(val, (int, float, str)):
        try:
            dec = Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"Invalid monetary format for {name}: {e}")
    elif isinstance(val, Decimal):
        dec = val
    else:
        raise ValueError(f"{name} must be a valid numeric type or string")

    if not dec.is_finite():
        raise ValueError(f"{name} must be a finite number (not NaN or Infinity)")
    if dec <= Decimal("0"):
        raise ValueError(f"{name} must be strictly greater than zero (got {dec})")

    return dec


def validate_finite_return(val: Any, name: str = "return") -> Decimal:
    """
    Validates that a return value is a finite Decimal.
    Rejects booleans and non-finite values (NaN, Infinity).
    """
    if isinstance(val, bool):
        raise ValueError(f"{name} cannot be a boolean")

    if isinstance(val, (int, float, str)):
        try:
            dec = Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"Invalid format for {name}: {e}")
    elif isinstance(val, Decimal):
        dec = val
    else:
        raise ValueError(f"{name} must be a valid numeric type or string")

    if not dec.is_finite():
        raise ValueError(f"{name} must be a finite number (not NaN or Infinity)")

    return dec


def extract_and_validate_prices(
    prices: Sequence[Any],
) -> List[Decimal]:
    """
    Extracts and validates a sequence of prices.
    Accepts:
    - Sequence of numeric/Decimal price levels.
    - Sequence of objects with a .timestamp and .close attribute (e.g. PriceHistoryPoint).
    - Sequence of (datetime, price) tuples.

    Enforces:
    - If timestamps are provided, checks strictly ascending chronological order without duplicates.
      Raises ValueError if out-of-order or duplicate timestamps are encountered.
    - Every price level must be finite and strictly positive (> 0).
    """
    if not isinstance(prices, (list, tuple)):
        raise ValueError("Prices must be provided as a sequence (list or tuple)")

    if len(prices) == 0:
        return []

    validated_prices: List[Decimal] = []
    has_timestamps = False
    last_timestamp: Optional[datetime] = None

    for i, item in enumerate(prices):
        dt: Optional[datetime] = None
        raw_price: Any = None

        if hasattr(item, "timestamp") and hasattr(item, "close"):
            dt = getattr(item, "timestamp")
            raw_price = getattr(item, "close")
            has_timestamps = True
        elif isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[0], datetime):
            dt = item[0]
            raw_price = item[1]
            has_timestamps = True
        else:
            raw_price = item

        # Verify chronological order if timestamps are present
        if has_timestamps and dt is not None:
            # Normalize to UTC for reliable comparison
            if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
                norm_dt = dt.astimezone(timezone.utc)
            else:
                raise ValueError(
                    f"Price at index {i} has naive timestamp; all timestamps must be timezone-aware"
                )

            if last_timestamp is not None:
                if norm_dt == last_timestamp:
                    raise ValueError(
                        f"Duplicate timestamp encountered at index {i} ({norm_dt.isoformat()}). "
                        f"Prices must not contain duplicate timestamps."
                    )
                if norm_dt < last_timestamp:
                    raise ValueError(
                        f"Out-of-order timestamp encountered at index {i} ({norm_dt.isoformat()} < "
                        f"{last_timestamp.isoformat()}). Prices must be strictly ascending chronologically."
                    )
            last_timestamp = norm_dt

        price_dec = validate_finite_positive_price(raw_price, name=f"Price at index {i}")
        validated_prices.append(price_dec)

    return validated_prices


def calculate_discrete_returns(prices: Sequence[Any]) -> List[Decimal]:
    """
    Calculates discrete simple daily returns from a chronological series of prices:
    R_t = (P_t - P_{t-1}) / P_{t-1} for t = 1, ..., N.

    Preserves 28-digit Decimal precision isolated via localcontext() for downstream
    statistical aggregations without altering the caller's ambient Decimal context.
    Raises ValueError on invalid, negative, non-finite, duplicate, or out-of-order prices.
    Returns empty list if fewer than 2 price points are provided.
    """
    validated = extract_and_validate_prices(prices)
    if len(validated) < 2:
        return []

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        returns: List[Decimal] = []
        for i in range(1, len(validated)):
            p_prev = validated[i - 1]
            p_curr = validated[i]
            r = (p_curr - p_prev) / p_prev
            returns.append(r)

    return returns


def calculate_sample_volatility(
    prices: Sequence[Any],
    trading_days: int = 252,
) -> Optional[Decimal]:
    """
    Calculates annualized historical volatility using:
    - Discrete simple returns.
    - Sample variance with Bessel's correction (N - 1 denominator).
    - Annualization factor sqrt(trading_days) (default 252 for Indian equities).
    - Native Decimal.sqrt() with 28-digit precision isolated via localcontext().
    - Output quantized to 2 decimal places (ROUND_HALF_UP).

    Data requirements:
    - Requires at least 10 return observations (meaning at least 11 price points).
    - Returns None if observations < 10 (insufficient data).
    - If all returns are identical / prices are flat, returns Decimal("0.00").
    - Raises ValueError on invalid inputs (negative prices, NaNs, duplicate/out-of-order timestamps).
    """
    if trading_days <= 0:
        raise ValueError("trading_days must be a positive integer (typically 252)")

    returns = calculate_discrete_returns(prices)
    n = len(returns)
    if n < MIN_OBSERVATIONS_FOR_VOLATILITY:
        return None  # Insufficient data

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION

        # 1. Sample mean return
        mean_r = sum(returns) / Decimal(n)

        # 2. Sample variance with Bessel's correction (N - 1)
        variance_sum = sum((r - mean_r) ** 2 for r in returns)
        sample_var = variance_sum / Decimal(n - 1)

        if sample_var <= Decimal("0"):
            return Decimal("0.00")

        # 3. Daily standard deviation using native Decimal.sqrt()
        daily_std = sample_var.sqrt()

        # 4. Annualization factor sqrt(252)
        annualization_factor = Decimal(trading_days).sqrt()

        # 5. Annualized volatility expressed as percentage (%)
        ann_vol = daily_std * annualization_factor * Decimal("100")
        return ann_vol.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_maximum_drawdown(prices: Sequence[Any]) -> Optional[Decimal]:
    """
    Calculates the Maximum Drawdown (MDD) as a positive percentage decline from peak:
    DD_t = (Peak_t - P_t) / Peak_t * 100
    MDD = max(DD_t)

    Properties:
    - Requires at least 1 price point. Returns None if price sequence is empty.
    - Guaranteed >= 0.00%. A strictly rising series returns Decimal("0.00").
    - Calculations isolated with 28-digit precision via localcontext().
    - Output quantized to 2 decimal places (ROUND_HALF_UP).
    - Raises ValueError on invalid inputs (non-positive prices, NaNs, out-of-order timestamps).
    """
    validated = extract_and_validate_prices(prices)
    if len(validated) == 0:
        return None

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION

        peak = validated[0]
        max_dd = Decimal("0.00")

        for p in validated:
            if p > peak:
                peak = p
            else:
                dd = ((peak - p) / peak) * Decimal("100")
                if dd > max_dd:
                    max_dd = dd

        return max_dd.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_paired_beta(
    portfolio_returns: Sequence[Any],
    benchmark_returns: Sequence[Any],
) -> Optional[Decimal]:
    """
    Calculates systematic risk beta:
    Beta = Cov(R_p, R_b) / Var(R_b)

    Requirements:
    - Requires equal-length return series representing identical chronological intervals.
      Raises ValueError if sequence lengths do not match or if elements are non-finite.
    - Requires at least 10 paired observations. Returns None if len < 10 (insufficient data).
    - Requires non-zero benchmark variance. Returns None if benchmark variance is zero.
    - Calculations isolated with 28-digit precision via localcontext().
    - Output quantized to 4 decimal places (ROUND_HALF_UP).
    """
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError(
            f"Portfolio returns ({len(portfolio_returns)}) and benchmark returns "
            f"({len(benchmark_returns)}) must have identical lengths"
        )

    n = len(portfolio_returns)
    if n < MIN_OBSERVATIONS_FOR_BETA:
        return None  # Insufficient observations

    p_rets = [validate_finite_return(r, f"Portfolio return at index {i}") for i, r in enumerate(portfolio_returns)]
    b_rets = [validate_finite_return(r, f"Benchmark return at index {i}") for i, r in enumerate(benchmark_returns)]

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION

        mean_p = sum(p_rets) / Decimal(n)
        mean_b = sum(b_rets) / Decimal(n)

        # Benchmark sample variance with Bessel's correction
        var_b_sum = sum((b - mean_b) ** 2 for b in b_rets)
        sample_var_b = var_b_sum / Decimal(n - 1)

        # Zero benchmark variance guard
        if sample_var_b <= Decimal("0"):
            return None

        # Sample covariance with Bessel's correction
        cov_sum = sum((p_rets[i] - mean_p) * (b_rets[i] - mean_b) for i in range(n))
        sample_cov = cov_sum / Decimal(n - 1)

        beta = sample_cov / sample_var_b
        return beta.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def calculate_relative_return(
    portfolio_return: Any,
    benchmark_return: Any,
) -> Decimal:
    """
    Calculates relative performance (excess return over benchmark) in percentage points:
    Relative Return (%) = Portfolio Return (%) - Benchmark Return (%)

    Contract & Units:
    - Both portfolio_return and benchmark_return must be expressed in percentage points
      (e.g., Decimal("15.50") for 15.50%, Decimal("10.25") for 10.25%), NOT fractional returns
      (e.g., 0.1550).
    - Both inputs must be finite numbers (booleans, NaN, and Infinity are strictly rejected).
    - The inputs are assumed to represent comparable investment horizons.
    - Output is the percentage-point difference, quantized to 2 decimal places using ROUND_HALF_UP.
    - Fractional inputs are NOT silently converted; callers are expected to supply percentage points
      directly consistent with benchmark_relative_return_percent.
    """
    p_dec = validate_finite_return(portfolio_return, "portfolio_return")
    b_dec = validate_finite_return(benchmark_return, "benchmark_return")

    with localcontext() as ctx:
        ctx.prec = DECIMAL_CALCULATION_PRECISION
        rel = p_dec - b_dec
        return rel.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
