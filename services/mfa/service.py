"""Server-authoritative TOTP MFA helpers (enrollment, verification, recovery).

Design invariants:
- TOTP secrets are stored Fernet-encrypted at rest using a key derived from
  the app secret — never in plaintext, never in JWTs, never in logs.
- Recovery codes are one-time, generated with `secrets`, stored ONLY as
  SHA-256 hashes, and shown to the user exactly once.
- No MFA material ever reaches the client except the single enrollment
  secret/otpauth payload and the freshly generated recovery-code list.
"""
import base64
import hashlib
import secrets
from typing import Optional

from cryptography.fernet import Fernet
import pyotp

from config.settings import get_settings

RECOVERY_CODE_COUNT = 10
TOTP_ISSUER = "Financial AI Operator"
TOTP_VALID_WINDOW = 1  # ±1 step of clock skew


def _fernet() -> Fernet:
    """Deterministic Fernet key derived from the app secret (32 raw bytes)."""
    settings = get_settings()
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str) -> Optional[str]:
    """Returns None if the stored value cannot be decrypted (defensive)."""
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception:  # noqa: BLE001 - defensive, never crash auth on bad storage
        return None


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code allowing ±1 time-step of clock skew."""
    if not code or not secret:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=TOTP_VALID_WINDOW)


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Cryptographically random, human-typeable one-time codes."""
    codes: list[str] = []
    for _ in range(count):
        group_a = secrets.token_hex(4).upper()
        group_b = secrets.token_hex(4).upper()
        codes.append(f"{group_a}-{group_b}")
    return codes


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
