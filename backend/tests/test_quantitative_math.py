import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List

from app.schemas.price_history import PriceHistoryPoint
from app.schemas.analytics import HistoricalRiskMetrics
from app.services.quantitative_math import (
    calculate_discrete_returns,
    calculate_sample_volatility,
    calculate_maximum_drawdown,
    calculate_paired_beta,
    calculate_relative_return,
    validate_finite_positive_price,
    validate_finite_return,
    extract_and_validate_prices,
)


# Standard 11-price fixture producing 10 discrete returns
FIXTURE_11_PRICES = [
    Decimal("100.00"),
    Decimal("102.00"),
    Decimal("101.00"),
    Decimal("105.00"),
    Decimal("104.00"),
    Decimal("108.00"),
    Decimal("107.00"),
    Decimal("110.00"),
    Decimal("108.00"),
    Decimal("112.00"),
    Decimal("115.00"),
]


def test_fixture_discrete_returns():
    """Verify exact discrete simple returns from the 11-price fixture."""
    returns = calculate_discrete_returns(FIXTURE_11_PRICES)
    assert len(returns) == 10
    # Expected discrete returns:
    # 0: (102 - 100) / 100 = 0.02
    # 1: (101 - 102) / 102 = -1 / 102
    # 2: (105 - 101) / 101 = 4 / 101
    # 3: (104 - 105) / 105 = -1 / 105
    # 4: (108 - 104) / 104 = 4 / 104
    # 5: (107 - 108) / 108 = -1 / 108
    # 6: (110 - 107) / 107 = 3 / 107
    # 7: (108 - 110) / 110 = -2 / 110
    # 8: (112 - 108) / 108 = 4 / 108
    # 9: (115 - 112) / 112 = 3 / 112
    assert returns[0] == Decimal("0.02")
    assert returns[1] == Decimal("-1") / Decimal("102")
    assert returns[7] == Decimal("-2") / Decimal("110")


def test_fixture_annualized_volatility_independently_verified():
    """
    Verify annualized sample volatility on the 11-price fixture.
    10 returns, Bessel's correction (N-1 = 9), trading_days=252.
    Independently calculated: ~36.95%.
    """
    vol = calculate_sample_volatility(FIXTURE_11_PRICES, trading_days=252)
    assert vol is not None
    assert vol == Decimal("36.95")


def test_fixture_maximum_drawdown_independently_verified():
    """
    Verify maximum drawdown on the 11-price fixture.
    Peak of 110.00 drops to 108.00 (step 7 to 8): (110 - 108) / 110 * 100 = 1.81818...% -> 1.82%.
    """
    mdd = calculate_maximum_drawdown(FIXTURE_11_PRICES)
    assert mdd is not None
    assert mdd == Decimal("1.82")


def test_maximum_drawdown_scenarios():
    """Verify maximum drawdown across diverse chronological price paths."""
    # Strictly rising prices -> 0.00% drawdown
    rising = [Decimal("100.00"), Decimal("105.00"), Decimal("110.00"), Decimal("120.00")]
    assert calculate_maximum_drawdown(rising) == Decimal("0.00")

    # Flat prices -> 0.00% drawdown
    flat = [Decimal("100.00"), Decimal("100.00"), Decimal("100.00")]
    assert calculate_maximum_drawdown(flat) == Decimal("0.00")

    # Major peak-to-trough: 100 -> 150 -> 90 -> 120 (peak 150, trough 90 = 40.00%)
    drop = [Decimal("100.00"), Decimal("150.00"), Decimal("90.00"), Decimal("120.00")]
    assert calculate_maximum_drawdown(drop) == Decimal("40.00")

    # Multiple pullbacks: Peak 100 -> 50 (50%), then rallies to 80 -> drops to 60 (25% from 80).
    # MDD is 50.00% from initial peak.
    multi_drop = [Decimal("100.00"), Decimal("50.00"), Decimal("80.00"), Decimal("60.00")]
    assert calculate_maximum_drawdown(multi_drop) == Decimal("50.00")

    # Single price point -> 0.00%
    assert calculate_maximum_drawdown([Decimal("100.00")]) == Decimal("0.00")

    # Empty sequence -> None
    assert calculate_maximum_drawdown([]) is None


def test_volatility_insufficient_observations():
    """Verify that fewer than 10 return observations returns None."""
    # 0 prices
    assert calculate_sample_volatility([]) is None

    # 1 price -> 0 returns
    assert calculate_sample_volatility([Decimal("100.00")]) is None

    # 10 prices -> 9 returns (strictly below minimum of 10)
    nine_returns = FIXTURE_11_PRICES[:10]
    assert calculate_sample_volatility(nine_returns) is None

    # 11 prices -> 10 returns (meets threshold)
    assert calculate_sample_volatility(FIXTURE_11_PRICES) is not None


