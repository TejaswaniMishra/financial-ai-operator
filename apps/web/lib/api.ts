// ─── Auth Types ────────────────────────────────────────────────────────────

/** POST /api/auth/login */
export interface LoginRequest {
  email: string;
  password: string;
}

/** POST /api/auth/signup */
export interface SignupRequest {
  display_name: string;
  email: string;
  password: string;
}

/**
 * Authenticated user returned by GET /api/v1/auth/me (via BFF).
 * Contains ONLY identity fields — no roles, no auth internals.
 */
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
}

// ─── API Base resolution ────────────────────────────────────────────────────
//
// IMPORTANT: API_BASE strategy:
//   - Direct backend URL is used ONLY for unauthenticated/server-safe calls
//     (e.g. /health) that don't need cookie injection.
//   - All authenticated business API calls go through the Next.js BFF proxy at
//     a relative path (/api/v1/...) so the server-side route handler can read
//     the HttpOnly cookie and inject the Authorization header.
//   - When called from the browser, relative URLs resolve to the Next.js origin.
//   - When called from server components, we must use an absolute URL.

const DIRECT_API_BASE =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

/**
 * Returns the base URL for authenticated business API calls.
 * Browser: relative path (Next.js BFF proxy handles auth injection).
 * Server:  absolute URL to the internal backend.
 */
function bffBase(): string {
  if (typeof window !== "undefined") {
    // Browser — relative URL routes through the Next.js catch-all proxy
    return "";
  }
  // Server-side — use the direct backend URL
  return DIRECT_API_BASE;
}

// ─── 401 event (browser-only) ──────────────────────────────────────────────
// Dispatched when an authenticated API call returns 401 so the AuthProvider
// can react and clear session state without direct coupling.
export const UNAUTHORIZED_EVENT = "fao:unauthorized";

function dispatchUnauthorized(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }
}

// ─── Core authenticated fetch ───────────────────────────────────────────────
/**
 * fetchAuthenticated wraps fetch for authenticated business API calls.
 * - Uses relative BFF path from the browser
 * - Dispatches UNAUTHORIZED_EVENT on 401 (except on auth routes)
 */
async function fetchAuthenticated(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const res = await fetch(url, { cache: "no-store", ...options });

  if (res.status === 401) {
    // Avoid dispatching if the request itself was to an auth endpoint
    const isAuthEndpoint = url.includes("/api/auth/");
    if (!isAuthEndpoint) {
      dispatchUnauthorized();
    }
  }

  return res;
}

// ─── Auth API functions (call Next.js BFF, never raw backend) ─────────────

export async function login(payload: LoginRequest): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string" ? data.detail : "Invalid email or password"
    );
  }
}

export async function signup(payload: SignupRequest): Promise<void> {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string" ? data.detail : "Registration failed"
    );
  }
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const res = await fetch("/api/auth/me", { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Not authenticated");
  }
  return res.json();
}

export async function logout(): Promise<void> {
  // Call BFF — backend token revocation happens server-side
  await fetch("/api/auth/logout", { method: "POST" });
  // Always continue: cookie will be cleared by the BFF route
}

// ─── Health (no auth needed, direct backend call is safe) ──────────────────

export interface DatabaseStatus {
  connected: boolean;
  engine: string;
  latency_ms: number | null;
  error: string | null;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  timestamp: string;
  version: string;
  environment: string;
  database: DatabaseStatus;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${DIRECT_API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch health status: ${res.statusText}`);
  }
  return res.json();
}

// ─── System Info (via BFF proxy for auth) ──────────────────────────────────

export interface SystemInfoResponse {
  name: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  active_services: Record<string, "healthy" | "degraded" | "unhealthy">;
  architecture_phase: string;
}

export async function fetchSystemInfo(): Promise<SystemInfoResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/system/info`);
  if (!res.ok) throw new Error(`Failed to fetch system info: ${res.statusText}`);
  return res.json();
}

// ─── Metrics ───────────────────────────────────────────────────────────────

export interface MetricsOverviewResponse {
  merchants: number;
  payments: number;
  settlements: number;
  bank_transactions: number;
  total_volume: number;
}

export async function fetchMetricsOverview(): Promise<MetricsOverviewResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/metrics/overview`);
  if (!res.ok) throw new Error(`Failed to fetch metrics overview: ${res.statusText}`);
  return res.json();
}

export interface ReconciliationRun {
  run_id: string;
  status: string;
  total_records_processed: number;
  matches_created: number;
  discrepancies_found: number;
}

export async function fetchReconciliationRuns(): Promise<ReconciliationRun[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/reconciliation/runs`);
  if (!res.ok) throw new Error(`Failed to fetch reconciliation runs: ${res.statusText}`);
  return res.json();
}

export interface DiscrepancyResponse {
  id: string;
  rule_code: string;
  discrepancy_type: string;
  severity: string;
  source_entity_type: string;
  source_entity_id: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  difference_amount: number | null;
  currency: string | null;
  created_at: string;
}

