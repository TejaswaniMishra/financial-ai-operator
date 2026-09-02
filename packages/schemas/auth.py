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

