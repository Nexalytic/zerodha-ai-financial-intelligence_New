from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.portfolio import Holding, Portfolio

@pytest.mark.asyncio
async def test_portfolio_and_holding_persistence(test_db_setup):
    """
    Verifies creating and querying a Portfolio with associated Holdings
    using the isolated temporary database, ensuring UUIDs and Decimal buy prices.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        portfolio = Portfolio(
            name="Core Long Term",
            description="Bluechip portfolio",
            is_sample=False,
        )
        session.add(portfolio)
        await session.flush()

        holding_1 = Holding(
            portfolio_id=portfolio.id,
            symbol="RELIANCE",
            exchange="NSE",
            quantity=50,
            average_buy_price=Decimal("2850.50"),
            sector="Energy",
            asset_class="EQUITY",
        )
        holding_2 = Holding(
            portfolio_id=portfolio.id,
            symbol="TCS",
            exchange="NSE",
            quantity=30,
            average_buy_price=Decimal("3920.00"),
            sector="IT",
            asset_class="EQUITY",
        )
        session.add_all([holding_1, holding_2])
        await session.commit()

    # Query in a fresh session to verify persistence and relationship
    async with session_factory() as session:
        result = await session.execute(
            select(Portfolio).where(Portfolio.name == "Core Long Term")
        )
        saved_portfolio = result.scalar_one()

        assert saved_portfolio.id is not None
        assert len(saved_portfolio.id) == 36  # UUID length
        assert saved_portfolio.is_sample is False
        assert saved_portfolio.created_at is not None
        assert saved_portfolio.updated_at is not None

        # Check holdings relationship
        holdings_res = await session.execute(
            select(Holding).where(Holding.portfolio_id == saved_portfolio.id).order_by(Holding.symbol)
        )
        saved_holdings = holdings_res.scalars().all()
        assert len(saved_holdings) == 2

        assert saved_holdings[0].symbol == "RELIANCE"
        assert saved_holdings[0].quantity == 50
        assert saved_holdings[0].average_buy_price == Decimal("2850.50")
        assert saved_holdings[0].sector == "Energy"

        assert saved_holdings[1].symbol == "TCS"
        assert saved_holdings[1].quantity == 30
        assert saved_holdings[1].average_buy_price == Decimal("3920.00")

@pytest.mark.asyncio
async def test_portfolio_cascade_deletion(test_db_setup):
    """
    Verifies that deleting a Portfolio cascades to automatically delete
    all associated Holdings (ON DELETE CASCADE).
    """
    session_factory, _ = test_db_setup

    portfolio_id = None
    async with session_factory() as session:
        portfolio = Portfolio(name="Temporary Basket", is_sample=True)
        session.add(portfolio)
        await session.flush()
        portfolio_id = portfolio.id

        holding = Holding(
            portfolio_id=portfolio_id,
            symbol="INFY",
            exchange="NSE",
            quantity=100,
            average_buy_price=Decimal("1520.25"),
            sector="IT",
        )
        session.add(holding)
        await session.commit()

    # Verify holding exists
    async with session_factory() as session:
        res = await session.execute(select(Holding).where(Holding.portfolio_id == portfolio_id))
        assert len(res.scalars().all()) == 1

        # Delete the portfolio
        portfolio_to_del = await session.get(Portfolio, portfolio_id)
        assert portfolio_to_del is not None
        await session.delete(portfolio_to_del)
        await session.commit()

    # Verify both portfolio and associated holding are gone
    async with session_factory() as session:
        portfolio_check = await session.get(Portfolio, portfolio_id)
        assert portfolio_check is None

        holding_check = await session.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id)
        )
        assert len(holding_check.scalars().all()) == 0

@pytest.mark.asyncio
async def test_foreign_key_constraint_enforcement(test_db_setup):
    """
    Verifies that attempting to create a Holding referencing a non-existent
    portfolio ID is rejected by SQLite foreign key enforcement.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        orphan_holding = Holding(
            portfolio_id="00000000-0000-0000-0000-000000000000",
            symbol="HDFCBANK",
            exchange="NSE",
            quantity=10,
            average_buy_price=Decimal("1650.00"),
        )
        session.add(orphan_holding)
        with pytest.raises(IntegrityError):
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

@pytest.mark.asyncio
async def test_portfolio_is_sample_flag_default_and_explicit(test_db_setup):
    """Verifies default and explicit is_sample marker persistence."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        user_p = Portfolio(name="Real Portfolio")
        demo_p = Portfolio(name="Demo Portfolio", is_sample=True)
        session.add_all([user_p, demo_p])
        await session.commit()

        assert user_p.is_sample is False
        assert demo_p.is_sample is True
