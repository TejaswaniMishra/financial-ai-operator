from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from database.models.action_execution import ActionExecutionStatus
from database.models.action_request import ActionRequest

@dataclass
class ExecutionResult:
    status: ActionExecutionStatus
    result_data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

class ActionExecutionAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the adapter (e.g., 'simulator', 'stripe')"""
        pass
        
    @abstractmethod
    async def execute(self, action_request: ActionRequest, idempotency_key: str) -> ExecutionResult:
        """
        Execute the action deterministically.
        Must return an ExecutionResult.
        Should handle its own network timeouts and map them to UNKNOWN status if appropriate.
        """
        pass
