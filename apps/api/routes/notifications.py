from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update

from apps.api.auth import get_current_user
from apps.api.dependencies import get_db_session
from database.models.identity import User
from database.models.notification import Notification
from packages.schemas.notification import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
    ReadAllResponse,
    UnreadCountResponse,
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(get_current_user)],
)


async def _own_unread_count(db: AsyncSession, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return (await db.execute(stmt)).scalar_one()


@router.get("", response_model=NotificationListResponse, summary="List the authenticated user's notifications")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Returns ONLY the authenticated user's own notifications, newest first."""
    total_stmt = (
        select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id)
    )
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    unread = await _own_unread_count(db, current_user.id)

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in rows],
        total=total,
        unread_count=unread,
    )


@router.get("/unread-count", response_model=UnreadCountResponse, summary="Unread notification count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return UnreadCountResponse(unread_count=await _own_unread_count(db, current_user.id))


@router.post("/{notification_id}/read", response_model=MarkReadResponse, summary="Mark one notification as read")
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Marks a notification as read. Users may only touch their own rows."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    notification = (await db.execute(stmt)).scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    await db.commit()
    return MarkReadResponse(ok=True)


@router.post("/read-all", response_model=ReadAllResponse, summary="Mark all notifications as read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    res = await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return ReadAllResponse(updated=res.rowcount or 0)
