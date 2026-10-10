import asyncio
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models.portfolio import Holding, Portfolio
from app.schemas.portfolio import (
    HoldingCreate,
    PortfolioCreate,
    PortfolioImportRequest,
    PortfolioUpdate,
)
from app.services.portfolio_service import (
    CANONICAL_DEMO_NAME,
    DEMO_PORTFOLIO_ID,
    PortfolioService,
)

@pytest.mark.asyncio
async def test_service_create_and_eager_load(test_db_setup):
    """
    Verifies creating a portfolio with holdings and eager loading relations
    without MissingGreenlet errors.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = PortfolioService(session)
        portfolio = await service.create_portfolio(
            PortfolioCreate(
                name="Retirement Fund",
                description="Long term equity",
                holdings=[
                    HoldingCreate(
                        symbol="RELIANCE",
                        exchange="NSE",
                        quantity=50,
                        average_buy_price=Decimal("2850.50"),
                        sector="Energy",
                    ),
                    HoldingCreate(
                        symbol="TCS",
                        exchange="NSE",
                        quantity=25,
                        average_buy_price=Decimal("3920.00"),
                        sector="IT",
                    ),
                ],
            )
        )
        assert portfolio.id is not None
        assert portfolio.name == "Retirement Fund"
        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].symbol == "RELIANCE"
        assert portfolio.holdings[0].average_buy_price == Decimal("2850.50")

    # Verify retrieval
    async with session_factory() as session:
        service = PortfolioService(session)
        fetched = await service.get_portfolio(portfolio.id)
        assert fetched is not None
        assert len(fetched.holdings) == 2

@pytest.mark.asyncio
async def test_service_list_filtering_is_sample(test_db_setup):
    """Verifies listing portfolios with is_sample=True and is_sample=False filters."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = PortfolioService(session)
        await service.create_portfolio(PortfolioCreate(name="Real Portfolio", is_sample=False))
        await service.create_portfolio(PortfolioCreate(name="Demo Test Portfolio", is_sample=True))

        all_p = await service.list_portfolios()
        assert len(all_p) >= 2

        real_p = await service.list_portfolios(is_sample=False)
        assert all(p.is_sample is False for p in real_p)

        sample_p = await service.list_portfolios(is_sample=True)
        assert all(p.is_sample is True for p in sample_p)

