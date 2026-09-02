from database.models.action_request import ActionRequestStatus

class ActionRequestStateMachine:
    
    # Define valid transitions
    # key: current_state, value: set of allowed next_states
    _valid_transitions = {
        ActionRequestStatus.PENDING_APPROVAL: {
            ActionRequestStatus.APPROVED,
            ActionRequestStatus.REJECTED,
            ActionRequestStatus.CANCELLED
        },
        ActionRequestStatus.APPROVED: set(),
        ActionRequestStatus.REJECTED: set(),
        ActionRequestStatus.CANCELLED: set()
    }
    
    @classmethod
    def can_transition(cls, current_state: ActionRequestStatus, next_state: ActionRequestStatus) -> bool:
        """Check if a transition from current_state to next_state is valid."""
        allowed_next = cls._valid_transitions.get(current_state, set())
        return next_state in allowed_next
    
    @classmethod
    def validate_transition(cls, current_state: ActionRequestStatus, next_state: ActionRequestStatus):
        """Raise ValueError if the transition is invalid."""
        if not cls.can_transition(current_state, next_state):
            raise ValueError(
                f"Invalid state transition: Cannot transition from {current_state.value} to {next_state.value}"
            )
