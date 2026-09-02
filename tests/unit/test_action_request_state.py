import pytest

from database.models.action_request import ActionRequestStatus
from services.action_request.state_machine import ActionRequestStateMachine

def test_valid_transitions():
    # PENDING_APPROVAL -> APPROVED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.PENDING_APPROVAL, ActionRequestStatus.APPROVED
    ) is True
    
    # PENDING_APPROVAL -> REJECTED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.PENDING_APPROVAL, ActionRequestStatus.REJECTED
    ) is True
    
    # PENDING_APPROVAL -> CANCELLED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.PENDING_APPROVAL, ActionRequestStatus.CANCELLED
    ) is True

def test_invalid_transitions():
    # APPROVED -> REJECTED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.APPROVED, ActionRequestStatus.REJECTED
    ) is False
    
    # REJECTED -> APPROVED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.REJECTED, ActionRequestStatus.APPROVED
    ) is False
    
    # CANCELLED -> APPROVED
    assert ActionRequestStateMachine.can_transition(
        ActionRequestStatus.CANCELLED, ActionRequestStatus.APPROVED
    ) is False

def test_validate_transition_raises():
    with pytest.raises(ValueError, match="Invalid state transition"):
        ActionRequestStateMachine.validate_transition(
            ActionRequestStatus.APPROVED, ActionRequestStatus.REJECTED
        )
