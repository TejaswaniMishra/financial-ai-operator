"""Notification emission for real backend events.

Notifications are always derived from genuine state transitions performed by
authoritative services (action-request lifecycle, investigation completion,
period close blocking). Rows are user-scoped: a recipient only ever sees
rows addressed to them. No secrets or internal diagnostics are stored.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.notification import Notification
from database.models.identity import User, UserRole, Role, RoleName

# Notification type vocabulary
ACTION_REQUEST_PENDING = "ACTION_REQUEST_PENDING"
ACTION_REQUEST_APPROVED = "ACTION_REQUEST_APPROVED"
ACTION_REQUEST_REJECTED = "ACTION_REQUEST_REJECTED"
ACTION_REQUEST_CANCELLED = "ACTION_REQUEST_CANCELLED"
INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
INVESTIGATION_FAILED = "INVESTIGATION_FAILED"
PERIOD_BLOCKED = "PERIOD_BLOCKED"
PERIOD_CLOSED = "PERIOD_CLOSED"
# Ingestion (one notification per run, never per record)
INGESTION_COMPLETED_WITH_ERRORS = "INGESTION_COMPLETED_WITH_ERRORS"
INGESTION_FAILED = "INGESTION_FAILED"


async def notify_user(
    db: AsyncSession,
    user_id: str,
    ntype: str,
    title: str,
    message: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Optional[Notification]:
    """Create one notification addressed to a single user."""
    notification = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        target_type=target_type,
        target_id=target_id,
        is_read=False,
    )
    db.add(notification)
    return notification


async def notify_role(
    db: AsyncSession,
    role: RoleName,
    ntype: str,
    title: str,
    message: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> list[str]:
    """Fan out one notification to every active user holding `role`."""
    stmt = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == role, User.is_active.is_(True))
    )
    users = (await db.execute(stmt)).scalars().all()
    created_for: list[str] = []
    for user in users:
        if user.id:
            await notify_user(
                db, user.id, ntype, title, message, target_type, target_id
            )
            created_for.append(user.id)
    return created_for


async def notify_approvers(
    db: AsyncSession,
    ntype: str,
    title: str,
    message: str,
    target_type: str,
    target_id: str,
) -> None:
    """Notify everyone authorized to decide on action requests (FM + ADMIN)."""
    for role in (RoleName.FINANCE_MANAGER, RoleName.ADMIN):
        await notify_role(
            db, role, ntype, title, message, target_type, target_id
        )
