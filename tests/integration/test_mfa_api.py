import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import pyotp

from database.models.identity import User, UserCredential, Role, RoleName, UserRole
from database.models.mfa import MfaRecoveryCode
from database.models.security import SecurityEvent
from packages.utils.crypto import hash_password
from services.mfa import service as mfa_service

EMAIL = "mfa.user@example.com"
PASSWORD = "MfaPass123!"


async def _create_user(db: AsyncSession, email: str = EMAIL) -> User:
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    role = (await db.execute(stmt)).scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.OPERATOR, description="Operator")
        db.add(role)
        await db.flush()
    user = User(email=email, display_name="MFA User", is_active=True)
    db.add(user)
    await db.flush()
    db.add(UserCredential(user_id=user.id, password_hash=hash_password(PASSWORD)))
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()
    return user


@pytest.fixture
async def mfa_user(db_session: AsyncSession):
    return await _create_user(db_session)


async def _login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    res = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return res.json()


async def _enroll(client: AsyncClient, headers: dict) -> tuple[str, list[str]]:
    """setup + verify-setup. Returns (base32 secret, one-time recovery codes)."""
    res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert res.status_code == 200, res.text
    secret = res.json()["secret"]
    res = await client.post(
        "/api/v1/auth/mfa/verify-setup",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert res.status_code == 200, res.text
    codes = res.json()["codes"]
    assert len(codes) == mfa_service.RECOVERY_CODE_COUNT
    return secret, codes


async def _auth_headers(client: AsyncClient) -> dict:
    data = await _login(client)
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.mark.asyncio
async def test_login_without_mfa_returns_full_session(async_client: AsyncClient, mfa_user):
    data = await _login(async_client)
    assert data["mfa_required"] is False
    assert data["access_token"]
    assert data["mfa_token"] is None
    res = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert res.status_code == 200
    assert res.json()["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_unauthenticated_mfa_endpoints_are_401(async_client: AsyncClient, mfa_user):
    res = await async_client.post("/api/v1/auth/mfa/setup")
    assert res.status_code == 401
    res = await async_client.post("/api/v1/auth/mfa/verify-setup", json={"code": "123456"})
    assert res.status_code == 401
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": "not-a-token", "code": "123456"},
    )
    assert res.status_code == 401
    res = await async_client.post("/api/v1/auth/mfa/disable", json={"code": "123456"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_enrollment_rejects_invalid_code(async_client: AsyncClient, mfa_user):
    headers = await _auth_headers(async_client)
    res = await async_client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert res.status_code == 200
    secret = res.json()["secret"]
    wrong = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
    res = await async_client.post(
        "/api/v1/auth/mfa/verify-setup", headers=headers, json={"code": wrong}
    )
    assert res.status_code == 401
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.json()["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_mfa_challenge_blocks_until_verified(async_client: AsyncClient, mfa_user):
    headers = await _auth_headers(async_client)
    secret, _ = await _enroll(async_client, headers)

    # Login now yields a challenge, never a session.
    data = await _login(async_client)
    assert data["mfa_required"] is True
    assert data["access_token"] is None
    assert data["mfa_token"]

    # Challenge token cannot reach protected/identity endpoints.
    challenge = {"Authorization": f"Bearer {data['mfa_token']}"}
    for path in ("/api/v1/auth/me", "/api/v1/transactions", "/api/v1/notifications"):
        res = await async_client.get(path, headers=challenge)
        assert res.status_code in (401, 403), path

    # Wrong code → 401.
    wrong = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": wrong},
    )
    assert res.status_code == 401

    # Correct code → full session, MFA reported enabled, secret never exposed.
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert res.status_code == 200, res.text
    session = res.json()["access_token"]
    res = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {session}"}
    )
    assert res.status_code == 200
    me = res.json()
    assert me["mfa_enabled"] is True
    assert "mfa_secret" not in me and "secret" not in me and "codes" not in me

    # Challenge is single-use — replay is rejected.
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_recovery_code_login_single_use(
    async_client: AsyncClient, mfa_user, db_session: AsyncSession
):
    headers = await _auth_headers(async_client)
    _, codes = await _enroll(async_client, headers)
    assert len(codes) == mfa_service.RECOVERY_CODE_COUNT

    data = await _login(async_client)
    assert data["mfa_required"] is True

    # Recovery code completes login.
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": codes[0]},
    )
    assert res.status_code == 200, res.text

    # Same code cannot be reused against a fresh challenge.
    data2 = await _login(async_client)
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data2["mfa_token"], "code": codes[0]},
    )
    assert res.status_code == 401

    # The DB stores only a SHA-256 hash — never the plaintext code.
    stored = (
        await db_session.execute(
            select(MfaRecoveryCode.code_hash, MfaRecoveryCode.used).where(
                MfaRecoveryCode.user_id == mfa_user.id
            )
        )
    ).all()
    hashes = {h for h, _ in stored}
    assert mfa_service.hash_recovery_code(codes[0]) in hashes
    assert codes[0] not in hashes  # plaintext never persisted
    used_flags = [u for _, u in stored]
    assert sum(1 for u in used_flags if u) == 1  # exactly one code consumed


