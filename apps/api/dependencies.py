from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import Settings, get_settings
from database.connection import get_async_db


def get_app_settings() -> Settings:
    """Dependency injection provider for application settings."""
    return get_settings()


async def get_db_session(
    session: AsyncSession = Depends(get_async_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection provider for database session."""
    yield session