export async function fetchReconciliationDiscrepancies(): Promise<DiscrepancyResponse[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/reconciliation/discrepancies`);
  if (!res.ok) throw new Error(`Failed to fetch reconciliation discrepancies: ${res.statusText}`);
  return res.json();
}

export enum RootCauseEnum {
  UNEXPECTED_FEE = "UNEXPECTED_FEE",
  TIMING_DELAY = "TIMING_DELAY",
  DATA_INGESTION_ERROR = "DATA_INGESTION_ERROR",
  CURRENCY_FX_RATE_MISMATCH = "CURRENCY_FX_RATE_MISMATCH",
  SYSTEMIC_PROVIDER_ISSUE = "SYSTEMIC_PROVIDER_ISSUE",
  MISSING_TRANSACTION = "MISSING_TRANSACTION",
  DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION",
  PROVIDER_CONFIGURATION_ERROR = "PROVIDER_CONFIGURATION_ERROR",
  RECONCILIATION_RULE_ERROR = "RECONCILIATION_RULE_ERROR",
  UNKNOWN = "UNKNOWN",
}

export interface EvidenceCitation {
  entity_id: string;
  entity_type: string;
  field: string;
  value: unknown;
  currency: string | null;
}

export interface InvestigationClaim {
  claim: string;
  evidence: EvidenceCitation[];
}

export interface InvestigationResult {
  summary: string;
  root_cause_category: RootCauseEnum;
  ai_confidence: number;
  claims: InvestigationClaim[];
  recommendations: string[];
}

export interface InvestigationRunResponse {
  investigation_id: string;
  attempt_id: string;
  status: string;
  is_valid: boolean;
  result: unknown | null;
  errors: unknown | null;
}

export interface InvestigationResponse {
  id: string;
  discrepancy_id: string;
  status: string;
  active_attempt_id: string | null;
  created_at: string | null;
}

export interface InvestigationListItem {
  id: string;
  discrepancy_id: string;
  status: string;
  active_attempt_id: string | null;
  created_at: string | null;
}

export interface InvestigationAttempt {
  id: string;
  prompt_version: string | null;
  model_used: string | null;
  is_valid: boolean;
  created_at: string | null;
}

export interface InvestigationApprovalResponse {
  investigation_id: string;
  action: string;
  message: string;
}

export async function runInvestigation(discrepancyId: string): Promise<InvestigationRunResponse> {
  const res = await fetchAuthenticated(
    `${bffBase()}/api/v1/investigations/discrepancy/${discrepancyId}/run`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Failed to run investigation: ${res.statusText}`);
  return res.json();
}

export async function fetchInvestigations(): Promise<InvestigationListItem[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/investigations`);
  if (!res.ok) throw new Error(`Failed to fetch investigations: ${res.statusText}`);
  return res.json();
}

export async function fetchInvestigation(investigationId: string): Promise<InvestigationResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/investigations/${investigationId}`);
  if (!res.ok) throw new Error(`Failed to fetch investigation: ${res.statusText}`);
  return res.json();
}

export async function fetchInvestigationAttempts(investigationId: string): Promise<InvestigationAttempt[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/investigations/${investigationId}/attempts`);
  if (!res.ok) throw new Error(`Failed to fetch investigation attempts: ${res.statusText}`);
  return res.json();
}

export async function approveInvestigation(investigationId: string): Promise<InvestigationApprovalResponse> {
  const res = await fetchAuthenticated(
    `${bffBase()}/api/v1/investigations/${investigationId}/approve`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Failed to approve investigation: ${res.statusText}`);
  return res.json();
}

export interface InvestigationAttemptResultResponse {
  investigation_id: string;
  attempt_id: string;
  status: string;
  is_valid: boolean;
  result: InvestigationResult | null;
  errors: unknown | null;
}

export async function fetchInvestigationAttemptResult(
  investigationId: string,
  attemptId: string
): Promise<InvestigationAttemptResultResponse> {
  const res = await fetchAuthenticated(
    `${bffBase()}/api/v1/investigations/${investigationId}/attempts/${attemptId}`
  );
  if (!res.ok) throw new Error(`Failed to fetch investigation attempt result: ${res.statusText}`);
  return res.json();
}

export type ActionRequestStatus = "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "CANCELLED";

export interface ActionRequestResponse {
  id: string;
  investigation_id: string;
  discrepancy_id: string | null;
  policy_evaluation_id: string;
  action: string;
  status: ActionRequestStatus;
  requested_source: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchActionRequests(): Promise<ActionRequestResponse[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests`);
  if (!res.ok) throw new Error(`Failed to fetch action requests: ${res.statusText}`);
  return res.json();
}

export async function fetchActionRequest(id: string): Promise<ActionRequestResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch action request: ${res.statusText}`);
  return res.json();
}

export async function approveActionRequest(id: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to approve action request: ${res.statusText}`);
  }
  return res.json();
}

export async function rejectActionRequest(id: string, reason: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, actor }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to reject action request: ${res.statusText}`);
  }
  return res.json();
}

export async function cancelActionRequest(id: string, reason: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, actor }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to cancel action request: ${res.statusText}`);
  }
  return res.json();
}

export type ActionExecutionStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "UNKNOWN";

export interface ActionExecutionAttemptResponse {
  id: string;
  attempt_number: number;
  status: ActionExecutionStatus;
  result: any;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ActionExecutionResponse {
  id: string;
  action_request_id: string;
  idempotency_key: string;
  execution_type: string;
  adapter: string;
  status: ActionExecutionStatus;
  result: any;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  attempts: ActionExecutionAttemptResponse[];
}

export async function fetchActionExecutions(id: string): Promise<ActionExecutionResponse[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}/executions`);
  if (!res.ok) throw new Error(`Failed to fetch action executions: ${res.statusText}`);
  return res.json();
}

export async function executeActionRequest(id: string, idempotency_key?: string): Promise<ActionExecutionResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/action-requests/${id}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idempotency_key }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to execute action request: ${res.statusText}`);
  }
  return res.json();
}