@pytest.mark.asyncio
async def test_disable_mfa_requires_valid_code(async_client: AsyncClient, mfa_user, db_session: AsyncSession):
    headers = await _auth_headers(async_client)
    secret, codes = await _enroll(async_client, headers)

    # Wrong code cannot disable.
    wrong = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
    res = await async_client.post("/api/v1/auth/mfa/disable", headers=headers, json={"code": wrong})
    assert res.status_code == 401

    # Correct TOTP disables; recovery codes are wiped.
    res = await async_client.post(
        "/api/v1/auth/mfa/disable", headers=headers, json={"code": pyotp.TOTP(secret).now()}
    )
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.json()["mfa_enabled"] is False
    leftover = (
        await db_session.execute(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == mfa_user.id)
        )
    ).scalars().all()
    assert leftover == []

    # Login no longer requires a challenge.
    data = await _login(async_client)
    assert data["mfa_required"] is False
    assert data["access_token"]

    # A second disable attempt is a 409 (nothing to disable).
    headers2 = {"Authorization": f"Bearer {data['access_token']}"}
    res = await async_client.post(
        "/api/v1/auth/mfa/disable", headers=headers2, json={"code": codes[0]}
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_regenerate_recovery_codes(async_client: AsyncClient, mfa_user):
    headers = await _auth_headers(async_client)
    _, codes = await _enroll(async_client, headers)

    # Wrong password → denied.
    res = await async_client.post(
        "/api/v1/auth/mfa/recovery-codes", headers=headers, json={"current_password": "WrongPass1!"}
    )
    assert res.status_code == 401

    # Correct password → new codes; old ones are invalidated.
    res = await async_client.post(
        "/api/v1/auth/mfa/recovery-codes", headers=headers, json={"current_password": PASSWORD}
    )
    assert res.status_code == 200, res.text
    new_codes = res.json()["codes"]
    assert len(new_codes) == mfa_service.RECOVERY_CODE_COUNT
    assert set(new_codes) != set(codes)

    data = await _login(async_client)
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": codes[0]},
    )
    assert res.status_code == 401  # old code invalidated
    data = await _login(async_client)
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": new_codes[0]},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_password_change_invalidates_open_challenge(async_client: AsyncClient, mfa_user):
    headers = await _auth_headers(async_client)
    await _enroll(async_client, headers)

    # Obtain a challenge, then change the password before using it.
    data = await _login(async_client)
    assert data["mfa_required"] is True

    res = await async_client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "NewMfaPass456!"},
    )
    assert res.status_code == 200, res.text

    # Old-challenge verification is refused after the credential version bump.
    res = await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": "000000"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_mfa_security_events_recorded(async_client: AsyncClient, mfa_user, db_session: AsyncSession):
    headers = await _auth_headers(async_client)
    secret, _ = await _enroll(async_client, headers)
    data = await _login(async_client)
    await async_client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": data["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    rows = (
        await db_session.execute(
            select(SecurityEvent.event_type).where(SecurityEvent.user_id == mfa_user.id)
        )
    ).scalars().all()
    types = set(rows)
    assert "MFA_ENROLLMENT_STARTED" in types
    assert "MFA_ENABLED" in types
    assert "MFA_CHALLENGE_ISSUED" in types
    assert "MFA_VERIFICATION_SUCCESS" in types
    # MFA material must never be logged: event metadata on MFA/recovery rows
    # may not contain the plaintext secret or otpauth content.
    stmt = (
        select(SecurityEvent.event_type, SecurityEvent.metadata_payload)
        .where(SecurityEvent.user_id == mfa_user.id)
        .where(SecurityEvent.event_type.like("MFA%"))
    )
    rows = (await db_session.execute(stmt)).all()
    for event_type, payload in rows:
        text = str(payload or {}).lower()
        assert secret.lower() not in text
        assert "otpauth" not in text
        assert "recovery_codes" not in text
