"""M8.5 — Secure password management tests.

Covers self-service password change, ADMIN-initiated password reset, forced
password change, credential-version session invalidation, one-time temporary
credential semantics, authorization attacks, concurrency safety, and the
no-leak guarantees (no password/hash/token material in responses).
"""

import asyncio
import logging
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.identity import RoleName, User, UserCredential
from packages.utils.crypto import verify_password
from packages.utils.jwt import create_access_token, decode_access_token
from config.settings import get_settings

settings = get_settings()

CHANGE_PASSWORD_URL = "/api/v1/auth/change-password"
ADMIN_USERS_URL = "/api/v1/admin/users"

CURRENT_PW = "ValidPassword123!"
NEW_PW = "BrandNewPassword456!"


async def _login(client: AsyncClient, email: str, password: str) -> dict | None:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    if res.status_code != 200:
        return None
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _credential_hash(db: AsyncSession, user_id: str) -> str:
    # Column-only select: bypasses the session identity map so the value is
    # always freshly read from the database (the app commits on its own
    # session/connection, and db_session caches with expire_on_commit=False).
    stmt = select(UserCredential.password_hash).where(UserCredential.user_id == user_id)
    return (await db.execute(stmt)).scalar_one()


async def _user_version(db: AsyncSession, user_id: int) -> int:
    stmt = select(User.credential_version).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one() or 1


# ─── Self-service password change ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success_roundtrip(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_success@example.com")
    headers = await _login(async_client, "pw_success@example.com", CURRENT_PW)
    assert headers is not None

    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": NEW_PW},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert "message" in body
    # No password/hash/credential/token material in the response
    raw = res.text.lower()
    for forbidden in ["password_hash", "hash", "token", "jti", "credential"]:
        assert forbidden not in raw

    # Old password no longer works
    assert await _login(async_client, "pw_success@example.com", CURRENT_PW) is None
    # New password works
    assert await _login(async_client, "pw_success@example.com", NEW_PW) is not None


@pytest.mark.asyncio
async def test_change_password_wrong_current_is_400(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_wrong_current@example.com")
    headers = await _login(async_client, "pw_wrong_current@example.com", CURRENT_PW)
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "WrongPassword999!", "new_password": NEW_PW},
        headers=headers,
    )
    assert res.status_code == 400
    assert "incorrect" in res.json()["detail"].lower()
    # Password unchanged
    assert await _login(async_client, "pw_wrong_current@example.com", CURRENT_PW) is not None


@pytest.mark.asyncio
async def test_change_password_weak_new_is_422(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_weak_new@example.com")
    headers = await _login(async_client, "pw_weak_new@example.com", CURRENT_PW)
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": "short"},
        headers=headers,
    )
    assert res.status_code == 422
    # Original credential untouched
    assert await _login(async_client, "pw_weak_new@example.com", CURRENT_PW) is not None


@pytest.mark.asyncio
async def test_change_password_same_password_is_400(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_same@example.com")
    headers = await _login(async_client, "pw_same@example.com", CURRENT_PW)
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": CURRENT_PW},
        headers=headers,
    )
    assert res.status_code == 400
    assert "different" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_unauthenticated_is_401(async_client: AsyncClient):
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": NEW_PW},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_change_password_inactive_user_is_401(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    from sqlalchemy import update

    user, headers = await make_role_user(RoleName.OPERATOR, "pw_inactive@example.com")
    await db_session.execute(
        update(User).where(User.id == user.id).values(is_active=False)
    )
    await db_session.commit()
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": NEW_PW},
        headers=headers,
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_change_password_invalidates_all_existing_tokens(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Every token issued BEFORE the change (not just the current one) dies."""
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_all_tokens@example.com")
    token_a = create_access_token(user.id, credential_version=await _user_version(db_session, user.id))
    token_b = create_access_token(user.id, credential_version=await _user_version(db_session, user.id))

    # Both tokens work before the change
    for token in (token_a, token_b):
        res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    headers = await _login(async_client, "pw_all_tokens@example.com", CURRENT_PW)
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": CURRENT_PW, "new_password": NEW_PW},
        headers=headers,
    )
    assert res.status_code == 200

    # Both pre-change tokens are now rejected (401)
    for token in (token_a, token_b):
        res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    # Version was bumped
    assert await _user_version(db_session, user.id) == 2


@pytest.mark.asyncio
async def test_change_password_body_user_id_is_ignored(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Self-service can NEVER target another user via a body field."""
    actor, _ = await make_role_user(RoleName.OPERATOR, "pw_self_only@example.com")
    other, _ = await make_role_user(RoleName.OPERATOR, "pw_self_other@example.com")

    headers = await _login(async_client, "pw_self_only@example.com", CURRENT_PW)
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={
            "current_password": CURRENT_PW,
            "new_password": NEW_PW,
            "user_id": other.id,  # must be ignored
            "roles": ["ADMIN"],   # must be ignored
        },
        headers=headers,
    )
    assert res.status_code == 200

    # Actor changed; the OTHER user is completely untouched
    assert await _login(async_client, "pw_self_only@example.com", NEW_PW) is not None
    assert await _login(async_client, "pw_self_other@example.com", CURRENT_PW) is not None
    other_user = (
        await db_session.execute(select(User).where(User.id == other.id))
    ).scalar_one()
    assert other_user.credential_version == 1
    assert other_user.must_change_password is False


