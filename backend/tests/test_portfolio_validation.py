from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.portfolio import (
    HoldingBase,
    HoldingCreate,
    PortfolioCreate,
)

def test_valid_holding_creation():
    """Verifies that valid holding data parses cleanly with normalized symbol and Decimal price."""
    holding = HoldingCreate(
        symbol=" reliance ",
        exchange="nse",
        quantity=25,
        average_buy_price="2450.75",
        sector="Energy",
        asset_class="equity",
    )
    assert holding.symbol == "RELIANCE"
    assert holding.exchange == "NSE"
    assert holding.quantity == 25
    assert holding.average_buy_price == Decimal("2450.75")
    assert holding.sector == "Energy"
    assert holding.asset_class == "EQUITY"

def test_holding_rejects_negative_and_zero_quantity():
    """Verifies that quantities <= 0 are rejected by validation."""
    with pytest.raises(ValidationError) as exc_zero:
        HoldingCreate(
            symbol="TCS",
            quantity=0,
            average_buy_price=Decimal("3500.00"),
        )
    assert "quantity" in str(exc_zero.value)

    with pytest.raises(ValidationError) as exc_neg:
        HoldingCreate(
            symbol="TCS",
            quantity=-5,
            average_buy_price=Decimal("3500.00"),
        )
    assert "quantity" in str(exc_neg.value)

def test_holding_rejects_boolean_quantity():
    """Verifies that boolean values are rejected for quantity."""
    with pytest.raises(ValidationError):
        HoldingCreate(
            symbol="TCS",
            quantity=True,  # In Python, bool is a subclass of int, but must be rejected
            average_buy_price=Decimal("3500.00"),
        )

def test_holding_rejects_negative_and_zero_price():
    """Verifies that average buy prices <= 0 are rejected by validation."""
    with pytest.raises(ValidationError) as exc_zero:
        HoldingCreate(
            symbol="INFY",
            quantity=10,
            average_buy_price=Decimal("0.00"),
        )
    assert "average_buy_price" in str(exc_zero.value)

    with pytest.raises(ValidationError) as exc_neg:
        HoldingCreate(
            symbol="INFY",
            quantity=10,
            average_buy_price=Decimal("-150.50"),
        )
    assert "average_buy_price" in str(exc_neg.value)

def test_holding_rejects_non_finite_price_values():
    """Verifies that non-finite values (NaN, Infinity, -Infinity) are strictly rejected."""
    for invalid_val in ["nan", "inf", "-inf", float("nan"), float("inf"), float("-inf")]:
        with pytest.raises(ValidationError) as exc:
            HoldingCreate(
                symbol="INFY",
                quantity=10,
                average_buy_price=invalid_val,
            )
        assert "finite" in str(exc.value).lower() or "monetary" in str(exc.value).lower()

def test_holding_rejects_invalid_symbols():
    """Verifies that symbols with invalid characters or excessive lengths are rejected."""
    invalid_symbols = ["", "   ", "TOOLONGTICKERNAMEEXCEEDING20CHARS", "BAD$SYMBOL", "INVALID.SYM"]
    for sym in invalid_symbols:
        with pytest.raises(ValidationError):
            HoldingCreate(
                symbol=sym,
                quantity=10,
                average_buy_price=Decimal("100.00"),
            )

def test_holding_allows_valid_indian_symbols():
    """Verifies valid symbols including hyphens and ampersands (e.g. M&M, BAJAJ-AUTO)."""
    valid_symbols = ["M&M", "BAJAJ-AUTO", "L&TFH", "TCS", "HDFCBANK", "500325"]
    for sym in valid_symbols:
        h = HoldingCreate(
            symbol=sym,
            quantity=10,
            average_buy_price=Decimal("100.00"),
        )
        assert h.symbol == sym

def test_holding_rejects_invalid_exchange_and_asset_class():
    """Verifies that unrecognized exchanges and asset classes are rejected."""
    with pytest.raises(ValidationError):
        HoldingCreate(
            symbol="TCS",
            exchange="NASDAQ",
            quantity=10,
            average_buy_price=Decimal("100.00"),
        )

    with pytest.raises(ValidationError):
        HoldingCreate(
            symbol="TCS",
            asset_class="CRYPTO",
            quantity=10,
            average_buy_price=Decimal("100.00"),
        )

def test_portfolio_name_validation():
    """Verifies that empty or whitespace-only portfolio names are rejected."""
    with pytest.raises(ValidationError):
        PortfolioCreate(name="")

    with pytest.raises(ValidationError):
        PortfolioCreate(name="   ")

    with pytest.raises(ValidationError):
        PortfolioCreate(name="A" * 101)  # Exceeds max_length=100

    p = PortfolioCreate(name="  Retirement Portfolio  ", is_sample=True)
    assert p.name == "Retirement Portfolio"
    assert p.is_sample is True
