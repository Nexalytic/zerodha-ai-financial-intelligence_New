import asyncio
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.portfolio import Holding, Portfolio
from app.schemas.portfolio import (
    HoldingCreate,
    PortfolioCreate,
    PortfolioImportRequest,
    PortfolioResponse,
    PortfolioUpdate,
)

CANONICAL_DEMO_NAME = "Demo Indian Bluechip Portfolio"
DEMO_PORTFOLIO_ID = "00000000-0000-0000-0000-000000000001"

# In-process lock to serialize concurrent demo seeding calls within the same process
_seed_lock = asyncio.Lock()

DEMO_PORTFOLIO_HOLDINGS = [
    {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "quantity": 50,
        "average_buy_price": Decimal("2850.50"),
        "sector": "Energy",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "TCS",
        "exchange": "NSE",
        "quantity": 30,
        "average_buy_price": Decimal("3920.00"),
        "sector": "IT",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "INFY",
        "exchange": "NSE",
        "quantity": 60,
        "average_buy_price": Decimal("1520.25"),
        "sector": "IT",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "HDFCBANK",
        "exchange": "NSE",
        "quantity": 40,
        "average_buy_price": Decimal("1650.00"),
        "sector": "Financial Services",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "ICICIBANK",
        "exchange": "NSE",
        "quantity": 45,
        "average_buy_price": Decimal("1120.00"),
        "sector": "Financial Services",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "ITC",
        "exchange": "NSE",
        "quantity": 100,
        "average_buy_price": Decimal("430.00"),
        "sector": "Consumer Goods",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "BHARTIARTL",
        "exchange": "NSE",
        "quantity": 50,
        "average_buy_price": Decimal("1280.00"),
        "sector": "Telecommunication",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "SBIN",
        "exchange": "NSE",
        "quantity": 75,
        "average_buy_price": Decimal("760.00"),
        "sector": "Financial Services",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "LT",
        "exchange": "NSE",
        "quantity": 20,
        "average_buy_price": Decimal("3540.00"),
        "sector": "Construction",
        "asset_class": "EQUITY",
    },
    {
        "symbol": "M&M",
        "exchange": "NSE",
        "quantity": 25,
        "average_buy_price": Decimal("2800.00"),
        "sector": "Automobile",
        "asset_class": "EQUITY",
    },
]