def test_volatility_flat_prices():
    """Flat prices produce 0.00% volatility."""
    flat_11 = [Decimal("150.00")] * 11
    vol = calculate_sample_volatility(flat_11)
    assert vol == Decimal("0.00")


def test_volatility_trading_days_validation():
    """Verify trading_days validation."""
    with pytest.raises(ValueError, match="trading_days must be a positive integer"):
        calculate_sample_volatility(FIXTURE_11_PRICES, trading_days=0)

    with pytest.raises(ValueError, match="trading_days must be a positive integer"):
        calculate_sample_volatility(FIXTURE_11_PRICES, trading_days=-10)

    # 365 trading days yields higher annualized figure than 252
    vol_252 = calculate_sample_volatility(FIXTURE_11_PRICES, trading_days=252)
    vol_365 = calculate_sample_volatility(FIXTURE_11_PRICES, trading_days=365)
    assert vol_365 > vol_252


def test_extract_and_validate_prices_with_price_history_points():
    """Verify extract_and_validate_prices accepts PriceHistoryPoint objects."""
    base_dt = datetime(2025, 1, 1, 9, 15, tzinfo=timezone.utc)
    points = [
        PriceHistoryPoint(
            timestamp=base_dt + timedelta(days=i),
            open=FIXTURE_11_PRICES[i],
            high=FIXTURE_11_PRICES[i] + Decimal("1.00"),
            low=FIXTURE_11_PRICES[i] - Decimal("1.00"),
            close=FIXTURE_11_PRICES[i],
            volume=1000,
        )
        for i in range(len(FIXTURE_11_PRICES))
    ]

    vol = calculate_sample_volatility(points)
    assert vol == Decimal("36.95")

    mdd = calculate_maximum_drawdown(points)
    assert mdd == Decimal("1.82")


def test_extract_and_validate_prices_with_datetime_tuples():
    """Verify extract_and_validate_prices accepts (datetime, price) tuples."""
    base_dt = datetime(2025, 1, 1, 9, 15, tzinfo=timezone.utc)
    tuples = [
        (base_dt + timedelta(days=i), FIXTURE_11_PRICES[i])
        for i in range(len(FIXTURE_11_PRICES))
    ]

    vol = calculate_sample_volatility(tuples)
    assert vol == Decimal("36.95")


def test_chronological_ordering_and_duplicate_rejection():
    """Verify strict chronological validation when timestamps are present."""
    base_dt = datetime(2025, 1, 1, 9, 15, tzinfo=timezone.utc)

    # Duplicate timestamp
    dup_tuples = [
        (base_dt, Decimal("100.00")),
        (base_dt, Decimal("102.00")),
    ]
    with pytest.raises(ValueError, match="Duplicate timestamp encountered"):
        extract_and_validate_prices(dup_tuples)

    # Out-of-order timestamp
    out_of_order = [
        (base_dt + timedelta(days=1), Decimal("100.00")),
        (base_dt, Decimal("102.00")),
    ]
    with pytest.raises(ValueError, match="Out-of-order timestamp encountered"):
        extract_and_validate_prices(out_of_order)

    # Naive timestamp
    naive_dt = datetime(2025, 1, 1, 9, 15)  # no tzinfo
    naive_tuples = [
        (naive_dt, Decimal("100.00")),
        (naive_dt + timedelta(days=1), Decimal("102.00")),
    ]
    with pytest.raises(ValueError, match="all timestamps must be timezone-aware"):
        extract_and_validate_prices(naive_tuples)


def test_price_validation_rejects_invalid_values():
    """Verify that zero, negative, boolean, and non-finite prices raise ValueError."""
    # Zero price
    with pytest.raises(ValueError, match="must be strictly greater than zero"):
        validate_finite_positive_price(Decimal("0.00"))

    # Negative price
    with pytest.raises(ValueError, match="must be strictly greater than zero"):
        validate_finite_positive_price(Decimal("-10.00"))

    # Boolean
    with pytest.raises(ValueError, match="cannot be a boolean"):
        validate_finite_positive_price(True)
    with pytest.raises(ValueError, match="cannot be a boolean"):
        validate_finite_positive_price(False)

    # NaN and Infinity
    with pytest.raises(ValueError, match="must be a finite number"):
        validate_finite_positive_price(Decimal("NaN"))
    with pytest.raises(ValueError, match="must be a finite number"):
        validate_finite_positive_price(Decimal("Infinity"))

    # Non-sequence passed to extract_and_validate_prices
    with pytest.raises(ValueError, match="must be provided as a sequence"):
        extract_and_validate_prices("not-a-list")  # type: ignore


