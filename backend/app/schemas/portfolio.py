import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

SYMBOL_REGEX = re.compile(r"^[A-Z0-9&-]{1,20}$")
VALID_EXCHANGES = {"NSE", "BSE"}
VALID_ASSET_CLASSES = {"EQUITY", "ETF", "MUTUAL_FUND"}

class HoldingBase(BaseModel):
    symbol: str = Field(..., description="NSE/BSE ticker symbol (e.g. RELIANCE, TCS)")
    exchange: str = Field(default="NSE", description="Exchange identifier (NSE or BSE)")
    quantity: int = Field(..., gt=0, description="Positive quantity of shares held")
    average_buy_price: Decimal = Field(..., gt=Decimal("0"), description="Positive average acquisition price per share")
    sector: Optional[str] = Field(default=None, max_length=50, description="Industrial/market sector (e.g. IT, Energy)")
    asset_class: str = Field(default="EQUITY", description="Asset class identifier (e.g. EQUITY, ETF)")

    @field_validator("symbol")
    @classmethod
    def validate_and_normalize_symbol(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not SYMBOL_REGEX.match(cleaned):
            raise ValueError("Symbol must be 1-20 alphanumeric characters, &, or - (e.g. M&M, RELIANCE)")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_EXCHANGES:
            raise ValueError(f"Exchange must be one of {sorted(VALID_EXCHANGES)}")
        return cleaned

    @field_validator("asset_class")
    @classmethod
    def validate_asset_class(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in VALID_ASSET_CLASSES:
            raise ValueError(f"Asset class must be one of {sorted(VALID_ASSET_CLASSES)}")
        return cleaned

    @field_validator("average_buy_price", mode="before")
    @classmethod
    def validate_finite_price(cls, v: Any) -> Decimal:
        if isinstance(v, (float, int, str)):
            try:
                dec = Decimal(str(v))
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError("Invalid monetary value format")
        elif isinstance(v, Decimal):
            dec = v
        else:
            raise ValueError("Average buy price must be a valid monetary number")

        if not dec.is_finite():
            raise ValueError("Monetary values must be finite numbers (not NaN or Infinity)")
        if dec <= Decimal("0"):
            raise ValueError("Average buy price must be strictly greater than 0")
        return dec.quantize(Decimal("0.01"))

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity_int(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("Quantity must be a valid positive integer")
        if not isinstance(v, int):
            try:
                if isinstance(v, float) and not v.is_integer():
                    raise ValueError("Quantity must be an integer")
                v = int(v)
            except (ValueError, TypeError):
                raise ValueError("Quantity must be an integer")
        if v <= 0:
            raise ValueError("Quantity must be strictly greater than 0")
        return v

class HoldingCreate(HoldingBase):
    pass

class HoldingResponse(HoldingBase):
    id: str
    portfolio_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PortfolioBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable portfolio name")
    description: Optional[str] = Field(default=None, max_length=255, description="Optional portfolio description")
    is_sample: bool = Field(default=False, description="Marker indicating if this portfolio contains demo/sample data")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Portfolio name cannot be empty or whitespace only")
        return cleaned

class PortfolioCreate(PortfolioBase):
    holdings: List[HoldingCreate] = Field(default_factory=list, description="Initial holdings to associate with portfolio")

class PortfolioResponse(PortfolioBase):
    id: str
    created_at: datetime
    updated_at: datetime
    holdings_count: int = Field(default=0, description="Total number of asset positions")

    model_config = ConfigDict(from_attributes=True)

class PortfolioDetailResponse(PortfolioResponse):
    holdings: List[HoldingResponse] = Field(default_factory=list, description="List of individual holdings")

class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100, description="Updated portfolio name")
    description: Optional[str] = Field(default=None, max_length=255, description="Updated portfolio description")

    @field_validator("name")
    @classmethod
    def validate_update_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Portfolio name cannot be empty or whitespace only")
            return cleaned
        return v

class PortfolioImportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Imported portfolio name")
    description: Optional[str] = Field(default=None, max_length=255, description="Optional description")
    is_sample: bool = Field(default=False, description="Marker indicating if this is demo/sample data")
    holdings: List[HoldingCreate] = Field(..., min_length=1, description="List of positions to import")

    @field_validator("name")
    @classmethod
    def validate_import_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Portfolio name cannot be empty or whitespace only")
        return cleaned

    @field_validator("holdings")
    @classmethod
    def validate_unique_positions(cls, holdings: List[HoldingCreate]) -> List[HoldingCreate]:
        if not holdings:
            raise ValueError("Portfolio import must contain at least one holding")
        seen = set()
        for h in holdings:
            key = (h.symbol.strip().upper(), h.exchange.strip().upper())
            if key in seen:
                raise ValueError(
                    f"Duplicate position for symbol '{h.symbol}' on exchange '{h.exchange}'. "
                    f"Please consolidate quantity and average buy price before importing."
                )
            seen.add(key)
        return holdings

class SeedDemoResponse(BaseModel):
    portfolio: PortfolioDetailResponse
    created: bool
    message: str

class PortfolioDeleteResponse(BaseModel):
    id: str
    deleted: bool = True
    message: str = "Portfolio and associated holdings deleted successfully"

