# M11 — Financial Close & Period Management

## Overview

The Financial Close & Period Management module (M11) introduces deterministic control workflows to bound financial activity into immutable periods. This ensures that operational states—such as reconciliations, exceptions, and action requests—are cleanly finalized before a period is closed.

In adherence to core architectural principles, **Financial Close is a strictly deterministic control workflow**. The system determines close readiness exclusively from authoritative database facts and existing deterministic operational state. LLMs are explicitly prohibited from determining readiness, overriding blockers, or executing a close.

## Core Principles

1. **Deterministic Readiness**: Close readiness is evaluated strictly by querying database state for pending operations (e.g., unresolved exceptions, pending investigations).
2. **Immutability of Source Facts**: The close process does not mutate monetary execution data (e.g., Payments, Settlements). It acts purely as a control state transition and emits audit events.
3. **Strict RBAC Enforcement**:
   - `OPERATOR`: Can view periods.
   - `FINANCE_MANAGER`: Can view, create, evaluate readiness, approve, and close periods.
   - `ADMIN`: Inherits all capabilities.
4. **Concurrency Safety**: State transitions (e.g., `OPEN` -> `CLOSING` -> `CLOSED`) use database-level locks (`SELECT ... FOR UPDATE`) to prevent race conditions during concurrent close attempts.
5. **No LLM Involvement**: LLMs cannot override blockers, approve closures, or evaluate readiness. Human authorization is always required for the final close transition.

## Architecture

### Data Models

- **`FinancialPeriod`**: Defines the temporal boundary (start and end dates) and status (`OPEN`, `CLOSING`, `CLOSED`).
- **`PeriodCloseEvaluation`**: An audit trail of readiness evaluations, capturing the deterministic snapshot of blockers at the time of evaluation.

### Service Layer (`services/period.py`)

The service layer implements the core logic for the close lifecycle:

1. **`evaluate_period_close(period_id)`**:
   Determines if a period is ready to close by executing targeted queries against the following operational constraints:
   - **Unreconciled Transactions**: Queries `Payment` and `Settlement` records within the period that are not `RECONCILED`.
   - **Unresolved Exceptions**: Queries `Discrepancy` records associated with the period's transactions that are not `RESOLVED`.
   - **Pending Investigations**: Queries `Investigation` records linked to the period's discrepancies that are in `PENDING` or `IN_PROGRESS` state.
   - **Pending Action Requests**: Queries `ActionRequest` records linked to the period's investigations that are in `PENDING_APPROVAL` state.
   - **Running Action Executions**: Queries `ActionExecution` records linked to the period's action requests that are in `PENDING` or `RUNNING` state.
   
   If any of these queries return results, the period is marked as `BLOCKED`. If all are clear, the period is `READY`.

2. **`close_period(period_id)`**:
   - Acquires a row lock (`with_for_update()`) on the `FinancialPeriod`.
   - Re-runs `evaluate_period_close` to ensure the state hasn't changed since the user checked readiness.
   - If `READY`, transitions the status to `CLOSED` and emits a `PERIOD_CLOSED` `SecurityEvent`.
   - If `BLOCKED`, raises an exception detailing the blocking conditions.

### API Routes (`apps/api/routes/periods.py`)

Provides the HTTP interfaces for interacting with periods, secured by the standard RBAC dependency (`require_permission`):

- `GET /api/v1/periods`: List periods (`VIEW_PERIODS`).
- `POST /api/v1/periods`: Create a new period (`CREATE_PERIOD`).
- `GET /api/v1/periods/{id}`: Retrieve period details and metrics (`VIEW_PERIODS`).
- `POST /api/v1/periods/{id}/evaluate`: Evaluate close readiness (`EVALUATE_PERIOD_CLOSE`).
- `POST /api/v1/periods/{id}/close`: Execute the period close (`CLOSE_PERIOD` & `APPROVE_PERIOD_CLOSE`).

### Frontend

The Next.js frontend provides a dedicated workspace for managing periods:

- **List View (`/periods`)**: Displays all periods and their current status.
- **Detail View (`/periods/[id]`)**: Shows comprehensive metrics for the period and an interactive "Close Readiness Controls" panel that visualizes blocking conditions.
- **Creation Flow (`/periods/new`)**: Interface for defining new period boundaries.

## Testing

The implementation is validated by a rigorous integration test suite (`tests/integration/test_periods_api.py`), covering:

- **RBAC Enforcement**: Ensures only authorized roles can perform specific actions.
- **Deterministic Readiness**: Verifies that specific operational states correctly block the close process.
- **Concurrency**: Simulates simultaneous close requests to ensure only one succeeds and data integrity is maintained.
- **Immutability**: Confirms that financial source facts are unaffected by the close process.

## Extension Points

Future enhancements (e.g., M12) may integrate external reporting or ledger synchronization triggered by the `PERIOD_CLOSED` security event. The deterministic evaluation logic can also be expanded to include new control requirements as the system evolves.