def test_paired_beta_calculation():
    """Verify paired beta calculation across distinct relationships."""
    # Benchmark returns (10 returns)
    b_rets = [
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.015"),
        Decimal("-0.005"),
        Decimal("0.025"),
        Decimal("-0.01"),
        Decimal("0.03"),
        Decimal("-0.015"),
        Decimal("0.02"),
        Decimal("-0.005"),
    ]

    # Portfolio returns = 2 * Benchmark returns -> Beta should be exactly 2.0000
    p_rets_2x = [b * Decimal("2") for b in b_rets]
    beta_2x = calculate_paired_beta(p_rets_2x, b_rets)
    assert beta_2x == Decimal("2.0000")

    # Portfolio returns = 1 * Benchmark returns -> Beta should be exactly 1.0000
    beta_1x = calculate_paired_beta(b_rets, b_rets)
    assert beta_1x == Decimal("1.0000")

    # Portfolio returns = -0.5 * Benchmark returns -> Beta should be -0.5000
    p_rets_neg = [b * Decimal("-0.5") for b in b_rets]
    beta_neg = calculate_paired_beta(p_rets_neg, b_rets)
    assert beta_neg == Decimal("-0.5000")

    # Constant portfolio returns -> Covariance is 0 -> Beta should be 0.0000
    p_rets_flat = [Decimal("0.01")] * 10
    beta_flat = calculate_paired_beta(p_rets_flat, b_rets)
    assert beta_flat == Decimal("0.0000")


def test_paired_beta_edge_cases():
    """Verify paired beta error conditions and insufficient observations."""
    b_rets = [Decimal("0.01")] * 10
    p_rets = [Decimal("0.02")] * 10

    # Zero benchmark variance (all benchmark returns identical) -> returns None
    assert calculate_paired_beta(p_rets, b_rets) is None

    # Insufficient returns (< 10)
    assert calculate_paired_beta(p_rets[:9], b_rets[:9]) is None

    # Mismatched sequence lengths -> ValueError
    with pytest.raises(ValueError, match="must have identical lengths"):
        calculate_paired_beta(p_rets[:10], b_rets[:9])

    # Boolean or non-finite in returns -> ValueError
    with pytest.raises(ValueError, match="cannot be a boolean"):
        calculate_paired_beta(p_rets[:9] + [True], b_rets)
    with pytest.raises(ValueError, match="must be a finite number"):
        calculate_paired_beta(p_rets[:9] + [Decimal("NaN")], b_rets)


def test_relative_return_calculation():
    """Verify excess/relative return over benchmark."""
    # Outperformance
    rel1 = calculate_relative_return(Decimal("15.50"), Decimal("10.25"))
    assert rel1 == Decimal("5.25")

    # Underperformance
    rel2 = calculate_relative_return(Decimal("5.00"), Decimal("12.00"))
    assert rel2 == Decimal("-7.00")

    # Equal
    rel3 = calculate_relative_return(Decimal("8.50"), Decimal("8.50"))
    assert rel3 == Decimal("0.00")

    # Invalid inputs
    with pytest.raises(ValueError, match="cannot be a boolean"):
        calculate_relative_return(True, Decimal("10.00"))
    with pytest.raises(ValueError, match="must be a finite number"):
        calculate_relative_return(Decimal("10.00"), Decimal("Infinity"))


def test_historical_risk_metrics_schema_defaults():
    """Verify HistoricalRiskMetrics schema structure and truthful defaults."""
    risk = HistoricalRiskMetrics()
    assert risk.annualized_volatility_percent is None
    assert risk.maximum_drawdown_percent is None
    assert risk.beta is None
    assert risk.benchmark_relative_return_percent is None
    assert risk.benchmark_symbol is None
    assert risk.data_status == "INSUFFICIENT_HISTORY"
    assert "Historical volatility and risk metrics reflect actual chronological price observations" in risk.disclaimer


