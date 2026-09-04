import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from database.base import Base


class Notification(Base):
    """User-facing notification derived from real backend events.

    Each row belongs to exactly one recipient. Notifications are produced by
    the services that own the underlying events (action-request lifecycle,
    investigation completion, period close blocking) — never fabricated by
    the client. The payload holds only safe display fields plus an optional
    typed target for navigation; no secrets or internal diagnostics.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Stable machine-readable category, e.g. ACTION_REQUEST_PENDING,
    # ACTION_REQUEST_APPROVED, INVESTIGATION_COMPLETED, PERIOD_BLOCKED.
    type = Column(String(80), nullable=False)

    title = Column(String(255), nullable=False)
    message = Column(String, nullable=False)

    is_read = Column(Boolean, nullable=False, default=False)

    # Optional typed target for navigation (e.g. action_request/<id>).
    target_type = Column(String(40), nullable=True)
    target_id = Column(String(36), nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
    )

    user = relationship("User")
