from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from apps.api.dependencies import get_db_session
from database.models.security import SecurityEvent
from packages.rbac.permissions import Permission

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


@router.get(
    "",
    response_model=List[SecurityEventResponse],
    dependencies=[Depends(require_permission(Permission.VIEW_AUDIT_LOGS))],
)
async def list_security_events(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Fetch security audit events. Restricted to ADMIN users (VIEW_AUDIT_LOGS).
    Results are returned newest first.
    """
    stmt = select(SecurityEvent).order_by(SecurityEvent.created_at.desc())
    
    if event_type:
        stmt = stmt.where(SecurityEvent.event_type == event_type)
    if user_id:
        stmt = stmt.where(SecurityEvent.user_id == user_id)
        
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    return events
