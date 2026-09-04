from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database.connection import get_async_db
from services.exceptions import list_exceptions, get_exception_detail
from packages.schemas.exceptions import ExceptionListResponse, ExceptionDetail
from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from packages.rbac.permissions import Permission

router = APIRouter(prefix="/exceptions", tags=["Exceptions"], dependencies=[Depends(get_current_user)])

@router.get("", response_model=ExceptionListResponse, dependencies=[Depends(require_permission(Permission.VIEW_DISCREPANCIES))])
async def get_exceptions(
    session: AsyncSession = Depends(get_async_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[str] = None,
    state: Optional[str] = None,
    currency: Optional[str] = None,
    transaction_type: Optional[str] = None,
):
    return await list_exceptions(
        session=session,
        limit=limit,
        offset=offset,
        discrepancy_type=type,
        overall_state=state,
        currency=currency,
        transaction_type=transaction_type,
    )

@router.get("/{exception_id}", response_model=ExceptionDetail, dependencies=[Depends(require_permission(Permission.VIEW_DISCREPANCIES))])
async def get_exception(
    exception_id: str,
    session: AsyncSession = Depends(get_async_db)
):
    detail = await get_exception_detail(session, exception_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")
    return detail
