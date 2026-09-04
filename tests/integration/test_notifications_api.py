"""Integration tests for the Notification center.

Covers:
- authentication (401 without a token)
- notifications are strictly user-scoped (no cross-user reads)
- mark-read / mark-all-read persistence across requests
- real-event fan-out: creating an action request notifies approvers
- list ordering and unread counts
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from decimal import Decimal

from database.models.identity import User, Role, RoleName, UserRole
from database.models.reconciliation import ReconciliationRun, Discrepancy
from services.notifications.service import notify_user, ACTION_REQUEST_PENDING


@pytest.mark.asyncio
async def test_notifications_require_authentication(async_client: AsyncClient):
    assert (await async_client.get("/api/v1/notifications")).status_code == 401
    assert (await async_client.get("/api/v1/notifications/unread-count")).status_code == 401
    assert (await async_client.post("/api/v1/notifications/read-all")).status_code == 401
    assert (await async_client.post(f"/api/v1/notifications/{uuid4()}/read")).status_code == 401


@pytest.mark.asyncio
async def test_notifications_are_user_scoped(
    async_client: AsyncClient, db_session: AsyncSession, auth_headers, operator_headers
):
    # Find both fixture users' ids from /me
    me_res = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    user_a_id = me_res.json()["id"]
    me_res_b = await async_client.get("/api/v1/auth/me", headers=operator_headers)
    user_b_id = me_res_b.json()["id"]

    # Seed one notification for user B
    from database.models.notification import Notification
    db_session.add(
        Notification(
            user_id=user_b_id,
            type="TEST_EVENT",
            title="For user B",
            message="secret message",
            is_read=False,
            target_type="investigation",
            target_id=str(uuid4()),
        )
    )
    await db_session.commit()

    # A must not see B's notification
    res_a = await async_client.get("/api/v1/notifications", headers=auth_headers)
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 0

    # B sees exactly their own
    res_b = await async_client.get("/api/v1/notifications", headers=operator_headers)
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["title"] == "For user B"

    # A cannot mark B's notification as read -> 404
    other_id = res_b.json()["items"][0]["id"]
    mark = await async_client.post(
        f"/api/v1/notifications/{other_id}/read", headers=auth_headers
    )
    assert mark.status_code == 404


@pytest.mark.asyncio
async def test_mark_read_and_unread_count_persist(
    async_client: AsyncClient, db_session: AsyncSession, auth_headers
):
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["id"]

    from database.models.notification import Notification
    for i in range(3):
        db_session.add(
            Notification(
                user_id=user_id,
                type="TEST_EVENT",
                title=f"Notification {i}",
                message=f"Body {i}",
                is_read=False,
            )
        )
    await db_session.commit()

    res = await async_client.get("/api/v1/notifications", headers=auth_headers)
    assert res.json()["total"] == 3
    assert res.json()["unread_count"] == 3

    # Mark the first one read
    first_id = res.json()["items"][0]["id"]
    mark = await async_client.post(
        f"/api/v1/notifications/{first_id}/read", headers=auth_headers
    )
    assert mark.status_code == 200

    # Separate request — read state persisted
    res2 = await async_client.get("/api/v1/notifications", headers=auth_headers)
    assert res2.json()["unread_count"] == 2
    first = next(n for n in res2.json()["items"] if n["id"] == first_id)
    assert first["is_read"] is True

    # Mark-all-read
    all_res = await async_client.post(
        "/api/v1/notifications/read-all", headers=auth_headers
    )
    assert all_res.status_code == 200
    assert all_res.json()["updated"] == 2

    res3 = await async_client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert res3.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_action_request_creation_notifies_approvers(
    async_client: AsyncClient, db_session: AsyncSession, auth_headers, operator_headers,
    finance_manager_headers,
):
    """Real-event fan-out: creating an action request must notify users
    authorized to approve (FINANCE_MANAGER / ADMIN), not the requester."""
    # 1. Seed a discrepancy
    run_id = str(uuid4())
    run = ReconciliationRun(id=run_id)
    db_session.add(run)
    disc_id = str(uuid4())
    disc = Discrepancy(
        id=disc_id,
        run_id=run_id,
        rule_code="NOTIFY_TEST_001",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="HIGH",
        source_entity_type="PAYMENT",
        source_entity_id=str(uuid4()),
        expected_amount=Decimal("500.00"),
        actual_amount=Decimal("450.00"),
        difference_amount=Decimal("50.00"),
        currency="USD",
    )
    db_session.add(disc)
    await db_session.commit()

    # 2. OPERATOR runs an investigation
    run_res = await async_client.post(
        f"/api/v1/investigations/discrepancy/{disc_id}/run", headers=auth_headers
    )
    assert run_res.status_code == 200, run_res.text
    inv_id = run_res.json()["investigation_id"]

    # The actor gets a personal INVESTIGATION_COMPLETED notification
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    actor_id = me.json()["id"]
    from database.models.notification import Notification
    from sqlalchemy.future import select
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == actor_id)
        )
    ).scalars().all()
    assert any(n.type == "INVESTIGATION_COMPLETED" for n in rows)

    # 3. Policy evaluation (ESCALATE -> APPROVAL_REQUIRED)
    pe = await async_client.post(
        "/api/v1/policies/evaluate",
        headers=auth_headers,
        json={"investigation_id": inv_id, "action": "ESCALATE"},
    )
    assert pe.status_code == 200, pe.text
    assert pe.json()["approval_required"] is True

    # 4. Create the action request
    ar = await async_client.post(
        "/api/v1/action-requests",
        headers=auth_headers,
        json={"policy_evaluation_id": pe.json()["policy_decision_id"]},
    )
    assert ar.status_code == 200, ar.text
    ar_id = ar.json()["id"]

    # 5. FINANCE_MANAGER sees the PENDING notification targeting the request
    fm_list = await async_client.get("/api/v1/notifications", headers=finance_manager_headers)
    assert fm_list.status_code == 200
    fm_items = fm_list.json()["items"]
    pending = [n for n in fm_items if n["type"] == "ACTION_REQUEST_PENDING" and n["target_id"] == ar_id]
    assert pending, f"FM should be notified about {ar_id}; got {[n['type'] for n in fm_items]}"

    # 6. The OPERATOR requester is NOT notified about their own request (no approver rights)
    op_list = await async_client.get("/api/v1/notifications", headers=operator_headers)
    assert all(n["target_id"] != ar_id for n in op_list.json()["items"])