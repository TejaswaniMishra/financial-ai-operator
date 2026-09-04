import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship

from database.base import Base


class MfaRecoveryCode(Base):
    """One-time MFA recovery code, stored ONLY as a SHA-256 hash.

    The plaintext is shown to the user exactly once at generation time and
    is never persisted, logged, or returned again. Each code is single-use.
    """

    __tablename__ = "mfa_recovery_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash = Column(String(64), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="mfa_recovery_codes")

    __table_args__ = (
        Index("ix_mfa_recovery_user_hash", "user_id", "code_hash", unique=True),
    )
