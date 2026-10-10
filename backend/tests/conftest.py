from pathlib import Path
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.session import get_db
from app.main import app, lifespan

@pytest.fixture
async def test_db_setup(tmp_path: Path):
    """
    Creates an isolated temporary SQLite database for testing,
    completely segregated from the development database.
    """
    test_db_file = tmp_path / "test_zerodha.db"
    test_db_url = f"sqlite+aiosqlite:///{test_db_file.as_posix()}"

    engine: AsyncEngine = create_async_engine(test_db_url, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Initialize tables / verify connection
    from app.db.base import Base
    import app.models  # Register models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await session.execute(text("SELECT 1"))

    yield session_factory, engine

    # Cleanup: cleanly dispose engine and release file locks before deleting
    await engine.dispose()
    try:
        if test_db_file.exists():
            test_db_file.unlink(missing_ok=True)
    except PermissionError:
        pass

@pytest.fixture
async def client(test_db_setup) -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client executing inside the FastAPI lifespan context,
    with database dependencies bound to the isolated test database.
    """
    session_factory, _ = test_db_setup

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with lifespan(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()
