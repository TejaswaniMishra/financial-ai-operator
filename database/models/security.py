import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean, JSON
from database.base import Base

class SecurityEvent(Base):
    """
    Production-grade security audit log.
    Captures critical authentication and account lifecycle events deterministically.
    """
    __tablename__ = "security_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # E.g. LOGIN_SUCCESS, LOGIN_FAILURE, PASSWORD_CHANGED, ADMIN_PASSWORD_RESET, ROLE_CHANGED, etc.
    event_type = Column(String(50), nullable=False, index=True)
    
    # Nullable because we preserve the event even if the user is deleted
    user_id = Column(String(36), nullable=True, index=True)
    
    # Nullable, identifies the admin who performed the action (for admin events)
    actor_id = Column(String(36), nullable=True, index=True)
    
    # Network context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Success/Failure indicator
    is_success = Column(Boolean, nullable=False, default=True)
    
    # Additional safe metadata (never passwords/hashes/tokens)
    metadata_payload = Column(JSON, nullable=True)
    
    # Immutable timestamp
    created_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), 
        nullable=False, 
        index=True
    )