# ─── Admin password reset ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_reset_full_forced_change_flow(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Reset → temp credential login → forced change → access restored."""
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "reset_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_target@example.com")

    old_hash = await _credential_hash(db_session, target.id)
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    temp = data["temporary_password"]
    assert len(temp) >= 12
    assert data["must_change_password"] is True

    # DB stores a NEW Argon2id hash of the temp credential — never plaintext
    new_hash = await _credential_hash(db_session, target.id)
    assert new_hash != old_hash
    assert verify_password(temp, new_hash) is True
    assert temp not in new_hash  # plaintext is not embedded
    assert await _user_version(db_session, target.id) == 2

    # Target can authenticate with the temporary credential
    temp_headers = await _login(async_client, "reset_target@example.com", temp)
    assert temp_headers is not None
    # /me reports the backend-controlled flag
    me = await async_client.get("/api/v1/auth/me", headers=temp_headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True
    # Normal protected functionality is DENIED while forced
    denied = await async_client.get("/api/v1/metrics/overview", headers=temp_headers)
    assert denied.status_code == 403

    # Forced change via the temp credential as current password
    res = await async_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": temp, "new_password": NEW_PW},
        headers=temp_headers,
    )
    assert res.status_code == 200

    # Flag cleared and access restored with a fresh login
    fresh = await _login(async_client, "reset_target@example.com", NEW_PW)
    assert fresh is not None
    me = await async_client.get("/api/v1/auth/me", headers=fresh)
    assert me.json()["must_change_password"] is False
    ok = await async_client.get("/api/v1/metrics/overview", headers=fresh)
    assert ok.status_code == 200

    # The one-time temporary credential cannot be reused
    assert await _login(async_client, "reset_target@example.com", temp) is None


