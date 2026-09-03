import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import datetime, timedelta, timezone

from database.models.identity import User, TokenRevocation
from packages.utils.jwt import create_access_token, decode_access_token
from config.settings import get_settings
from services.auth.token_revocation import revoke_token, purge_expired_revocations

pytestmark = pytest.mark.asyncio

async def test_logout_and_replay(client: AsyncClient, auth_headers: dict):
    # 1. Access protected endpoint successfully
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    # 2. Logout
    logout_resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out"

    # 3. Replay exact Bearer token
    replay_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert replay_resp.status_code == 401
    
    # 4. Repeated logout returns 401 (handled by get_current_user)
    repeated_logout_resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert repeated_logout_resp.status_code == 401


async def test_two_tokens_same_user(client: AsyncClient, test_user: User):
    # Create two valid tokens for the same user
    token_a = create_access_token(user_id=test_user.id)
    token_b = create_access_token(user_id=test_user.id)
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # Verify both work
    assert (await client.get("/api/v1/auth/me", headers=headers_a)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers_b)).status_code == 200
    
    # Revoke token A via logout
    assert (await client.post("/api/v1/auth/logout", headers=headers_a)).status_code == 200
    
    # Token A is 401
    assert (await client.get("/api/v1/auth/me", headers=headers_a)).status_code == 401
    
    # Token B is still valid
    assert (await client.get("/api/v1/auth/me", headers=headers_b)).status_code == 200


async def test_concurrent_revocation(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    # Make two concurrent requests to logout using asyncio.gather
    # We create multiple AsyncClients so they don't share underlying HTTP state connection pools unexpectedly in the test
    async with AsyncClient(app=client._transport.app, base_url="http://test") as c1, \
               AsyncClient(app=client._transport.app, base_url="http://test") as c2:
        
        results = await asyncio.gather(
            c1.post("/api/v1/auth/logout", headers=auth_headers),
            c2.post("/api/v1/auth/logout", headers=auth_headers),
            return_exceptions=True
        )
        
    # Both operations should return a safe HTTP response, no 500s.
    # One will get 200, one will get 401 (if get_current_user caught it first) 
    # OR both get 200 if they bypassed the check simultaneously and caught IntegrityError silently
    for res in results:
        assert res.status_code in (200, 401)
        
    # Verify exactly one TokenRevocation row exists for this JTI
    token = auth_headers["Authorization"].split(" ")[1]
    payload = decode_access_token(token)
    jti = payload.get("jti")
    
    stmt = select(TokenRevocation).where(TokenRevocation.jti == jti)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_internal_revocation_idempotency(db_session: AsyncSession, test_user: User):
    jti = "test-idempotent-jti"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    
    # Call revoke twice
    await revoke_token(db_session, jti, test_user.id, expires_at)
    await revoke_token(db_session, jti, test_user.id, expires_at)
    
    # Verify no duplicate row
    stmt = select(TokenRevocation).where(TokenRevocation.jti == jti)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_user_deletion_preserves_revocation(db_session: AsyncSession, test_user: User):
    jti = "test-delete-jti"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    
    # Create revocation
    await revoke_token(db_session, jti, test_user.id, expires_at)
    
    # Delete user
    stmt = delete(User).where(User.id == test_user.id)
    await db_session.execute(stmt)
    await db_session.commit()
    
    # Verify TokenRevocation remains and user_id is NULL
    stmt_check = select(TokenRevocation).where(TokenRevocation.jti == jti)
    result = await db_session.execute(stmt_check)
    revocation = result.scalar_one()
    
    assert revocation is not None
    assert revocation.user_id is None
    assert revocation.jti == jti


async def test_expiration_cleanup(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Expired token revocation
    expired_jti = "expired-jti"
    await revoke_token(db_session, expired_jti, test_user.id, now - timedelta(minutes=5))
    
    # Active token revocation
    active_jti = "active-jti"
    await revoke_token(db_session, active_jti, test_user.id, now + timedelta(minutes=5))
    
    # Purge
    deleted_count = await purge_expired_revocations(db_session)
    assert deleted_count == 1
    
    # Verify active remains
    stmt = select(TokenRevocation).where(TokenRevocation.jti == active_jti)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is not None
    
    # Verify expired is gone
    stmt2 = select(TokenRevocation).where(TokenRevocation.jti == expired_jti)
    res2 = await db_session.execute(stmt2)
    assert res2.scalar_one_or_none() is None
