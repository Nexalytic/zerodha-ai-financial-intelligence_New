import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Portfolio(Base):
    """
    Portfolio entity representing an investment portfolio container.
    Supports an explicit is_sample flag to distinguish demo portfolios from real user data.
    """
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # 1-to-many relationship with Holding; cascades deletes
    holdings: Mapped[List["Holding"]] = relationship(
        "Holding",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Holding.symbol",
    )

    __table_args__ = (
        Index(
            "uq_canonical_demo_portfolio",
            "name",
            unique=True,
            sqlite_where=text("name = 'Demo Indian Bluechip Portfolio' AND is_sample = 1"),
        ),
    )

class Holding(Base):
    """
    Holding entity representing an asset position within a portfolio.
    Financial values use exact Numeric/Decimal types.
    """
    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(10), default="NSE", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_buy_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )
    sector: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(20), default="EQUITY", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