@pytest.mark.asyncio
async def test_admin_reset_invalidates_all_target_sessions(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "reset_admin2@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_target2@example.com")

    version = await _user_version(db_session, target.id)
    token_a = create_access_token(target.id, credential_version=version)
    token_b = create_access_token(target.id, credential_version=version)
    assert (await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})).status_code == 200
    assert (await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})).status_code == 200

    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=admin_headers,
    )
    assert res.status_code == 200

    for token in (token_a, token_b):
        res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_reset_missing_user_is_404(
    async_client: AsyncClient, admin_headers
):
    ghost = str(uuid.uuid4())
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{ghost}/password-reset",
        headers=admin_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_reset_operator_is_403(async_client: AsyncClient, operator_headers, make_role_user):
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_op_target@example.com")
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=operator_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_reset_finance_manager_is_403(
    async_client: AsyncClient, finance_manager_headers, make_role_user
):
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_fm_target@example.com")
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=finance_manager_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_reset_self(
    async_client: AsyncClient, make_role_user
):
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "reset_self@example.com")
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{admin.id}/password-reset",
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert "own account" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_reset_plaintext_never_persisted(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Generated temporary passwords never appear in the database."""
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "reset_pt_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_pt_target@example.com")

    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=admin_headers,
    )
    temp = res.json()["temporary_password"]

    rows = (await db_session.execute(select(UserCredential))).scalars().all()
    hashes = [r.password_hash for r in rows]
    assert temp not in hashes
    assert all(temp not in h for h in hashes)  # not embedded anywhere

    # A second reset produces a DIFFERENT credential
    res2 = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers=admin_headers,
    )
    assert res2.json()["temporary_password"] != temp


# ─── Authorization attacks ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forged_role_body_and_header_cannot_reset(
    async_client: AsyncClient, make_role_user
):
    operator, operator_headers = await make_role_user(
        RoleName.OPERATOR, "reset_forge_op@example.com"
    )
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_forge_t@example.com")

    headers = {
        **operator_headers,
        "X-Role": "ADMIN",
        "X-User-Roles": "ADMIN",
        "X-Permissions": "MANAGE_USERS",
    }
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        json={"role": "ADMIN", "roles": ["ADMIN"], "permissions": ["MANAGE_USERS"]},
        headers=headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_forged_jwt_role_claims_cannot_reset(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    operator, _ = await make_role_user(RoleName.OPERATOR, "reset_forge_jwt@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_forge_jwt_t@example.com")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": operator.id,
        "iat": now,
        "exp": now + timedelta(minutes=10),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "cver": await _user_version(db_session, operator.id),
        "roles": ["ADMIN"],
        "permissions": ["MANAGE_USERS"],
    }
    forged = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/password-reset",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_stale_credential_version_token_is_401(
    async_client: AsyncClient, make_role_user
):
    """A validly signed token from a previous credential version is rejected."""
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_stale_cver@example.com")
    stale = create_access_token(user.id, credential_version=99)
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {stale}"})
    assert res.status_code == 401

    fresh = create_access_token(user.id, credential_version=1)
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh}"})
    assert res.status_code == 200


# ─── Concurrency ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_password_changes_are_serialized(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Two simultaneous changes with the same current password: exactly one
    succeeds; the second is rejected (its current password is now stale)."""
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_conc_change@example.com")
    headers_a = await _login(async_client, "pw_conc_change@example.com", CURRENT_PW)
    headers_b = await _login(async_client, "pw_conc_change@example.com", CURRENT_PW)

    r1, r2 = await asyncio.gather(
        async_client.post(
            CHANGE_PASSWORD_URL,
            json={"current_password": CURRENT_PW, "new_password": "FirstNewPass456!"},
            headers=headers_a,
        ),
        async_client.post(
            CHANGE_PASSWORD_URL,
            json={"current_password": CURRENT_PW, "new_password": "SecondNewPass789!"},
            headers=headers_b,
        ),
    )
    statuses = {r1.status_code, r2.status_code}
    assert 200 in statuses
    assert statuses <= {200, 400}  # no 500s, no silent double-success overwrites
    assert await _user_version(db_session, user.id) == 2


@pytest.mark.asyncio
async def test_concurrent_admin_resets_keep_consistent_state(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    """Concurrent resets of the same target serialize; the final credential is
    exactly one of the generated temporaries and the forced flag holds."""
    admin_a, headers_a = await make_role_user(RoleName.ADMIN, "reset_conc_a@example.com")
    admin_b, headers_b = await make_role_user(RoleName.ADMIN, "reset_conc_b@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "reset_conc_t@example.com")

    r1, r2 = await asyncio.gather(
        async_client.post(f"{ADMIN_USERS_URL}/{target.id}/password-reset", headers=headers_a),
        async_client.post(f"{ADMIN_USERS_URL}/{target.id}/password-reset", headers=headers_b),
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    temps = {r1.json()["temporary_password"], r2.json()["temporary_password"]}
    assert len(temps) == 2  # distinct one-time credentials
    final_hash = await _credential_hash(db_session, target.id)
    assert any(verify_password(t, final_hash) for t in temps)

    # Column-only reads: the session identity map would otherwise return a
    # stale pre-reset User instance.
    must_change = (
        await db_session.execute(
            select(User.must_change_password).where(User.id == target.id)
        )
    ).scalar_one()
    version = (
        await db_session.execute(
            select(User.credential_version).where(User.id == target.id)
        )
    ).scalar_one()
    assert must_change is True
    assert version == 3  # two bumps, no lost update


# ─── Security event logging ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_events_logged_without_passwords(
    async_client: AsyncClient, make_role_user, caplog
):
    with caplog.at_level(logging.INFO, logger="fao.security"):
        user, headers = await make_role_user(RoleName.OPERATOR, "pw_events@example.com")
        res = await async_client.post(
            CHANGE_PASSWORD_URL,
            json={"current_password": CURRENT_PW, "new_password": NEW_PW},
            headers=headers,
        )
        assert res.status_code == 200
        # The change invalidated the old token; log in again for a fresh one,
        # then make a failed attempt (wrong current password) so the service
        # layer emits PASSWORD_CHANGE_FAILED.
        fresh = await _login(async_client, "pw_events@example.com", NEW_PW)
        assert fresh is not None
        await async_client.post(
            CHANGE_PASSWORD_URL,
            json={"current_password": "TotallyWrong999!", "new_password": NEW_PW},
            headers=fresh,
        )

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "PASSWORD_CHANGED" in messages
    assert "PASSWORD_CHANGE_FAILED" in messages
    # Never any password material in logs
    assert CURRENT_PW not in messages
    assert NEW_PW not in messages


# ─── Regression sanity (full suites cover these in depth) ──────────────────

@pytest.mark.asyncio
async def test_signup_still_works_with_security_columns(
    async_client: AsyncClient, db_session: AsyncSession
):
    res = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "display_name": "M8.5 Signup",
            "email": "m85_signup@example.com",
            "password": CURRENT_PW,
        },
    )
    assert res.status_code == 201
    user = (
        await db_session.execute(select(User).where(User.email == "m85_signup@example.com"))
    ).scalar_one()
    assert user.credential_version == 1
    assert user.must_change_password is False
    # New user can log in and reach protected routes
    headers = await _login(async_client, "m85_signup@example.com", CURRENT_PW)
    res = await async_client.get("/api/v1/metrics/overview", headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_logout_and_revocation_still_work(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_logout@example.com")
    headers = await _login(async_client, "pw_logout@example.com", CURRENT_PW)
    assert headers is not None
    res = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert res.status_code == 200
    # Token is revoked
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    # A fresh token for the same user still works (per-token revocation)
    fresh = await _login(async_client, "pw_logout@example.com", CURRENT_PW)
    res = await async_client.get("/api/v1/auth/me", headers=fresh)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_me_contract_includes_safe_boolean_only(
    async_client: AsyncClient, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "pw_me_contract@example.com")
    headers = await _login(async_client, "pw_me_contract@example.com", CURRENT_PW)
    me = (await async_client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["must_change_password"] is False
    assert "credential_version" not in me  # internal counter stays private
    assert "password_hash" not in me
    assert "cver" not in me
