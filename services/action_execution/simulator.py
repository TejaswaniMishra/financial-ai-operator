import asyncio
from services.action_execution.adapter import ActionExecutionAdapter, ExecutionResult
from database.models.action_execution import ActionExecutionStatus
from database.models.action_request import ActionRequest

class SimulatedExecutionAdapter(ActionExecutionAdapter):
    @property
    def name(self) -> str:
        return "simulator"
        
    async def execute(self, action_request: ActionRequest, idempotency_key: str) -> ExecutionResult:
        """
        Simulate an execution safely.
        Special testing keys:
        - idempotency_key containing 'simulate_fail' -> FAILED
        - idempotency_key containing 'simulate_unknown' -> UNKNOWN
        """
        
        # Simulate slight network latency
        await asyncio.sleep(0.1)
        
        if "simulate_fail" in idempotency_key:
            return ExecutionResult(
                status=ActionExecutionStatus.FAILED,
                error_code="SIMULATED_FAILURE",
                error_message="This failure was intentionally simulated via idempotency_key."
            )
            
        if "simulate_unknown" in idempotency_key:
            return ExecutionResult(
                status=ActionExecutionStatus.UNKNOWN,
                error_code="SIMULATED_TIMEOUT",
                error_message="This unknown state was intentionally simulated via idempotency_key."
            )
            
        # Default success
        return ExecutionResult(
            status=ActionExecutionStatus.SUCCEEDED,
            result_data={
                "simulation": True,
                "provider": self.name,
                "provider_execution_id": f"sim_{idempotency_key[:8]}",
                "outcome": "SUCCEEDED",
                "message": "Action executed successfully in simulation mode."
            }
        )
