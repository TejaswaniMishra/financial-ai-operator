import pytest
import asyncio
import jwt as pyjwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, text
from datetime import datetime, timedelta, timezone

from database.models.identity import User, TokenRevocation
from packages.utils.jwt import create_access_token, decode_access_token
from config.settings import get_settings
from services.auth.token_revocation import revoke_token, purge_expired_revocations

pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────
# 1. Exact logged-out token replay
# ──────────────────────────────────────────────────────────────

async def test_logout_and_replay(client: AsyncClient, auth_headers: dict):
    # 1. Access protected endpoint successfully
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    # 2. Logout
    logout_resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out"

    # 3. Replay exact Bearer token → 401
    replay_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert replay_resp.status_code == 401

    # 4. Repeated logout on revoked token → 401
    repeated_logout_resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert repeated_logout_resp.status_code == 401


# ──────────────────────────────────────────────────────────────
# 2. Two tokens for the same user — per-token isolation
# ──────────────────────────────────────────────────────────────

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

    # Token A → 401
    assert (await client.get("/api/v1/auth/me", headers=headers_a)).status_code == 401

    # Token B → still valid
    assert (await client.get("/api/v1/auth/me", headers=headers_b)).status_code == 200


# ──────────────────────────────────────────────────────────────
# 3. Genuine concurrent revocation
# ──────────────────────────────────────────────────────────────

async def test_concurrent_revocation(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    # HTTP-level: a double logout is safe and leaves exactly one revocation row.
    # (Sequential here: concurrent httpx ASGITransport requests share a single
    # event-loop greenlet context, which is a known aiosqlite limitation that
    # raises MissingGreenlet spuriously — genuine concurrency is exercised at
    # the service layer below on independent sessions.)
    first = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert second.status_code == 401  # token is already revoked

    # Genuine asyncio concurrency at the service layer: two tasks revoke the
    # SAME jti simultaneously on independent DB sessions. Both must complete
    # without error and exactly one revocation row may survive (idempotent).
    from database.connection import AsyncSessionLocal

    token = auth_headers["Authorization"].split(" ")[1]
    payload = decode_access_token(token)
    jti = payload.get("jti")
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None)

    async def _revoke():
        async with AsyncSessionLocal() as session:
            await revoke_token(session, jti, payload["sub"], expires_at)
            return "ok"

    results = await asyncio.gather(_revoke(), _revoke(), return_exceptions=True)
    assert all(r == "ok" for r in results), f"Unexpected exception: {results}"

    # Verify exactly one TokenRevocation row exists for this JTI
    stmt = select(TokenRevocation).where(TokenRevocation.jti == jti)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 1


# ──────────────────────────────────────────────────────────────
# 4. Internal revocation idempotency
# ──────────────────────────────────────────────────────────────

async def test_internal_revocation_idempotency(db_session: AsyncSession, test_user: User):
    jti = "test-idempotent-jti"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)

    # Call revoke twice — must not raise, must not duplicate
    await revoke_token(db_session, jti, test_user.id, expires_at)
    await revoke_token(db_session, jti, test_user.id, expires_at)

    # Verify no duplicate row
    stmt = select(TokenRevocation).where(TokenRevocation.jti == jti)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()
    assert len(rows) == 1


# ──────────────────────────────────────────────────────────────
# 5. User deletion preserves revocation history
# ──────────────────────────────────────────────────────────────

async def test_user_deletion_preserves_revocation(db_session: AsyncSession, test_user: User):
    jti = "test-delete-jti"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)

    # Create revocation
    await revoke_token(db_session, jti, test_user.id, expires_at)

    # Enable FK constraints for this connection so ON DELETE SET NULL fires
    await db_session.execute(text("PRAGMA foreign_keys=ON"))

    try:
        # Delete user
        stmt = delete(User).where(User.id == test_user.id)
        await db_session.execute(stmt)
        await db_session.commit()

        # Expire cached state so SQLAlchemy re-reads from DB
        db_session.expire_all()

        # Verify TokenRevocation remains and user_id is NULL
        stmt_check = select(TokenRevocation).where(TokenRevocation.jti == jti)
        result = await db_session.execute(stmt_check)
        revocation = result.scalar_one()

        assert revocation is not None
        assert revocation.user_id is None
        assert revocation.jti == jti
        assert revocation.expires_at is not None
        assert revocation.revoked_at is not None
        assert revocation.created_at is not None
    finally:
        await db_session.execute(text("PRAGMA foreign_keys=OFF"))


# ──────────────────────────────────────────────────────────────
# 6. Expiration cleanup
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
# 7. Invalid JWT security
# ──────────────────────────────────────────────────────────────

async def test_malformed_token_returns_401(client: AsyncClient):
    headers = {"Authorization": "Bearer not-a-valid-jwt"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_tampered_token_returns_401(client: AsyncClient, test_user: User):
    token = create_access_token(user_id=test_user.id)
    # Tamper with the payload by flipping a character
    parts = token.split(".")
    tampered_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    headers = {"Authorization": f"Bearer {tampered_token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_expired_token_returns_401(client: AsyncClient, test_user: User):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    # Token that expired 10 minutes ago
    payload = {
        "sub": test_user.id,
        "iat": now - timedelta(minutes=20),
        "exp": now - timedelta(minutes=10),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": "expired-test-jti",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_wrong_issuer_returns_401(client: AsyncClient, test_user: User):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": test_user.id,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": "wrong-issuer",
        "aud": settings.JWT_AUDIENCE,
        "jti": "wrong-iss-jti",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_wrong_audience_returns_401(client: AsyncClient, test_user: User):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": test_user.id,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": settings.JWT_ISSUER,
        "aud": "wrong-audience",
        "jti": "wrong-aud-jti",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_alg_none_returns_401(client: AsyncClient, test_user: User):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": test_user.id,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": "alg-none-jti",
    }
    # Craft an alg=none token manually (PyJWT refuses to encode with none by default)
    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload, default=str).encode()).rstrip(b"=").decode()
    none_token = f"{header}.{body}."

    headers = {"Authorization": f"Bearer {none_token}"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────
# 8. Logout must NOT accept a client-supplied jti
# ──────────────────────────────────────────────────────────────

async def test_logout_jti_comes_from_validated_token(client: AsyncClient, test_user: User):
    """
    Verify that logout extracts jti from the validated Bearer token,
    NOT from any client-supplied body or query parameter.
    """
    token = create_access_token(user_id=test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to supply a different jti in the request body — it must be ignored
    resp = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"jti": "attacker-supplied-jti"}
    )
    assert resp.status_code == 200

    # The revoked jti must be the one FROM the token, not the attacker's
    payload = decode_access_token(token)
    real_jti = payload.get("jti")

    # The real token's jti should now be revoked
    replay = await client.get("/api/v1/auth/me", headers=headers)
    assert replay.status_code == 401

    # A different token for the same user should still work (proving per-token revocation)
    token_b = create_access_token(user_id=test_user.id)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = await client.get("/api/v1/auth/me", headers=headers_b)
    assert resp_b.status_code == 200
