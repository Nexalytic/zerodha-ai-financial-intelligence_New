import logging
from pathlib import Path
from typing import Any, AsyncGenerator
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import BACKEND_DIR, settings

logger = logging.getLogger("zerodha_backend.db")

def resolve_sqlite_url(url: str) -> tuple[str, Path | None]:
    """
    Explicitly resolves relative SQLite file paths against BACKEND_DIR,
    guaranteeing parent directory creation and normalized forward slashes.
    """
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        raw_path = url[len(prefix):]
        if raw_path == ":memory:" or not raw_path:
            return "sqlite+aiosqlite:///:memory:", None
        file_path = Path(raw_path)
        if not file_path.is_absolute():
            file_path = (BACKEND_DIR / file_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_url = f"{prefix}{file_path.as_posix()}"
        return normalized_url, file_path
    return url, None

def create_db_engine(database_url: str) -> AsyncEngine:
    resolved_url, _ = resolve_sqlite_url(database_url)
    engine = create_async_engine(
        resolved_url,
        echo=False,
        future=True,
    )

    if "sqlite" in database_url:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    return engine

# Application-wide engine and sessionmaker
engine: AsyncEngine = create_db_engine(settings.DATABASE_URL)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing a transactional async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def ping_database(session_factory=None) -> dict[str, Any]:
    """
    Pings the database and verifies active SQLite PRAGMA settings.
    Raises an exception if the database is unreachable.
    """
    factory = session_factory or async_session_factory
    async with factory() as session:
        await session.execute(text("SELECT 1"))
        fk_result = await session.execute(text("PRAGMA foreign_keys;"))
        fk_val = fk_result.scalar()
        jm_result = await session.execute(text("PRAGMA journal_mode;"))
        jm_val = jm_result.scalar()
        return {
            "connected": True,
            "foreign_keys": bool(fk_val),
            "journal_mode": str(jm_val).lower() if jm_val else "unknown",
        }

async def close_database():
    """Disposes the async engine and releases connections cleanly."""
    await engine.dispose()