@pytest.mark.asyncio
async def test_analytics_service_exposes_historical_risk_insufficient_history(test_db_setup):
    """
    Verify that AnalyticsService exposes historical_risk block with
    truthful null metrics and INSUFFICIENT_HISTORY status for portfolios.
    """
    from app.services.analytics_service import AnalyticsService
    from app.services.portfolio_service import PortfolioService
    from app.schemas.portfolio import PortfolioCreate, HoldingCreate

    session_factory, _ = test_db_setup

    async with session_factory() as session:
        port_service = PortfolioService(session)
        # 1. Empty portfolio
        empty_p = await port_service.create_portfolio(PortfolioCreate(name="Empty Risk Test"))
        analytics_service = AnalyticsService(session)
        res_empty = await analytics_service.calculate_portfolio_analytics(empty_p.id)

        assert res_empty is not None
        assert res_empty.historical_risk is not None
        assert res_empty.historical_risk.annualized_volatility_percent is None
        assert res_empty.historical_risk.maximum_drawdown_percent is None
        assert res_empty.historical_risk.beta is None
        assert res_empty.historical_risk.benchmark_relative_return_percent is None
        assert res_empty.historical_risk.benchmark_symbol == "NIFTY 50"
        assert res_empty.historical_risk.data_status == "INSUFFICIENT_HISTORY"

        # 2. Populated portfolio
        pop_p = await port_service.create_portfolio(PortfolioCreate(name="Populated Risk Test"))
        await port_service.add_holding(
            pop_p.id,
            HoldingCreate(
                symbol="RELIANCE",
                exchange="NSE",
                asset_class="EQUITY",
                quantity=10,
                average_buy_price=Decimal("2500.00"),
                sector="Energy",
            ),
        )
        res_pop = await analytics_service.calculate_portfolio_analytics(pop_p.id)

        assert res_pop is not None
        assert res_pop.historical_risk is not None
        assert res_pop.historical_risk.annualized_volatility_percent is None
        assert res_pop.historical_risk.maximum_drawdown_percent is None
        assert res_pop.historical_risk.beta is None
        assert res_pop.historical_risk.benchmark_relative_return_percent is None
        assert res_pop.historical_risk.benchmark_symbol == "NIFTY 50"
        assert res_pop.historical_risk.data_status == "INSUFFICIENT_HISTORY"


def test_caller_decimal_precision_isolation():
    """
    Verify calculation functions isolate precision using localcontext(28)
    even when caller's Decimal context precision is drastically reduced or altered,
    and that the caller's context is restored without modification.
    """
    from decimal import getcontext

    orig_prec = getcontext().prec
    try:
        # Set caller's precision to very low value (e.g. 4)
        getcontext().prec = 4

        # 1. Volatility still evaluates to exactly 36.95%
        vol = calculate_sample_volatility(FIXTURE_11_PRICES)
        assert vol == Decimal("36.95")

        # 2. Maximum drawdown still evaluates to exactly 1.82%
        mdd = calculate_maximum_drawdown(FIXTURE_11_PRICES)
        assert mdd == Decimal("1.82")

        # 3. Paired beta still evaluates to exactly 2.0000
        b_rets = [Decimal("0.01") * Decimal(i) for i in range(1, 11)]
        p_rets = [b * Decimal("2") for b in b_rets]
        beta = calculate_paired_beta(p_rets, b_rets)
        assert beta == Decimal("2.0000")

        # 4. Discrete returns still preserves exact fractions
        returns = calculate_discrete_returns(FIXTURE_11_PRICES)
        assert len(returns) == 10
        assert returns[0] == Decimal("0.02")

        # 5. Caller's context precision is NOT unintentionally modified
        assert getcontext().prec == 4
    finally:
        getcontext().prec = orig_prec


def test_caller_decimal_context_not_modified_high_precision():
    """
    Verify that high precision contexts set by caller are preserved and not overwritten.
    """
    from decimal import getcontext

    orig_prec = getcontext().prec
    try:
        getcontext().prec = 100

        vol = calculate_sample_volatility(FIXTURE_11_PRICES)
        assert vol == Decimal("36.95")

        assert getcontext().prec == 100
    finally:
        getcontext().prec = orig_prec


def test_relative_return_percentage_point_contract():
    """
    Verify that calculate_relative_return operates strictly on percentage points:
    - Inputs represent percentage points (e.g., 15.50 for 15.50%).
    - Output is quantized to 2 decimal places using ROUND_HALF_UP.
    - Does NOT silently convert/scale fractional inputs (e.g., 0.1550 is treated as 0.1550%).
    """
    # Outperformance in percentage points: 15.50% - 10.25% = 5.25%
    assert calculate_relative_return(Decimal("15.50"), Decimal("10.25")) == Decimal("5.25")

    # Underperformance in percentage points: 5.00% - 12.00% = -7.00%
    assert calculate_relative_return(Decimal("5.00"), Decimal("12.00")) == Decimal("-7.00")

    # Zero difference
    assert calculate_relative_return(Decimal("8.50"), Decimal("8.50")) == Decimal("0.00")

    # No silent scaling of fractional inputs: passing 0.1550 and 0.1025 subtracts directly to 0.0525 -> 0.05
    # (demonstrating it is the caller's duty to pass percentage points matching benchmark_relative_return_percent)
    assert calculate_relative_return(Decimal("0.1550"), Decimal("0.1025")) == Decimal("0.05")


