import jwt
from datetime import datetime, timedelta, timezone
import uuid
from typing import Dict, Any

from config.settings import get_settings

settings = get_settings()

class JWTError(Exception):
    """Base exception for JWT validation failures."""
    pass

def create_access_token(user_id: str, credential_version: int = 1) -> str:
    """
    Generate a secure, short-lived JWT access token for a user.

    `credential_version` (the user's DB `credential_version`) is embedded as
    the `cver` claim. Authentication rejects any token whose cver does not
    match the user's current DB value, so a password change/reset (which
    increments the version) invalidates every previously issued token at
    once. Only authentication-lifecycle state lives in the token — never
    roles, permissions, passwords, or hashes.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Required minimal claims for identity and security
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expire,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "cver": credential_version
    }
    
    token = jwt.encode(
        payload, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return token

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and strictly validate a JWT access token.
    Raises JWTError on any validation failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM], # Explicitly restrict accepted algorithm
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require": ["sub", "iat", "exp", "iss", "aud", "jti"]
            }
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise JWTError("Token has expired")
    except jwt.InvalidIssuerError:
        raise JWTError("Invalid token issuer")
    except jwt.InvalidAudienceError:
        raise JWTError("Invalid token audience")
    except jwt.InvalidAlgorithmError:
        raise JWTError("Unsupported token algorithm")
    except jwt.MissingRequiredClaimError as e:
        raise JWTError(f"Missing required claim: {str(e)}")
    except jwt.InvalidTokenError as e:
        raise JWTError("Invalid token")
    except Exception as e:
        raise JWTError("Token validation failed")
