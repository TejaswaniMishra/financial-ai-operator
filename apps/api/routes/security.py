from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from apps.api.dependencies import get_db_session
from database.models.security import SecurityEvent, SecurityEventType
from packages.rbac.permissions import Permission
import uuid

router = APIRouter(
    prefix="/admin/security-events",
    tags=["Security Audit"],
    dependencies=[Depends(get_current_user)],
)

class SecurityEventResponse(BaseModel):
    id: str
    event_type: str
    user_id: Optional[str]
    actor_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_success: bool
    metadata_payload: Optional[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityEventPaginatedResponse(BaseModel):
    items: List[SecurityEventResponse]
    total: int
    limit: int
    offset: int


def validate_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


@router.get(
    "",
    response_model=SecurityEventPaginatedResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_AUDIT_LOGS))],
)
async def list_security_events(
    event_type: Optional[SecurityEventType] = None,
    user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    is_success: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Fetch security audit events. Restricted to ADMIN users (VIEW_AUDIT_LOGS).
    Results are returned newest first (created_at DESC, id DESC).
    """
    if user_id and not validate_uuid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id format")
    if actor_id and not validate_uuid(actor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid actor_id format")
        
    stmt = select(SecurityEvent)
    
    if event_type:
        stmt = stmt.where(SecurityEvent.event_type == event_type.value)
    if user_id:
        stmt = stmt.where(SecurityEvent.user_id == user_id)
    if actor_id:
        stmt = stmt.where(SecurityEvent.actor_id == actor_id)
    if is_success is not None:
        stmt = stmt.where(SecurityEvent.is_success == is_success)
    if start_time:
        stmt = stmt.where(SecurityEvent.created_at >= start_time.replace(tzinfo=None))
    if end_time:
        stmt = stmt.where(SecurityEvent.created_at <= end_time.replace(tzinfo=None))
        
    # Count total matching records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()
    
    # Apply ordering and pagination
    stmt = stmt.order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    return SecurityEventPaginatedResponse(
        items=list(events),
        total=total_count,
        limit=limit,
        offset=offset
    )
