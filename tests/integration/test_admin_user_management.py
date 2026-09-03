"""M8.4 — Admin user & role management API tests.

Covers authentication (401), authorization (403 vs ADMIN access), user
listing/detail, activation/deactivation invariants, atomic role assignment,
the final-active-ADMIN safety rule, immediate DB-backed authorization
effects, and privilege-escalation attempts.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.settings import get_settings
from database.models.identity import RoleName, User, UserRole

settings = get_settings()

ADMIN_USERS_URL = "/api/v1/admin/users"


def _admin_user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "roles": ["ADMIN"],
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ─── Authentication: 401 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_token_is_401(async_client: AsyncClient):
    res = await async_client.get(ADMIN_USERS_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_is_401(async_client: AsyncClient):
    res = await async_client.get(
        ADMIN_USERS_URL, headers={"Authorization": "Bearer bad.token.here"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_revoked_token_is_401(
    async_client: AsyncClient, make_role_user
):
    _, headers = await make_role_user(RoleName.ADMIN, "revoked_admin@example.com")
    out = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    res = await async_client.get(ADMIN_USERS_URL, headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_inactive_admin_is_401(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    user, headers = await make_role_user(RoleName.ADMIN, "inactive_admin@example.com")
    await db_session.execute(
        update(User).where(User.id == user.id).values(is_active=False)
    )
    await db_session.commit()
    res = await async_client.get(ADMIN_USERS_URL, headers=headers)
    assert res.status_code == 401


# ─── Authorization: 403 vs ADMIN ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_operator_is_403(async_client: AsyncClient, operator_headers):
    res = await async_client.get(ADMIN_USERS_URL, headers=operator_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_finance_manager_is_403(async_client: AsyncClient, finance_manager_headers):
    res = await async_client.get(ADMIN_USERS_URL, headers=finance_manager_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_finance_manager_cannot_change_roles(
    async_client: AsyncClient, db_session: AsyncSession,
    finance_manager_headers, make_role_user,
):
    target, _ = await make_role_user(RoleName.OPERATOR, "target_user@example.com")
    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["FINANCE_MANAGER"]},
        headers=finance_manager_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(async_client: AsyncClient, admin_headers):
    res = await async_client.get(ADMIN_USERS_URL, headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ─── User listing ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_listing_safe_fields_and_order(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    # Create users with explicit, distinct created_at values (older than the
    # admin, which is created last at real-now and therefore sorts first)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, email in enumerate(["older@example.com", "middle@example.com", "newest@example.com"]):
        db_session.add(User(
            id=str(uuid.uuid4()), email=email, display_name=f"User {i}",
            is_active=True, created_at=now - timedelta(hours=3 - i),
        ))
    await db_session.commit()

    admin, headers = await make_role_user(RoleName.ADMIN, "list_admin@example.com")

    res = await async_client.get(ADMIN_USERS_URL, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 4
    # Newest first (created_at DESC): the admin was created last
    assert data[0]["email"] == "list_admin@example.com"
    assert data[1]["email"] == "newest@example.com"
    assert data[2]["email"] == "middle@example.com"
    assert data[3]["email"] == "older@example.com"

    for item in data:
        # Safe fields only
        assert set(item.keys()) == {
            "id", "email", "display_name", "is_active", "roles", "created_at",
        }
        assert "password_hash" not in str(item).lower()
        assert "credential" not in str(item).lower()
        assert "jti" not in str(item).lower()


@pytest.mark.asyncio
async def test_user_listing_returns_roles(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "roles_admin@example.com")
    target, _ = await make_role_user(RoleName.FINANCE_MANAGER, "fm_list@example.com")
    res = await async_client.get(ADMIN_USERS_URL, headers=headers)
    data = res.json()
    target_entry = next(u for u in data if u["id"] == target.id)
    assert target_entry["roles"] == ["FINANCE_MANAGER"]


# ─── User detail ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_detail(
    async_client: AsyncClient, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "detail_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "detail_target@example.com")
    res = await async_client.get(f"{ADMIN_USERS_URL}/{target.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == target.id
    assert data["email"] == "detail_target@example.com"
    assert data["roles"] == ["OPERATOR"]
    assert set(data.keys()) == {
        "id", "email", "display_name", "is_active", "roles", "created_at", "updated_at",
    }


@pytest.mark.asyncio
async def test_user_detail_missing_user_is_404(async_client: AsyncClient, admin_headers):
    res = await async_client.get(
        f"{ADMIN_USERS_URL}/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert res.status_code == 404


# ─── Activation ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_inactive_user_and_idempotent(
    async_client: AsyncClient, db_session: AsyncSession, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "act_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "act_target@example.com")
    await db_session.execute(
        update(User).where(User.id == target.id).values(is_active=False)
    )
    await db_session.commit()

    res1 = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/activate", headers=headers
    )
    assert res1.status_code == 200
    assert res1.json()["is_active"] is True

    # Repeated activate is a safe no-op
    res2 = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/activate", headers=headers
    )
    assert res2.status_code == 200
    assert res2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_cycle(
    async_client: AsyncClient, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "cycle_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "cycle_target@example.com")

    deact = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/deactivate", headers=headers
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Repeated deactivate is a safe no-op
    deact2 = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/deactivate", headers=headers
    )
    assert deact2.status_code == 200

    act = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/activate", headers=headers
    )
    assert act.status_code == 200
    assert act.json()["is_active"] is True


# ─── Deactivation invariants ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_self_deactivation_rejected(async_client: AsyncClient, make_role_user):
    admin, headers = await make_role_user(RoleName.ADMIN, "self_admin@example.com")
    res = await async_client.post(
        f"{ADMIN_USERS_URL}/{admin.id}/deactivate", headers=headers
    )
    assert res.status_code == 409
    assert "own account" in res.json()["detail"].lower()
    # No mutation occurred
    me = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["is_active"] is True


@pytest.mark.asyncio
async def test_final_active_admin_cannot_be_deactivated(
    db_session: AsyncSession, make_role_user
):
    """Service-level: the final active ADMIN is protected even when the actor
    is a different (non-admin) service caller."""
    from services.admin.user_management import (
        AdminUserManagementError,
        AdminUserService,
    )

    last_admin, _ = await make_role_user(RoleName.ADMIN, "last_admin@example.com")
    other, _ = await make_role_user(RoleName.OPERATOR, "not_admin@example.com")

    service = AdminUserService(db_session)
    try:
        await service.deactivate_user(last_admin.id, actor=other)
        raise AssertionError("Expected AdminUserManagementError")
    except AdminUserManagementError as exc:
        assert "last active ADMIN" in str(exc)

    # DB unchanged
    row = (await db_session.execute(select(User).where(User.id == last_admin.id))).scalar_one()
    assert row.is_active is True


# ─── Role management ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_each_fixed_role(
    async_client: AsyncClient, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "actor_admin@example.com")
    for role in ["OPERATOR", "FINANCE_MANAGER", "ADMIN"]:
        target, _ = await make_role_user(RoleName.OPERATOR, f"assign_{role.lower()}@example.com")
        res = await async_client.put(
            f"{ADMIN_USERS_URL}/{target.id}/roles",
            json={"roles": [role]},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()["roles"] == [role]


@pytest.mark.asyncio
async def test_multiple_roles_and_duplicate_normalization(
    async_client: AsyncClient, make_role_user
):
    admin, headers = await make_role_user(RoleName.ADMIN, "multi_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "multi_target@example.com")

    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["FINANCE_MANAGER", "OPERATOR", "FINANCE_MANAGER"]},
        headers=headers,
    )
    assert res.status_code == 200
    # Deterministic canonical order, duplicates removed
    assert res.json()["roles"] == ["OPERATOR", "FINANCE_MANAGER"]

    # Replacement is atomic — previous set fully replaced
    res2 = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["OPERATOR"]},
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["roles"] == ["OPERATOR"]


@pytest.mark.asyncio
async def test_invalid_role_rejected(async_client: AsyncClient, make_role_user):
    admin, headers = await make_role_user(RoleName.ADMIN, "invalid_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "invalid_target@example.com")

    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["SUPERUSER"]},
        headers=headers,
    )
    assert res.status_code == 422  # pydantic rejects unknown enum value

    # DB unchanged — still OPERATOR
    detail = await async_client.get(f"{ADMIN_USERS_URL}/{target.id}", headers=headers)
    assert detail.json()["roles"] == ["OPERATOR"]


@pytest.mark.asyncio
async def test_last_active_admin_cannot_lose_admin_role(
    async_client: AsyncClient, make_role_user
):
    """The only active ADMIN (the actor) cannot demote themselves to a
    non-admin role."""
    admin, headers = await make_role_user(RoleName.ADMIN, "solo_admin@example.com")

    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{admin.id}/roles",
        json={"roles": ["OPERATOR"]},
        headers=headers,
    )
    assert res.status_code == 409
    assert "last active ADMIN" in res.json()["detail"]

    me = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["roles"] == ["ADMIN"]


@pytest.mark.asyncio
async def test_admin_can_demote_other_admin_but_not_last(
    async_client: AsyncClient, make_role_user
):
    admin_a, headers_a = await make_role_user(RoleName.ADMIN, "admin_a@example.com")
    admin_b, headers_b = await make_role_user(RoleName.ADMIN, "admin_b@example.com")

    # A demotes B to OPERATOR — allowed, A remains an active ADMIN
    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{admin_b.id}/roles",
        json={"roles": ["OPERATOR"]},
        headers=headers_a,
    )
    assert res.status_code == 200
    assert res.json()["roles"] == ["OPERATOR"]

    # Now A is the last active ADMIN — A cannot demote self
    res2 = await async_client.put(
        f"{ADMIN_USERS_URL}/{admin_a.id}/roles",
        json={"roles": ["OPERATOR"]},
        headers=headers_a,
    )
    assert res2.status_code == 409


# ─── Immediate DB-backed authorization effects ─────────────────────────────

@pytest.mark.asyncio
async def test_role_grant_and_removal_reflected_on_next_me(
    async_client: AsyncClient, make_role_user
):
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "effect_admin@example.com")
    target, target_headers = await make_role_user(RoleName.OPERATOR, "effect_target@example.com")

    me0 = await async_client.get("/api/v1/auth/me", headers=target_headers)
    assert "FINANCE_MANAGER" not in me0.json()["roles"]
    assert "APPROVE_ACTION_REQUEST" not in me0.json()["permissions"]

    # Grant FINANCE_MANAGER → next /me reflects it
    grant = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["OPERATOR", "FINANCE_MANAGER"]},
        headers=admin_headers,
    )
    assert grant.status_code == 200

    me1 = await async_client.get("/api/v1/auth/me", headers=target_headers)
    assert "FINANCE_MANAGER" in me1.json()["roles"]
    assert "APPROVE_ACTION_REQUEST" in me1.json()["permissions"]

    # Remove FINANCE_MANAGER → next /me drops the permissions
    revoke = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["OPERATOR"]},
        headers=admin_headers,
    )
    assert revoke.status_code == 200

    me2 = await async_client.get("/api/v1/auth/me", headers=target_headers)
    assert "FINANCE_MANAGER" not in me2.json()["roles"]
    assert "APPROVE_ACTION_REQUEST" not in me2.json()["permissions"]


@pytest.mark.asyncio
async def test_deactivated_user_next_request_is_401(
    async_client: AsyncClient, make_role_user
):
    admin, admin_headers = await make_role_user(RoleName.ADMIN, "deact_admin@example.com")
    target, target_headers = await make_role_user(RoleName.OPERATOR, "deact_target@example.com")

    ok = await async_client.get("/api/v1/metrics/overview", headers=target_headers)
    assert ok.status_code == 200

    deact = await async_client.post(
        f"{ADMIN_USERS_URL}/{target.id}/deactivate", headers=admin_headers
    )
    assert deact.status_code == 200

    denied = await async_client.get("/api/v1/metrics/overview", headers=target_headers)
    assert denied.status_code == 401


# ─── Privilege escalation attempts ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_fake_role_and_permissions_in_body_cannot_elevate(
    async_client: AsyncClient, make_role_user
):
    operator, operator_headers = await make_role_user(RoleName.OPERATOR, "escalate_op@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "escalate_target@example.com")

    res = await async_client.put(
        f"{ADMIN_USERS_URL}/{target.id}/roles",
        json={"roles": ["OPERATOR"], "role": "ADMIN", "permissions": ["MANAGE_USERS"]},
        headers=operator_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_fake_role_header_cannot_elevate(
    async_client: AsyncClient, operator_headers
):
    headers = {**operator_headers, "X-Role": "ADMIN", "X-User-Roles": "ADMIN"}
    res = await async_client.get(ADMIN_USERS_URL, headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_forged_jwt_role_claims_cannot_elevate(
    async_client: AsyncClient, make_role_user
):
    operator, _ = await make_role_user(RoleName.OPERATOR, "forged_jwt@example.com")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": operator.id,
        "iat": now,
        "exp": now + timedelta(minutes=10),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "roles": ["ADMIN"],
        "permissions": ["MANAGE_USERS", "MANAGE_ROLES"],
    }
    forged = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    forged_headers = {"Authorization": f"Bearer {forged}"}

    res = await async_client.get(ADMIN_USERS_URL, headers=forged_headers)
    assert res.status_code == 403


# ─── Service-level guarantees ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_list_empty_db_returns_empty(db_session: AsyncSession):
    from services.admin.user_management import AdminUserService

    service = AdminUserService(db_session)
    assert await service.list_users() == []


@pytest.mark.asyncio
async def test_service_rejects_unknown_role_token(
    db_session: AsyncSession, make_role_user
):
    from services.admin.user_management import (
        AdminUserManagementError,
        AdminUserService,
    )

    admin, _ = await make_role_user(RoleName.ADMIN, "svc_admin@example.com")
    target, _ = await make_role_user(RoleName.OPERATOR, "svc_target@example.com")
    service = AdminUserService(db_session)

    with pytest.raises(AdminUserManagementError):
        await service.replace_user_roles(target.id, ["SUPERUSER"], actor=admin)  # type: ignore[list-item]