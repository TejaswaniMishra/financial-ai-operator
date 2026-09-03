from typing import List

from pydantic import BaseModel, Field

class SignupRequest(BaseModel):
    email: str = Field(
        ..., 
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="Must be a valid email structure"
    )
    password: str = Field(
        ..., 
        min_length=12, 
        description="Must be at least 12 characters"
    )
    display_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255
    )

    def normalize_email(self) -> str:
        """Deterministically normalize the email address."""
        return self.email.lower().strip()

class LoginRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    def normalize_email(self) -> str:
        """Deterministically normalize the email address."""
        return self.email.lower().strip()

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type, typically 'bearer'")
    expires_in: int = Field(..., description="Token expiration in seconds")

class CurrentUserResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    display_name: str = Field(..., description="User display name")
    is_active: bool = Field(..., description="Whether the user is currently active")
    roles: List[str] = Field(
        default_factory=list,
        description="Authoritative role names resolved from the database",
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="Permission codes resolved from the user's database roles",
    )
    must_change_password: bool = Field(
        default=False,
        description="Backend-controlled flag: an admin password reset is pending and the user must change their password before accessing protected functionality",
    )

class ChangePasswordRequest(BaseModel):
    """Self-service password change. The target is ALWAYS the authenticated
    user — no user_id is accepted or consulted."""
    current_password: str = Field(..., description="The user's current password")
    new_password: str = Field(..., description="The new password (must satisfy the centralized password policy)")

class ChangePasswordResponse(BaseModel):
    message: str = Field(..., description="Success message")

class LogoutResponse(BaseModel):
    message: str = Field(..., description="Success message")
