"""Admin user-management service (M8.4).

Encapsulates listing users, fetching a user, activating/deactivating users,
and atomically replacing role assignments. Business rules live here, not in
route handlers.

Safety invariants enforced by this service:
- An admin cannot deactivate their own account (self-lockout prevention).
- The final active ADMIN can never be deactivated or lose the ADMIN role.
- Role updates are atomic (single transaction) and normalized against the
  fixed RoleName vocabulary.
"""

import asyncio
import weakref
from datetime import datetime, timezone
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database.models.identity import RoleName, Role, User, UserRole


# Serializes the read-check-commit critical sections of admin mutations so the
# last-active-ADMIN invariant cannot be raced away by concurrent requests.
# Correct for this single-process deployment; a multi-worker deployment would
# additionally require a DB-level guarantee.
#
# The lock is cached per running event loop: in production all requests share
# one loop (so all mutations serialize), while test runners that create a fresh
# loop per test never reuse a loop-bound lock.
_admin_mutation_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()


def _admin_mutation_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _admin_mutation_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _admin_mutation_locks[loop] = lock
    return lock


class AdminUserNotFoundError(Exception):
    """Raised when the target user does not exist."""


class AdminUserManagementError(Exception):
    """Raised when an admin action violates a business rule (409)."""


class AdminUserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Loading helpers ─────────────────────────────────────────────────────

    async def _load_user_with_roles(self, user_id: str) -> User:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise AdminUserNotFoundError(f"User {user_id} not found")
        return user

    @staticmethod
    def _role_names(user: User) -> List[str]:
        return [
            ur.role.name.value
            for ur in user.roles
            if ur.role is not None
        ]

    async def _active_admin_count_excluding(self, exclude_user_id: str) -> int:
        """Number of active users holding the ADMIN role, excluding the target."""
        stmt = (
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.is_active.is_(True),
                Role.name == RoleName.ADMIN,
                User.id != exclude_user_id,
            )
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return len(rows)

    # ── Reads ───────────────────────────────────────────────────────────────

    async def list_users(self) -> List[User]:
        """Deterministic listing: newest first, ties broken by email."""
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.created_at.desc(), User.email.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_user(self, user_id: str) -> User:
        return await self._load_user_with_roles(user_id)

    # ── Activation / deactivation ───────────────────────────────────────────

    async def set_user_active(self, user_id: str, is_active: bool, actor: User) -> User:
        async with _admin_mutation_lock():
            user = await self._load_user_with_roles(user_id)

            if is_active == user.is_active:
                # Idempotent: nothing to change.
                return user

            if not is_active:
                if user.id == actor.id:
                    raise AdminUserManagementError(
                        "You cannot deactivate your own account."
                    )
                has_admin_role = RoleName.ADMIN.value in self._role_names(user)
                if has_admin_role and await self._active_admin_count_excluding(user.id) == 0:
                    raise AdminUserManagementError(
                        "Cannot deactivate the last active ADMIN user."
                    )

            user.is_active = is_active
            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.db.commit()
            return await self._load_user_with_roles(user.id)

    async def activate_user(self, user_id: str, actor: User) -> User:
        return await self.set_user_active(user_id, True, actor)

    async def deactivate_user(self, user_id: str, actor: User) -> User:
        return await self.set_user_active(user_id, False, actor)

    # ── Role assignment ─────────────────────────────────────────────────────

    async def replace_user_roles(
        self, user_id: str, roles: List[RoleName], actor: User
    ) -> User:
        async with _admin_mutation_lock():
            user = await self._load_user_with_roles(user_id)

            # Defensive: normalize each entry to the fixed enum vocabulary even
            # if the schema layer was bypassed (route validates via pydantic).
            normalized: List[RoleName] = []
            for r in roles:
                try:
                    normalized.append(r if isinstance(r, RoleName) else RoleName(r))
                except (ValueError, KeyError):
                    raise AdminUserManagementError(
                        f"Invalid role '{r}'. Roles are limited to the fixed vocabulary."
                    )

            # Deterministic normalization: canonical fixed order, no duplicates.
            canonical_order = [RoleName.OPERATOR, RoleName.FINANCE_MANAGER, RoleName.ADMIN]
            unique_roles = [r for r in canonical_order if r in set(normalized)]
            if not unique_roles:
                raise AdminUserManagementError(
                    "At least one valid role is required."
                )

            user_has_admin = RoleName.ADMIN.value in self._role_names(user)
            new_has_admin = RoleName.ADMIN in unique_roles
            if user_has_admin and not new_has_admin and user.is_active:
                # This change would strip ADMIN from an active admin — allowed
                # only if at least one other active ADMIN remains.
                if await self._active_admin_count_excluding(user.id) == 0:
                    raise AdminUserManagementError(
                        "Cannot remove ADMIN from the last active ADMIN user."
                    )

            # Resolve target Role rows (must already exist in the vocabulary).
            role_rows = {}
            for role_name in unique_roles:
                stmt = select(Role).where(Role.name == role_name)
                role_row = (await self.db.execute(stmt)).scalar_one_or_none()
                if role_row is None:
                    raise AdminUserManagementError(
                        f"Role '{role_name.value}' is not configured. Seed roles first."
                    )
                role_rows[role_name] = role_row

            # Atomic replacement through the ORM relationship (cascade delete-
            # orphan). We flush the collection clear FIRST so the old
            # assignments are deleted before the new rows are inserted —
            # required because the (user_id, role_id) unique constraint would
            # otherwise collide on the insert of a re-assigned role. Both steps
            # run in the same transaction.
            user.roles.clear()
            await self.db.flush()
            for role_name in unique_roles:
                user.roles.append(
                    UserRole(user_id=user.id, role_id=role_rows[role_name].id)
                )

            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.db.commit()
            return await self._load_user_with_roles(user.id)