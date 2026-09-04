# M10: Unified Exception Management & Resolution Workspace

## Architecture

This workspace unifies the disjointed data models created during previous milestones (Discrepancy, Investigation, Policy Evaluation, Action Request, Action Execution) into a single read-oriented `Exception` entity. This allows operators to manage the full lifecycle of a discrepancy from a single view without jumping between multiple tools.

We intentionally did **not** duplicate the underlying state. The `Exception` read model is generated dynamically on the backend via SQL `LEFT JOIN` and a `CASE` statement, maintaining the authoritative facts in the existing systems (e.g., `Discrepancy`, `Investigation`).

### Exception State Model

The overall operational state of an exception is deterministically derived from its lifecycle relationships:

- **EXECUTING**: When there is an `ActionExecution` in `PENDING` or `RUNNING`.
- **RESOLVED**: When there is an `ActionExecution` that `SUCCEEDED`, or when a policy evaluation is `DENIED` (terminal state).
- **FAILED**: When there is an `ActionExecution` that `FAILED`, or an `Investigation` that `FAILED` or is `UNAVAILABLE`.
- **UNKNOWN**: When there is an `ActionExecution` that is `UNKNOWN`.
- **APPROVED**: When an `ActionRequest` is `APPROVED` but not yet executing.
- **AWAITING_APPROVAL**: When an `ActionRequest` is `PENDING_APPROVAL`, or when a policy evaluation is `APPROVAL_REQUIRED`.
- **INVESTIGATING**: When an `Investigation` is `PENDING`.
- **OPEN**: The default state if none of the above are met (e.g., discrepancy found but not investigated, or an action request was cancelled).

## API Endpoints

### `GET /api/v1/exceptions`
Returns a paginated list of exceptions.

**Query Parameters:**
- `limit` (default: 50)
- `offset` (default: 0)
- `type` (optional): Filter by discrepancy type (e.g., `FEE_MISMATCH`)
- `state` (optional): Filter by derived `overall_state`
- `currency` (optional)
- `transaction_type` (optional)

*Note: Pagination and state filtering are performed efficiently at the database level.*

### `GET /api/v1/exceptions/{id}`
Returns the detailed view for a single exception, eagerly loading all relevant relationships including the AI investigation results, policy decisions, and action execution state. Sensitive internal AI reasoning (like context snapshots) is intentionally omitted from the response schema.

## Frontend Routes

- `/exceptions`: The main unified workspace dashboard. Includes filters and pagination over the overall state.
- `/exceptions/[id]`: The detail console for a specific exception. It unifies financial context, the AI investigation result, the policy decision, and execution status into a single view. Users can trigger investigations, approve/reject action requests, and execute actions directly from this page if permitted.

## RBAC Integration

Exception read access is gated behind the existing `VIEW_DISCREPANCIES` permission.
All mutative actions (triggering investigations, approving requests, executing actions) re-use the existing backend endpoints and therefore enforce their respective existing permissions (`RUN_INVESTIGATION`, `APPROVE_ACTION_REQUEST`, `EXECUTE_ACTION`). No new permissions were introduced unnecessarily. 

## Known Limitations
- The resolution model implies that once an execution succeeds, the exception is `RESOLVED`. It does not retroactively rewrite the original source financial facts (e.g., the base payment amounts), which preserves auditability. 
- Timeline events are synthesized implicitly through the existence of the related models; a dedicated event-sourced timeline is not yet explicitly tracked, though all timestamps are preserved on the individual records.
