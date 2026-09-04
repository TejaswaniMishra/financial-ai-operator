"""Admin-facing schemas for identity/user management (M8.4).

Dedicated schemas so public auth contracts stay clean. Only safe identity
fields are ever serialized — never password hashes, credentials, JWT data,
token revocations, or internal diagnostics.

Role updates validate against the fixed RoleName vocabulary; the client can
never create arbitrary roles.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from database.models.identity import RoleName


class AdminUserListItem(BaseModel):
    """Safe identity profile for a user in an admin listing."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    display_name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether the user is currently active")
    roles: List[str] = Field(
        default_factory=list,
        description="Role names currently assigned to the user",
    )
    # Optional because legacy/seed rows may predate timestamp columns; a single
    # malformed row must never 500 the whole admin listing.
    created_at: Optional[datetime] = Field(
        default=None, description="When the user was created"
    )


class AdminUserDetail(AdminUserListItem):
    """Full safe identity profile for a single user."""

    updated_at: Optional[datetime] = Field(
        default=None, description="When the user was last updated"
    )


class UserRolesUpdateRequest(BaseModel):
    """Replace a user's role assignments (fixed vocabulary only)."""

    roles: List[RoleName] = Field(
        ...,
        description="Complete set of roles to assign; replaces existing assignments",
    )


class UserStatusUpdateRequest(BaseModel):
    """Explicit, typed request for changing a user's active status."""

    is_active: bool = Field(..., description="Whether the user should be active")


class AdminPasswordResetResponse(BaseModel):
    """Result of an admin-initiated password reset.

    `temporary_password` is the ONLY time the generated credential is ever
    returned. It is a server-generated, one-time handoff value: the database
    stores only its Argon2id hash, and the target user must change it before
    any protected functionality becomes available (must_change_password).
    """

    message: str = Field(..., description="Human-readable success message")
    temporary_password: str = Field(
        ...,
        description="One-time temporary password. Show it to the administrator once and instruct secure handoff.",
    )
    must_change_password: bool = Field(
        default=True,
        description="The target is now required to change this password before accessing protected functionality",
    )