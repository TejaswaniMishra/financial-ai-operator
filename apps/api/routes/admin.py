"""Admin identity/user-management API (M8.4).

Every route requires authentication AND the specific permission:
- user-management endpoints        → MANAGE_USERS
- role-management operations       → MANAGE_ROLES

Authorization is DB-backed (require_permission); the request body, headers,
and JWT claims are never consulted for privileges.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from apps.api.dependencies import get_db_session
from database.models.identity import User
from packages.rbac.permissions import Permission
from packages.schemas.admin import (
    AdminUserDetail,
    AdminUserListItem,
    UserRolesUpdateRequest,
)
from services.admin.user_management import (
    AdminUserManagementError,
    AdminUserNotFoundError,
    AdminUserService,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_user)],
)


def _to_list_item(user: User) -> AdminUserListItem:
    roles = [
        ur.role.name.value for ur in user.roles if ur.role is not None
    ]
    return AdminUserListItem(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=roles,
        created_at=user.created_at,
    )


def _to_detail(user: User) -> AdminUserDetail:
    item = _to_list_item(user)
    return AdminUserDetail(**item.model_dump(), updated_at=user.updated_at)


def _map_service_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, AdminUserNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, AdminUserManagementError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred.",
    )


@router.get(
    "/users",
    response_model=List[AdminUserListItem],
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))],
)
async def list_users(
    db=Depends(get_db_session),
):
    service = AdminUserService(db)
    users = await service.list_users()
    return [_to_list_item(u) for u in users]


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetail,
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))],
)
async def get_user(
    user_id: str,
    db=Depends(get_db_session),
):
    service = AdminUserService(db)
    try:
        user = await service.get_user(user_id)
    except AdminUserNotFoundError as exc:
        raise _map_service_errors(exc)
    return _to_detail(user)


@router.post(
    "/users/{user_id}/activate",
    response_model=AdminUserDetail,
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))],
)
async def activate_user(
    user_id: str,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db=Depends(get_db_session),
):
    """Activate a user. Idempotent: activating an active user is a no-op."""
    service = AdminUserService(db)
    try:
        user = await service.activate_user(user_id, actor)
    except (AdminUserNotFoundError, AdminUserManagementError) as exc:
        raise _map_service_errors(exc)
    return _to_detail(user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=AdminUserDetail,
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))],
)
async def deactivate_user(
    user_id: str,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db=Depends(get_db_session),
):
    """Deactivate a user. Idempotent; refuses self-deactivation and never
    leaves the system without an active ADMIN."""
    service = AdminUserService(db)
    try:
        user = await service.deactivate_user(user_id, actor)
    except (AdminUserNotFoundError, AdminUserManagementError) as exc:
        raise _map_service_errors(exc)
    return _to_detail(user)


@router.put(
    "/users/{user_id}/roles",
    response_model=AdminUserDetail,
    dependencies=[Depends(require_permission(Permission.MANAGE_ROLES))],
)
async def replace_user_roles(
    user_id: str,
    payload: UserRolesUpdateRequest,
    actor: User = Depends(require_permission(Permission.MANAGE_ROLES)),
    db=Depends(get_db_session),
):
    """Atomically replace a user's roles (fixed vocabulary only). Never lets
    the final active ADMIN lose the ADMIN role."""
    service = AdminUserService(db)
    try:
        user = await service.replace_user_roles(user_id, payload.roles, actor)
    except (AdminUserNotFoundError, AdminUserManagementError) as exc:
        raise _map_service_errors(exc)
    return _to_detail(user)