class PortfolioService:
    """
    Portfolio management service encapsulating CRUD, atomic imports,
    eager relationship loading, transaction safety, and idempotent demo seeding.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_portfolios(self, is_sample: Optional[bool] = None) -> List[PortfolioResponse]:
        """
        Lists portfolios with optional filtering by is_sample flag.
        Eagerly loads holdings to safely calculate holdings_count.
        """
        stmt = (
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .order_by(Portfolio.created_at.desc())
        )
        if is_sample is not None:
            stmt = stmt.where(Portfolio.is_sample == is_sample)

        result = await self.session.execute(stmt)
        portfolios = result.scalars().all()

        return [
            PortfolioResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                is_sample=p.is_sample,
                created_at=p.created_at,
                updated_at=p.updated_at,
                holdings_count=len(p.holdings) if p.holdings is not None else 0,
            )
            for p in portfolios
        ]

    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """
        Retrieves a single portfolio by ID with eager loading of associated holdings.
        """
        stmt = (
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.id == portfolio_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_portfolio(self, data: PortfolioCreate) -> Portfolio:
        """
        Creates a new portfolio with optional initial holdings in an atomic transaction.
        Rejects using the canonical demo name for user-created portfolios.
        """
        cleaned_name = data.name.strip()
        if cleaned_name == CANONICAL_DEMO_NAME:
            raise ValueError(
                f"The name '{CANONICAL_DEMO_NAME}' is reserved for the canonical demo portfolio."
            )

        portfolio = Portfolio(
            name=cleaned_name,
            description=data.description.strip() if data.description else None,
            is_sample=data.is_sample,
        )

        for h in data.holdings:
            portfolio.holdings.append(
                Holding(
                    symbol=h.symbol.strip().upper(),
                    exchange=h.exchange.strip().upper(),
                    quantity=h.quantity,
                    average_buy_price=h.average_buy_price,
                    sector=h.sector.strip() if h.sector else None,
                    asset_class=h.asset_class.strip().upper(),
                )
            )

        self.session.add(portfolio)
        try:
            await self.session.commit()
            await self.session.refresh(portfolio)
        except Exception:
            await self.session.rollback()
            raise

        # Re-query with eager load to ensure full attribute population
        return await self.get_portfolio(portfolio.id)

    async def update_portfolio(self, portfolio_id: str, data: PortfolioUpdate) -> Optional[Portfolio]:
        """
        Updates portfolio metadata with strict field handling:
        - Rejects empty payload.
        - Supports updating name and clearing/updating description.
        """
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("At least one field ('name' or 'description') must be provided for update.")

        portfolio = await self.get_portfolio(portfolio_id)
        if portfolio is None:
            return None

        if "name" in updates:
            cleaned_name = data.name.strip()
            if cleaned_name == CANONICAL_DEMO_NAME and not portfolio.is_sample:
                raise ValueError(
                    f"The name '{CANONICAL_DEMO_NAME}' is reserved for the canonical demo portfolio."
                )
            portfolio.name = cleaned_name

        if "description" in updates:
            portfolio.description = data.description.strip() if data.description else None

        try:
            await self.session.commit()
            await self.session.refresh(portfolio)
        except Exception:
            await self.session.rollback()
            raise

        return portfolio

    async def delete_portfolio(self, portfolio_id: str) -> bool:
        """
        Deletes a portfolio and cascades deletion to all associated holdings.
        """
        portfolio = await self.get_portfolio(portfolio_id)
        if portfolio is None:
            return False

        try:
            await self.session.delete(portfolio)
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            raise

    async def import_portfolio(self, data: PortfolioImportRequest) -> Portfolio:
        """
        Performs atomic portfolio import.
        If any persistence failure occurs, rolls back cleanly leaving no partial records.
        """
        cleaned_name = data.name.strip()
        if cleaned_name == CANONICAL_DEMO_NAME:
            raise ValueError(
                f"The name '{CANONICAL_DEMO_NAME}' is reserved for the canonical demo portfolio."
            )

        portfolio = Portfolio(
            name=cleaned_name,
            description=data.description.strip() if data.description else None,
            is_sample=data.is_sample,
        )

        for h in data.holdings:
            portfolio.holdings.append(
                Holding(
                    symbol=h.symbol.strip().upper(),
                    exchange=h.exchange.strip().upper(),
                    quantity=h.quantity,
                    average_buy_price=h.average_buy_price,
                    sector=h.sector.strip() if h.sector else None,
                    asset_class=h.asset_class.strip().upper(),
                )
            )

        self.session.add(portfolio)
        try:
            await self.session.commit()
            await self.session.refresh(portfolio)
        except Exception:
            await self.session.rollback()
            raise

        return await self.get_portfolio(portfolio.id)

    async def seed_demo_portfolio(self) -> Tuple[Portfolio, bool]:
        """
        Idempotent and concurrency-safe demo portfolio seeder.
        - Backed by SQLite partial unique index on canonical demo identity.
        - Uses deterministic DEMO_PORTFOLIO_ID.
        - Catches IntegrityError, rolls back immediately, and retrieves existing demo portfolio.
        Returns: (portfolio, created: bool)
        """
        async with _seed_lock:
            # 1. Fast check if canonical demo portfolio already exists
            stmt = (
                select(Portfolio)
                .options(selectinload(Portfolio.holdings))
                .where(
                    (Portfolio.id == DEMO_PORTFOLIO_ID)
                    | ((Portfolio.name == CANONICAL_DEMO_NAME) & (Portfolio.is_sample == True))
                )
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing, False

            # 2. Build demo portfolio with curated holdings
            demo_portfolio = Portfolio(
                id=DEMO_PORTFOLIO_ID,
                name=CANONICAL_DEMO_NAME,
                description="Curated sample portfolio of leading Indian equities for platform demonstration.",
                is_sample=True,
            )

            for item in DEMO_PORTFOLIO_HOLDINGS:
                demo_portfolio.holdings.append(
                    Holding(
                        symbol=item["symbol"],
                        exchange=item["exchange"],
                        quantity=item["quantity"],
                        average_buy_price=item["average_buy_price"],
                        sector=item["sector"],
                        asset_class=item["asset_class"],
                    )
                )

            self.session.add(demo_portfolio)
            try:
                await self.session.commit()
                seeded = await self.get_portfolio(demo_portfolio.id)
                return seeded, True
            except IntegrityError:
                # Race condition: another transaction committed first
                await self.session.rollback()
                result = await self.session.execute(stmt)
                winner = result.scalar_one()
                return winner, False

    async def add_holding(self, portfolio_id: str, data: HoldingCreate) -> Optional[Holding]:
        """
        Adds a single holding to an existing portfolio.
        """
        portfolio = await self.get_portfolio(portfolio_id)
        if portfolio is None:
            return None

        holding = Holding(
            portfolio_id=portfolio_id,
            symbol=data.symbol.strip().upper(),
            exchange=data.exchange.strip().upper(),
            quantity=data.quantity,
            average_buy_price=data.average_buy_price,
            sector=data.sector.strip() if data.sector else None,
            asset_class=data.asset_class.strip().upper(),
        )

        self.session.add(holding)
        try:
            await self.session.commit()
            await self.session.refresh(holding)
            return holding
        except Exception:
            await self.session.rollback()
            raise

    async def delete_holding(self, portfolio_id: str, holding_id: str) -> bool:
        """
        Deletes a single holding from a portfolio.
        """
        stmt = select(Holding).where(
            Holding.id == holding_id,
            Holding.portfolio_id == portfolio_id,
        )
        result = await self.session.execute(stmt)
        holding = result.scalar_one_or_none()
        if holding is None:
            return False

        try:
            await self.session.delete(holding)
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            raise
