from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginResultResponse(BaseModel):
    """Result of POST /auth/login.

    Either a normal `access_token` session is returned, or — when the user
    has MFA enabled — `mfa_required` is true with a short-lived `mfa_token`
    that ONLY the MFA verification endpoint accepts.
    """

    access_token: Optional[str] = Field(default=None)
    token_type: str = Field(default="bearer")
    expires_in: int = Field(default=0)
    mfa_required: bool = Field(default=False)
    mfa_token: Optional[str] = Field(
        default=None,
        description="Short-lived, single-purpose token for the MFA challenge",
    )


class MfaVerifyRequest(BaseModel):
    """Second factor: mfa_token from login + a TOTP or recovery code."""

    model_config = ConfigDict(extra="forbid")

    mfa_token: str = Field(..., description="Challenge token issued by login")
    code: str = Field(..., min_length=1, max_length=32, description="6-digit TOTP or recovery code")


class MfaSetupResponse(BaseModel):
    """One-time enrollment payload. `secret` is returned ONLY here."""

    secret: str = Field(..., description="Base32 TOTP secret (shown once for authenticator entry)")
    otpauth_url: str = Field(..., description="otpauth:// URI for authenticator apps")


class MfaVerifySetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=32)


class RecoveryCodesResponse(BaseModel):
    codes: List[str] = Field(
        default_factory=list,
        description="Plaintext one-time recovery codes. Returned exactly once.",
    )


class MfaDisableRequest(BaseModel):
    """Disabling MFA requires proof of the current TOTP secret."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=32)


class MfaRegenerateRequest(BaseModel):
    """Regenerating recovery codes requires the account password."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1)
