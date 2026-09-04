import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean, JSON, event
from database.base import Base

class SecurityEventType(str, enum.Enum):
    # AUTH
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    SESSION_REJECTED = "SESSION_REJECTED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    # ACCOUNT
    ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    # PASSWORD
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    ADMIN_PASSWORD_RESET = "ADMIN_PASSWORD_RESET"
    FORCED_PASSWORD_CHANGE = "FORCED_PASSWORD_CHANGE"
    CREDENTIAL_VERSION_CHANGED = "CREDENTIAL_VERSION_CHANGED"
    # ADMIN/IDENTITY
    USER_CREATED = "USER_CREATED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    # AUTHORIZATION
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    PRIVILEGED_ACTION_DENIED = "PRIVILEGED_ACTION_DENIED"
    # ACTION REQUEST
    ACTION_REQUEST_CREATED = "ACTION_REQUEST_CREATED"
    ACTION_REQUEST_APPROVED = "ACTION_REQUEST_APPROVED"
    ACTION_REQUEST_REJECTED = "ACTION_REQUEST_REJECTED"
    ACTION_REQUEST_CANCELLED = "ACTION_REQUEST_CANCELLED"
    # ACTION EXECUTION
    ACTION_EXECUTION_STARTED = "ACTION_EXECUTION_STARTED"
    ACTION_EXECUTION_SUCCEEDED = "ACTION_EXECUTION_SUCCEEDED"
    ACTION_EXECUTION_FAILED = "ACTION_EXECUTION_FAILED"
    ACTION_EXECUTION_UNKNOWN = "ACTION_EXECUTION_UNKNOWN"
    # PERIOD
    PERIOD_CLOSED = "PERIOD_CLOSED"

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
    is_success = Column(Boolean, nullable=False, default=True, index=True)
    
    # Additional safe metadata (never passwords/hashes/tokens)
    metadata_payload = Column(JSON, nullable=True)
    
    # Immutable timestamp
    created_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), 
        nullable=False, 
        index=True
    )

# Application-level Append-Only Guarantee
@event.listens_for(SecurityEvent, "before_update")
def receive_before_update(mapper, connection, target):
    raise ValueError("SecurityEvent records are append-only. Updates are strictly forbidden.")

@event.listens_for(SecurityEvent, "before_delete")
def receive_before_delete(mapper, connection, target):
    raise ValueError("SecurityEvent records are append-only. Deletions are strictly forbidden.")
