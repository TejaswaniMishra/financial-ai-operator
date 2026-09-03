"""Admin-facing schemas for identity/user management (M8.4).

Dedicated schemas so public auth contracts stay clean. Only safe identity
fields are ever serialized — never password hashes, credentials, JWT data,
token revocations, or internal diagnostics.

Role updates validate against the fixed RoleName vocabulary; the client can
never create arbitrary roles.
"""

from datetime import datetime
from typing import List

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
    created_at: datetime = Field(..., description="When the user was created")


class AdminUserDetail(AdminUserListItem):
    """Full safe identity profile for a single user."""

    updated_at: datetime = Field(..., description="When the user was last updated")


class UserRolesUpdateRequest(BaseModel):
    """Replace a user's role assignments (fixed vocabulary only)."""

    roles: List[RoleName] = Field(
        ...,
        description="Complete set of roles to assign; replaces existing assignments",
    )


class UserStatusUpdateRequest(BaseModel):
    """Explicit, typed request for changing a user's active status."""

    is_active: bool = Field(..., description="Whether the user should be active")