@pytest.mark.asyncio
async def test_service_update_semantics(test_db_setup):
    """
    Verifies update semantics:
    - Valid name update
    - Explicit null description clears description
    - Empty payload raises ValueError
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = PortfolioService(session)
        created = await service.create_portfolio(
            PortfolioCreate(name="Growth Basket", description="Initial description")
        )
        port_id = created.id

        # Empty payload
        with pytest.raises(ValueError) as exc:
            await service.update_portfolio(port_id, PortfolioUpdate())
        assert "At least one field" in str(exc.value)

        # Update name and clear description
        updated = await service.update_portfolio(
            port_id, PortfolioUpdate(name="Renamed Growth Basket", description=None)
        )
        assert updated.name == "Renamed Growth Basket"
        assert updated.description is None

@pytest.mark.asyncio
async def test_service_delete_cascades_holdings(test_db_setup):
    """
    Verifies deleting a portfolio cascades and cleans up all associated holdings.
    """
    session_factory, _ = test_db_setup

    port_id = None
    async with session_factory() as session:
        service = PortfolioService(session)
        created = await service.create_portfolio(
            PortfolioCreate(
                name="To Delete",
                holdings=[
                    HoldingCreate(symbol="INFY", quantity=10, average_buy_price=Decimal("1500.00")),
                    HoldingCreate(symbol="ITC", quantity=20, average_buy_price=Decimal("400.00")),
                ],
            )
        )
        port_id = created.id

    # Delete portfolio
    async with session_factory() as session:
        service = PortfolioService(session)
        assert await service.delete_portfolio(port_id) is True

    # Assert 0 holdings remain in DB
    async with session_factory() as session:
        res = await session.execute(select(Holding).where(Holding.portfolio_id == port_id))
        assert len(res.scalars().all()) == 0

@pytest.mark.asyncio
async def test_service_atomic_import_success(test_db_setup):
    """Verifies atomic import creates portfolio and all positions in one unit."""
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = PortfolioService(session)
        imported = await service.import_portfolio(
            PortfolioImportRequest(
                name="Imported Balanced Fund",
                description="Imported from spreadsheet",
                holdings=[
                    HoldingCreate(symbol="HDFCBANK", quantity=30, average_buy_price=Decimal("1650.00")),
                    HoldingCreate(symbol="ICICIBANK", quantity=40, average_buy_price=Decimal("1100.00")),
                ],
            )
        )
        assert imported.id is not None
        assert len(imported.holdings) == 2

@pytest.mark.asyncio
async def test_service_atomic_import_rollback_on_failure(test_db_setup):
    """
    Verifies that a failure during import persistence causes a clean rollback,
    leaving no orphan portfolios or partial holdings.
    """
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        service = PortfolioService(session)
        # Construct request with invalid symbol that triggers DB failure or validation
        req = PortfolioImportRequest(
            name="Fail Import",
            holdings=[
                HoldingCreate(symbol="RELIANCE", quantity=10, average_buy_price=Decimal("2800.00")),
            ],
        )

        # Monkey-patch session.commit to simulate mid-transaction failure
        async def failing_commit():
            raise RuntimeError("Simulated database write IO failure")

        orig_commit = session.commit
        session.commit = failing_commit

        with pytest.raises(RuntimeError):
            await service.import_portfolio(req)

        session.commit = orig_commit

    # Verify no portfolio was created
    async with session_factory() as session:
        res = await session.execute(select(Portfolio).where(Portfolio.name == "Fail Import"))
        assert res.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_service_demo_seeding_concurrency_safe(test_db_setup):
    """
    Verifies that concurrent seeding requests via asyncio.gather()
    execute cleanly and create exactly 1 canonical demo portfolio.
    """
    session_factory, _ = test_db_setup

    async def worker():
        async with session_factory() as session:
            service = PortfolioService(session)
            portfolio, created = await service.seed_demo_portfolio()
            return portfolio.id, created

    # Run 10 concurrent seeding workers
    results = await asyncio.gather(*(worker() for _ in range(10)))

    # Verify all workers returned the same DEMO_PORTFOLIO_ID
    for port_id, _ in results:
        assert port_id == DEMO_PORTFOLIO_ID

    created_flags = [c for _, c in results]
    assert created_flags.count(True) == 1
    assert created_flags.count(False) == 9

    # Verify database has exactly 1 demo portfolio
    async with session_factory() as session:
        res = await session.execute(
            select(Portfolio).where(Portfolio.name == CANONICAL_DEMO_NAME)
        )
        all_demos = res.scalars().all()
        assert len(all_demos) == 1

@pytest.mark.asyncio
async def test_service_holding_add_and_delete(test_db_setup):
    """Verifies adding and deleting individual holdings on a portfolio."""
    session_factory, _ = test_db_setup

    port_id = None
    holding_id = None

    async with session_factory() as session:
        service = PortfolioService(session)
        p = await service.create_portfolio(PortfolioCreate(name="Dynamic Positions Basket"))
        port_id = p.id

        holding = await service.add_holding(
            port_id,
            HoldingCreate(symbol="SBIN", quantity=100, average_buy_price=Decimal("750.00")),
        )
        assert holding.id is not None
        holding_id = holding.id

    # Delete holding
    async with session_factory() as session:
        service = PortfolioService(session)
        assert await service.delete_holding(port_id, holding_id) is True

    # Verify holding is deleted
    async with session_factory() as session:
        service = PortfolioService(session)
        p_check = await service.get_portfolio(port_id)
        assert len(p_check.holdings) == 0

@pytest.mark.asyncio
async def test_database_enforced_partial_unique_index(test_db_setup):
    """
    Verifies that SQLite directly enforces the partial unique index:
    Attempting to insert a second portfolio with CANONICAL_DEMO_NAME and is_sample=True
    using a DIFFERENT UUID raises IntegrityError at the SQLite engine level.
    Also verifies non-canonical or real portfolios can share names freely.
    """
    from sqlalchemy.exc import IntegrityError
    session_factory, _ = test_db_setup

    async with session_factory() as session:
        p1 = Portfolio(
            id="11111111-1111-1111-1111-111111111111",
            name=CANONICAL_DEMO_NAME,
            is_sample=True,
        )
        session.add(p1)
        await session.commit()

    async with session_factory() as session:
        p2 = Portfolio(
            id="22222222-2222-2222-2222-222222222222",  # Different UUID!
            name=CANONICAL_DEMO_NAME,
            is_sample=True,
        )
        session.add(p2)
        with pytest.raises(IntegrityError):
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Verify that real user portfolios can share names without conflict
    async with session_factory() as session:
        real_p1 = Portfolio(id="33333333-3333-3333-3333-333333333333", name="My Shared Basket", is_sample=False)
        real_p2 = Portfolio(id="44444444-4444-4444-4444-444444444444", name="My Shared Basket", is_sample=False)
        session.add_all([real_p1, real_p2])
        await session.commit()

