"""Password management service (M8.5).

Encapsulates self-service password change and ADMIN-initiated password
reset with one central security model:

- Argon2id remains the only credential storage (never plaintext).
- The centralized 12-character password policy applies to every path.
- A successful change/reset increments the user's `credential_version`,
  which immediately invalidates every previously issued JWT (the auth
  dependency compares the token's `cver` claim to the DB value).
- An admin reset additionally sets `must_change_password=True`, forcing the
  target to choose a new password before any protected functionality works.
- The generated temporary password is returned exactly once to the admin
  caller; only its Argon2id hash is persisted and it is never logged.
"""

import asyncio
import secrets
import weakref
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.identity import User, UserCredential
from packages.utils.crypto import hash_password, verify_password
from packages.utils.password_policy import validate_password
from services.auth import security_events


class PasswordPolicyError(Exception):
    """New password violates the centralized policy (422)."""


class WrongCurrentPasswordError(Exception):
    """The supplied current password does not match (400)."""


class SamePasswordError(Exception):
    """New password equals the current password (400)."""


class UserNotFoundError(Exception):
    """Target user does not exist (404)."""


class SelfResetNotAllowedError(Exception):
    """Admin attempted to reset their own password (400)."""


class AdminUserServiceError(Exception):
    """Unexpected failure mapping to a safe 500."""


# Serializes the verify-then-write critical section of password mutations so
# concurrent change/reset requests cannot silently overwrite each other's
# credential hash or race the version bump. Cached per running event loop:
# production requests share one loop (full serialization); test runners that
# create a fresh loop per test never reuse a loop-bound lock.
_password_mutation_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()


def _password_mutation_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _password_mutation_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _password_mutation_locks[loop] = lock
    return lock


async def _load_credential(db: AsyncSession, user_id: str) -> UserCredential:
    stmt = select(UserCredential).where(UserCredential.user_id == user_id)
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if cred is None:
        # Every User created through the application has exactly one
        # credential row; a missing row means the database is inconsistent.
        raise AdminUserServiceError("Credential record is missing for user.")
    return cred


async def change_own_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Change the AUTHENTICATED user's password.

    The target is always `user` (derived from the token); request bodies
    never carry a user_id.

    On success:
    - the Argon2id hash is replaced,
    - `must_change_password` is cleared,
    - `credential_version` is incremented → all existing sessions die.
    """
    if not current_password or not new_password:
        raise WrongCurrentPasswordError(
            "Current password and new password are required."
        )

    try:
        validate_password(new_password)
    except ValueError as exc:
        raise PasswordPolicyError(str(exc))

    async with _password_mutation_lock():
        cred = await _load_credential(db, user.id)

        if not verify_password(current_password, cred.password_hash):
            security_events.password_change_failed(user.id, "wrong_current_password")
            raise WrongCurrentPasswordError("Current password is incorrect.")

        # New password must not equal the current one. Verifying against the
        # old hash avoids relying on plaintext equality and stays safe even
        # if the client supplied a differently-encoded variant of the same
        # value.
        if verify_password(new_password, cred.password_hash):
            raise SamePasswordError(
                "New password must be different from the current password."
            )

        new_hash = hash_password(new_password)
        cred.password_hash = new_hash
        cred.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        was_forced = bool(user.must_change_password)
        user.must_change_password = False
        user.credential_version = (user.credential_version or 1) + 1
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()

    security_events.password_changed(user.id)
    if was_forced:
        security_events.forced_password_change_completed(user.id)


def generate_temporary_password() -> str:
    """Cryptographically secure one-time temporary credential.

    `secrets.token_urlsafe(12)` yields 16 URL-safe characters (>= the
    centralized 12-character policy). The value is returned to the caller
    exactly once; only its hash is ever stored.
    """
    return secrets.token_urlsafe(12)


async def admin_reset_password(
    db: AsyncSession,
    actor: User,
    target_user_id: str,
) -> str:
    """ADMIN-initiated password reset for another user (MANAGE_USERS).

    Returns the generated temporary password (single display). The target is
    marked `must_change_password` and its `credential_version` is bumped, so:
    - all of the target's existing sessions die immediately,
    - the temporary credential only grants access to identity/password
      endpoints until a new password is chosen.
    """
    if actor.id == target_user_id:
        raise SelfResetNotAllowedError(
            "Use Change Password for your own account."
        )

    async with _password_mutation_lock():
        stmt = select(User).where(User.id == target_user_id)
        target = (await db.execute(stmt)).scalar_one_or_none()
        if target is None:
            raise UserNotFoundError("User not found.")

        temporary_password = generate_temporary_password()

        cred = await _load_credential(db, target.id)
        cred.password_hash = hash_password(temporary_password)
        cred.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        target.must_change_password = True
        target.credential_version = (target.credential_version or 1) + 1
        target.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()

    security_events.admin_password_reset(actor.id, target.id)
    return temporary_password
