import time
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config.settings import get_settings
from packages.schemas.system import DatabaseStatus

settings = get_settings()

# Engine creation with sensible connection pool defaults
_engine_kwargs = {"echo": settings.DATABASE_ECHO}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
    })

async_engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connectivity() -> DatabaseStatus:
    """Performs a lightweight connectivity check and measures latency."""
    engine_name = async_engine.url.drivername.split("+")[0]
    start_time = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start_time) * 1000.0
        return DatabaseStatus(
            connected=True,
            engine=engine_name,
            latency_ms=round(latency, 2),
            error=None,
        )
    except Exception as exc:
        return DatabaseStatus(
            connected=False,
            engine=engine_name,
            latency_ms=None,
            error=str(exc),
        )
