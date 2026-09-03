from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete

from database.models.identity import TokenRevocation

async def revoke_token(db: AsyncSession, jti: str, user_id: str, expires_at: datetime) -> None:
    """
    Revokes a specific JWT by its unique jti.
    Idempotent: safely ignores concurrent or repeated revocation attempts.
    """
    revocation = TokenRevocation(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        revoked_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(revocation)
    try:
        await db.commit()
    except IntegrityError:
        # Expected if another concurrent request already revoked this token
        await db.rollback()

async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
    """
    Checks if a token is revoked.
    """
    stmt = select(TokenRevocation.id).where(TokenRevocation.jti == jti)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None

async def purge_expired_revocations(db: AsyncSession) -> int:
    """
    Optional cleanup utility to remove revocations for tokens that have natively expired.
    Returns the number of rows deleted.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stmt = delete(TokenRevocation).where(TokenRevocation.expires_at < now)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
