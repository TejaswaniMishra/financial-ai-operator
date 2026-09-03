"""M8.3 — Backend-enforced RBAC tests.

These tests exercise the real authorization layer against the real database
(no mocks of the authorization path): users, roles, and UserRole rows are
created in SQLite, and the FastAPI endpoints enforce permissions using the
same dependency chain production uses.

401 = unauthenticated. 403 = authenticated but not permitted.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.authorization import require_permission
from config.settings import get_settings
from database.models.action_request import ActionRequest, ActionRequestStatus
from database.models.identity import RoleName, Role, User, UserRole
from database.models.investigation import Investigation, InvestigationStatus
from database.models.policy import PolicyDecision, PolicyEvaluation, PolicyAction
from database.models.reconciliation import Discrepancy, ReconciliationRun
from packages.rbac.matrix import (
    ROLE_PERMISSIONS,
    permissions_for_roles,
    user_has_permission,
)
from packages.rbac.permissions import Permission

settings = get_settings()


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_discrepancy(db_session: AsyncSession) -> str:
    from decimal import Decimal

    run = ReconciliationRun(id=str(uuid.uuid4()))
    db_session.add(run)
    disc = Discrepancy(
        id=str(uuid.uuid4()),
        run_id=run.id,
        rule_code="RBAC_TEST_001",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="HIGH",
        source_entity_type="PAYMENT",
        source_entity_id=str(uuid.uuid4()),
        expected_amount=Decimal("500.00"),
        actual_amount=Decimal("450.00"),
        difference_amount=Decimal("50.00"),
        currency="USD",
    )
    db_session.add(disc)
    await db_session.commit()
    return disc.id


@pytest_asyncio.fixture
async def sample_action_request(db_session: AsyncSession) -> str:
    inv = Investigation(
        id=str(uuid.uuid4()),
        discrepancy_id=str(uuid.uuid4()),
        status=InvestigationStatus.COMPLETED,
    )
    db_session.add(inv)
    evaluation = PolicyEvaluation(
        id=str(uuid.uuid4()),
        investigation_id=inv.id,
        discrepancy_id=inv.discrepancy_id,
        action=PolicyAction.RESOLVE_DISCREPANCY,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        rule_code="RBAC_POLICY",
        reason="test",
        approval_required=True,
    )
    db_session.add(evaluation)
    request = ActionRequest(
        id=str(uuid.uuid4()),
        investigation_id=inv.id,
        discrepancy_id=inv.discrepancy_id,
        policy_evaluation_id=evaluation.id,
        action=evaluation.action.value,
        status=ActionRequestStatus.PENDING_APPROVAL,
    )
    db_session.add(request)
    await db_session.commit()
    return request.id


async def load_user_with_roles(db_session: AsyncSession, user_id: str) -> User:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    return (await db_session.execute(stmt)).scalar_one()


def signed_token_with_claims(user_id: str, extra_claims: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=10),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        **extra_claims,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ─── 1–3: OPERATOR view/run capabilities ───────────────────────────────────

@pytest.mark.asyncio
async def test_operator_can_view_dashboard(async_client: AsyncClient, operator_headers):
    res = await async_client.get("/api/v1/metrics/overview", headers=operator_headers)
    assert res.status_code == 200
    assert "payments" in res.json()


@pytest.mark.asyncio
async def test_operator_can_view_investigations(async_client: AsyncClient, operator_headers):
    res = await async_client.get("/api/v1/investigations", headers=operator_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_operator_can_run_investigation(
    async_client: AsyncClient, seeded_discrepancy: str, operator_headers
):
    res = await async_client.post(
        f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run",
        headers=operator_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"


# ─── 4–6: OPERATOR is blocked from financial decisions ─────────────────────

@pytest.mark.asyncio
async def test_operator_cannot_approve_action_request(
    async_client: AsyncClient, sample_action_request: str, operator_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "operator"},
        headers=operator_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_reject_action_request(
    async_client: AsyncClient, sample_action_request: str, operator_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/reject",
        json={"reason": "no"},
        headers=operator_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_execute_action_request(
    async_client: AsyncClient, sample_action_request: str, operator_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/execute",
        json={"idempotency_key": "op_exec"},
        headers=operator_headers,
    )
    assert res.status_code == 403


# ─── 7–9: FINANCE_MANAGER financial capabilities ───────────────────────────

@pytest.mark.asyncio
async def test_finance_manager_can_approve_action_request(
    async_client: AsyncClient, sample_action_request: str, finance_manager_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "fm"},
        headers=finance_manager_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_finance_manager_can_reject_action_request(
    async_client: AsyncClient, sample_action_request: str, finance_manager_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/reject",
        json={"reason": "bad data"},
        headers=finance_manager_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_finance_manager_executes_only_through_existing_gates(
    async_client: AsyncClient, sample_action_request: str, finance_manager_headers
):
    # Gate 1: cannot execute a PENDING_APPROVAL request (approval required)
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/execute",
        json={"idempotency_key": "fm_gate_1"},
        headers=finance_manager_headers,
    )
    assert res.status_code == 400
    assert "cannot be executed. Status is PENDING_APPROVAL" in res.json()["detail"]

    # Gate 2: after approval, execution is allowed
    approve = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "fm"},
        headers=finance_manager_headers,
    )
    assert approve.status_code == 200

    exec_res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/execute",
        json={"idempotency_key": "fm_gate_2"},
        headers=finance_manager_headers,
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "SUCCEEDED"


# ─── 10–11: administrative permissions ─────────────────────────────────────

@pytest.mark.asyncio
async def test_finance_manager_cannot_manage_users(
    db_session: AsyncSession, make_role_user
):
    user, _ = await make_role_user(RoleName.FINANCE_MANAGER, "fm_noadmin@example.com")
    user = await load_user_with_roles(db_session, user.id)

    assert user_has_permission(user, Permission.MANAGE_USERS) is False
    assert user_has_permission(user, Permission.MANAGE_ROLES) is False

    # The real dependency must raise 403 for a DB-backed FM user
    dep = require_permission(Permission.MANAGE_USERS)
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_has_administrative_permissions(
    db_session: AsyncSession, make_role_user
):
    user, _ = await make_role_user(RoleName.ADMIN, "admin_rbac@example.com")
    user = await load_user_with_roles(db_session, user.id)

    assert user_has_permission(user, Permission.MANAGE_USERS) is True
    assert user_has_permission(user, Permission.MANAGE_ROLES) is True
    # ADMIN inherits FINANCE_MANAGER + OPERATOR capabilities
    assert user_has_permission(user, Permission.APPROVE_ACTION_REQUEST) is True
    assert user_has_permission(user, Permission.EXECUTE_ACTION) is True
    assert user_has_permission(user, Permission.VIEW_DASHBOARD) is True

    # The real dependency admits a DB-backed ADMIN user
    dep = require_permission(Permission.MANAGE_ROLES)
    returned = await dep(current_user=user)
    assert returned.id == user.id


@pytest.mark.asyncio
async def test_admin_can_approve_through_api(
    async_client: AsyncClient, sample_action_request: str, admin_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "admin"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "APPROVED"


# ─── 12–13: 401 semantics ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_request_is_401(async_client: AsyncClient):
    res = await async_client.get("/api/v1/metrics/overview")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_is_401(async_client: AsyncClient, db_session: AsyncSession):
    from packages.utils.jwt import create_access_token

    user = User(
        email="inactive_rbac@example.com",
        display_name="Inactive",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id)

    res = await async_client.get(
        "/api/v1/metrics/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401


# ─── 14–16: privilege escalation attempts ──────────────────────────────────

@pytest.mark.asyncio
async def test_fake_role_in_body_cannot_elevate(
    async_client: AsyncClient, sample_action_request: str, operator_headers
):
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "operator", "role": "ADMIN", "roles": ["ADMIN"]},
        headers=operator_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_fake_role_in_headers_cannot_elevate(
    async_client: AsyncClient, sample_action_request: str, operator_headers
):
    headers = {**operator_headers, "X-Role": "ADMIN", "X-User-Roles": "ADMIN"}
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "operator"},
        headers=headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_jwt_role_claims_cannot_elevate(
    async_client: AsyncClient, sample_action_request: str, make_role_user
):
    user, _ = await make_role_user(RoleName.OPERATOR, "jwt_claim_user@example.com")
    forged_token = signed_token_with_claims(
        user.id,
        {"roles": ["ADMIN"], "role": "ADMIN", "permissions": ["MANAGE_USERS"]},
    )
    forged_headers = {"Authorization": f"Bearer {forged_token}"}

    # /me reports only DB-authoritative roles, never JWT claims
    me = await async_client.get("/api/v1/auth/me", headers=forged_headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["OPERATOR"]
    assert "MANAGE_USERS" not in me.json()["permissions"]

    # And a forged-role token still cannot approve
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "forged"},
        headers=forged_headers,
    )
    assert res.status_code == 403


# ─── 17: multi-role union ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_roles_yield_union_of_permissions(
    async_client: AsyncClient,
    sample_action_request: str,
    db_session: AsyncSession,
    make_role_user,
):
    user, headers = await make_role_user(RoleName.OPERATOR, "multi_role@example.com")
    # Grant FINANCE_MANAGER as a second role (database remains authoritative)
    fm_role = (
        await db_session.execute(select(Role).where(Role.name == RoleName.FINANCE_MANAGER))
    ).scalar_one_or_none()
    if fm_role is None:
        fm_role = Role(name=RoleName.FINANCE_MANAGER, description="Finance Manager")
        db_session.add(fm_role)
        await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=fm_role.id))
    await db_session.commit()

    me = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    data = me.json()
    assert set(data["roles"]) == {"OPERATOR", "FINANCE_MANAGER"}
    assert "VIEW_DASHBOARD" in data["permissions"]  # from OPERATOR
    assert "APPROVE_ACTION_REQUEST" in data["permissions"]  # from FINANCE_MANAGER

    # Union means approval now works
    res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "multi"},
        headers=headers,
    )
    assert res.status_code == 200


# ─── 18: role removal takes effect immediately ─────────────────────────────

@pytest.mark.asyncio
async def test_removing_role_changes_authorization_immediately(
    async_client: AsyncClient,
    sample_action_request: str,
    db_session: AsyncSession,
    make_role_user,
):
    user, headers = await make_role_user(RoleName.FINANCE_MANAGER, "revoked_fm@example.com")

    ok = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "fm"},
        headers=headers,
    )
    assert ok.status_code == 200

    # Revoke the role directly in the DB — the next request must reflect it
    await db_session.execute(delete(UserRole).where(UserRole.user_id == user.id))
    await db_session.commit()

    denied = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "fm"},
        headers=headers,
    )
    assert denied.status_code == 403


# ─── 19: deterministic mapping ─────────────────────────────────────────────

def test_permission_mapping_is_deterministic_and_correct():
    # Exact matrix assertions (hierarchy + no accidental grants)
    assert ROLE_PERMISSIONS[RoleName.OPERATOR] == frozenset({
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_RECONCILIATION,
        Permission.VIEW_DISCREPANCIES,
        Permission.VIEW_INVESTIGATIONS,
        Permission.RUN_INVESTIGATION,
        Permission.VIEW_ACTION_REQUESTS,
        Permission.VIEW_TRANSACTIONS,
        Permission.VIEW_SETTINGS,
    })
    assert ROLE_PERMISSIONS[RoleName.FINANCE_MANAGER] == (
        ROLE_PERMISSIONS[RoleName.OPERATOR]
        | frozenset({
            Permission.APPROVE_ACTION_REQUEST,
            Permission.REJECT_ACTION_REQUEST,
            Permission.CANCEL_ACTION_REQUEST,
            Permission.EXECUTE_ACTION,
        })
    )
    assert ROLE_PERMISSIONS[RoleName.ADMIN] == (
        ROLE_PERMISSIONS[RoleName.FINANCE_MANAGER]
        | frozenset({Permission.MANAGE_USERS, Permission.MANAGE_ROLES})
    )

    # OPERATOR can never touch financial decisions or administration
    assert Permission.APPROVE_ACTION_REQUEST not in ROLE_PERMISSIONS[RoleName.OPERATOR]
    assert Permission.EXECUTE_ACTION not in ROLE_PERMISSIONS[RoleName.OPERATOR]
    assert Permission.MANAGE_USERS not in ROLE_PERMISSIONS[RoleName.FINANCE_MANAGER]

    # Deterministic: same input, same output
    a = permissions_for_roles([RoleName.ADMIN, RoleName.OPERATOR])
    b = permissions_for_roles([RoleName.OPERATOR, RoleName.ADMIN])
    assert a == b


# ─── 20: financial safety gates remain intact ──────────────────────────────

@pytest.mark.asyncio
async def test_financial_safety_gates_remain_intact(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sample_action_request: str,
    finance_manager_headers,
):
    # Rejected requests cannot be executed even by a permitted role
    reject = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/reject",
        json={"reason": "gate"},
        headers=finance_manager_headers,
    )
    assert reject.status_code == 200

    exec_res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/execute",
        json={"idempotency_key": "gate_rejected"},
        headers=finance_manager_headers,
    )
    assert exec_res.status_code == 400
    assert "cannot be executed" in exec_res.json()["detail"]


@pytest.mark.asyncio
async def test_operator_cannot_execute_even_approved_request(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sample_action_request: str,
    finance_manager_headers,
    operator_headers,
):
    # A request that IS approved still cannot be executed by OPERATOR
    approve = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/approve",
        json={"actor": "fm"},
        headers=finance_manager_headers,
    )
    assert approve.status_code == 200

    exec_res = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request}/execute",
        json={"idempotency_key": "op_approved_exec"},
        headers=operator_headers,
    )
    assert exec_res.status_code == 403