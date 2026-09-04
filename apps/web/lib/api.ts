import { SIGNUP_ERROR_MESSAGES, signupErrorMessage } from "@/lib/auth-errors";

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
 * Identity fields plus the authoritative, DB-resolved roles and permission
 * codes. Contains no credentials, password hashes, or JWT internals.
 */
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  roles: string[];
  permissions: string[];
  /** Backend-controlled: an admin password reset is pending and the user
   * must change their password before protected functionality is allowed. */
  must_change_password: boolean;
}

// ─── Password management (M8.5) ────────────────────────────────────────────

/** POST /api/v1/auth/change-password (self-service; target is always the
 * authenticated user — no user_id is accepted). */
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface ChangePasswordResult {
  message: string;
}

async function authErrorMessage(res: Response, fallback: string): Promise<string> {
  const data = await res.json().catch(() => null);
  if (typeof data?.detail === "string" && data.detail) {
    return data.detail;
  }
  return fallback;
}

/**
 * Changes the authenticated user's password through the BFF. On success the
 * backend bumps the credential version, so the current session is invalid —
 * the caller must obtain a fresh session via the login flow.
 */
export async function changePassword(payload: ChangePasswordRequest): Promise<ChangePasswordResult> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(
      await authErrorMessage(res, "Password change failed. Please try again.")
    );
  }
  return res.json();
}

/**
 * ADMIN-only (MANAGE_USERS): generate a one-time temporary password for a
 * user. The temporary credential is returned exactly once and shown only to
 * the administrator; the target must change it before accessing the platform.
 */
export interface AdminPasswordResetResult {
  message: string;
  temporary_password: string;
  must_change_password: boolean;
}

export async function adminResetPassword(id: string): Promise<AdminPasswordResetResult> {
  const res = await fetchAuthenticated(
    `${bffBase()}/api/v1/admin/users/${id}/password-reset`,
    { method: "POST" }
  );
  if (!res.ok) {
    throw new Error(
      await authErrorMessage(res, "Password reset failed. Please try again.")
    );
  }
  return res.json();
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
  let res: Response;
  try {
    res = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // The browser could not reach the Next.js BFF at all.
    throw new Error(SIGNUP_ERROR_MESSAGES.network);
  }
  if (!res.ok) {
    // The BFF only ever returns our own safe copy in `detail`; map by status
    // as a fallback for non-JSON error responses.
    const data = await res.json().catch(() => null);
    if (typeof data?.detail === "string") {
      throw new Error(data.detail);
    }
    throw new Error(signupErrorMessage(res.status));
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

// ─── Admin — User Management (M8.4) ────────────────────────────────────────
// All calls go through the BFF catch-all proxy (/api/v1/admin/...) so the
// HttpOnly session cookie is injected and the backend enforces
// MANAGE_USERS / MANAGE_ROLES. Safe identity fields only.

export interface AdminUser {
  id: string
  email: string
  display_name: string
  is_active: boolean
  roles: string[]
  created_at: string
}

export interface SecurityEvent {
  id: string
  event_type: string
  user_id: string | null
  actor_id: string | null
  ip_address: string | null
  user_agent: string | null
  is_success: boolean
  metadata_payload: any | null
  created_at: string
}

export interface AdminUserDetail extends AdminUser {
  updated_at: string;
}

async function adminErrorMessage(res: Response): Promise<string> {
  const data = await res.json().catch(() => null);
  if (typeof data?.detail === "string") {
    return data.detail;
  }
  return `Request failed (${res.status})`;
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/admin/users`);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function fetchAdminUser(id: string): Promise<AdminUserDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/admin/users/${id}`);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function activateAdminUser(id: string): Promise<AdminUserDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/admin/users/${id}/activate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function deactivateAdminUser(id: string): Promise<AdminUserDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/admin/users/${id}/deactivate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export interface SecurityEventPaginatedResponse {
  items: SecurityEvent[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchSecurityEvents(
  eventType?: string,
  limit: number = 100,
  offset: number = 0
): Promise<SecurityEventPaginatedResponse> {
  const url = buildApiUrl("/api/v1/admin/security-events", {
    event_type: eventType,
    limit,
    offset,
  });

  const res = await fetchAuthenticated(url);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function updateAdminUserRoles(id: string, roles: string[]): Promise<AdminUserDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/admin/users/${id}/roles`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roles }),
  });
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

// ─── Transaction workspace (M9) ────────────────────────────────────────────

export type TransactionRecordType =
  | "PAYMENT"
  | "REFUND"
  | "FEE"
  | "SETTLEMENT"
  | "BANK_TRANSACTION";

export interface TransactionRecord {
  id: string;
  record_type: TransactionRecordType;
  external_id: string | null;
  merchant_id: string;
  merchant_name: string;
  provider: string | null;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
  reconciled: boolean;
  has_discrepancy: boolean;
}

export interface TransactionSummary {
  PAYMENT: number;
  REFUND: number;
  FEE: number;
  SETTLEMENT: number;
  BANK_TRANSACTION: number;
  total: number;
}

export interface TransactionListResponse {
  items: TransactionRecord[];
  total: number;
  limit: number;
  offset: number;
  summary: TransactionSummary;
}

export interface TransactionListParams {
  record_type?: TransactionRecordType;
  status?: string;
  currency?: string;
  merchant_id?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: number;
  max_amount?: number;
  reconciled?: boolean;
  has_discrepancy?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ReconciliationContext {
  relationship_id: string;
  relationship_type: string;
  relationship_status: string;
  financial_status: string;
  run_id: string;
  run_status: string;
  source_entity_type: string;
  source_entity_id: string;
  target_entity_type: string;
  target_entity_id: string;
}

export interface DiscrepancyContext {
  id: string;
  rule_code: string;
  discrepancy_type: string;
  severity: string;
  expected_amount: string | null;
  actual_amount: string | null;
  difference_amount: string | null;
  currency: string | null;
  run_id: string;
}

export interface InvestigationContext {
  id: string;
  discrepancy_id: string;
  status: string;
  created_at: string | null;
}

export interface ActionRequestContext {
  id: string;
  investigation_id: string;
  discrepancy_id: string | null;
  action: string;
  status: string;
  created_at: string | null;
}

export interface ActionExecutionContext {
  id: string;
  action_request_id: string;
  status: string;
  execution_type: string;
  adapter: string;
  requested_at: string | null;
  error_code: string | null;
}

export interface RelatedRecord {
  id: string;
  record_type: TransactionRecordType;
  amount: string | null;
  currency: string | null;
  status: string | null;
  created_at: string | null;
}

export interface TransactionDetail {
  id: string;
  record_type: TransactionRecordType;
  external_id: string | null;
  merchant: { id: string; name: string };
  provider: string | null;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string | null;
  order: { id: string; external_id: string | null; status: string; amount: string; currency: string } | null;
  customer: { id: string; display_name: string } | null;
  related: RelatedRecord[];
  reconciliation: ReconciliationContext[];
  discrepancies: DiscrepancyContext[];
  investigation: InvestigationContext | null;
  action_requests: ActionRequestContext[];
  executions: ActionExecutionContext[];
}

export interface LineageNode {
  kind: string;
  role: "SOURCE" | "DERIVED";
  id: string;
  label: string;
  status: string | null;
  amount: string | null;
  currency: string | null;
  timestamp: string | null;
  detail: Record<string, unknown>;
}

export interface TransactionLineageResponse {
  record_type: TransactionRecordType;
  record_id: string;
  nodes: LineageNode[];
}

/**
 * Build a BFF URL without `new URL`: relative browser paths are not accepted
 * by every engine's `URL` constructor, and the BFF proxy only needs the
 * path + query string.
 */
function buildApiUrl(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return `${bffBase()}${path}${qs ? `?${qs}` : ""}`;
}

export async function fetchTransactions(
  params: TransactionListParams = {}
): Promise<TransactionListResponse> {
  const url = buildApiUrl("/api/v1/transactions", {
    record_type: params.record_type,
    status: params.status,
    currency: params.currency,
    merchant_id: params.merchant_id,
    date_from: params.date_from,
    date_to: params.date_to,
    min_amount: params.min_amount,
    max_amount: params.max_amount,
    reconciled: params.reconciled,
    has_discrepancy: params.has_discrepancy,
    search: params.search,
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
  });
  const res = await fetchAuthenticated(url);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function fetchTransactionDetail(id: string): Promise<TransactionDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/transactions/${id}`);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
}

export async function fetchTransactionLineage(id: string): Promise<TransactionLineageResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/transactions/${id}/lineage`);
  if (!res.ok) throw new Error(await adminErrorMessage(res));
  return res.json();
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

export type OverallExceptionState = "OPEN" | "INVESTIGATING" | "AWAITING_APPROVAL" | "APPROVED" | "EXECUTING" | "RESOLVED" | "FAILED" | "UNKNOWN";

export interface ExceptionReadSummary {
  id: string;
  type: string;
  severity: string;
  overall_state: OverallExceptionState;
  amount: number | null;
  currency: string | null;
  source_entity_type: string;
  source_entity_id: string;
  detected_at: string;
  investigation_status: string | null;
  policy_decision: string | null;
  action_request_status: string | null;
  execution_status: string | null;
}

export interface ExceptionListResponse {
  items: ExceptionReadSummary[];
  total: number;
  page: number;
  size: number;
}

export interface ExceptionDetail {
  id: string;
  type: string;
  severity: string;
  overall_state: OverallExceptionState;
  amount: number | null;
  expected_amount: number | null;
  actual_amount: number | null;
  difference_amount: number | null;
  currency: string | null;
  source_entity_type: string;
  source_entity_id: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  detected_at: string;
  run_id: string;
  rule_code: string;
  
  investigation_status: string | null;
  investigation_id: string | null;
  root_cause: string | null;
  investigation_explanation: string | null;
  
  policy_decision: string | null;
  policy_action: string | null;
  policy_rule_code: string | null;
  policy_reason: string | null;
  
  action_request_id: string | null;
  action_request_status: string | null;
  action_request_action: string | null;
  
  execution_id: string | null;
  execution_status: string | null;
  execution_error: string | null;
}

export async function fetchExceptions(params?: {
  page?: number;
  size?: number;
  type?: string;
  state?: string;
  transaction_type?: string;
}): Promise<ExceptionListResponse> {
  const url = new URL(`${bffBase()}/api/v1/exceptions`);
  if (params?.page && params?.size) {
    url.searchParams.set("offset", String((params.page - 1) * params.size));
    url.searchParams.set("limit", String(params.size));
  }
  if (params?.type && params.type !== "ALL") url.searchParams.set("type", params.type);
  if (params?.state && params.state !== "ALL") url.searchParams.set("state", params.state);
  if (params?.transaction_type && params.transaction_type !== "ALL") url.searchParams.set("transaction_type", params.transaction_type);


export type OverallExceptionState = "OPEN" | "INVESTIGATING" | "AWAITING_APPROVAL" | "APPROVED" | "EXECUTING" | "RESOLVED" | "FAILED" | "UNKNOWN";

export interface ExceptionReadSummary {
  id: string;
  type: string;
  severity: string;
  overall_state: OverallExceptionState;
  amount: number | null;
  currency: string | null;
  source_entity_type: string;
  source_entity_id: string;
  detected_at: string;
  investigation_status: string | null;
  policy_decision: string | null;
  action_request_status: string | null;
  execution_status: string | null;
}

export interface ExceptionListResponse {
  items: ExceptionReadSummary[];
  total: number;
  page: number;
  size: number;
}

export interface ExceptionDetail {
  id: string;
  type: string;
  severity: string;
  overall_state: OverallExceptionState;
  amount: number | null;
  expected_amount: number | null;
  actual_amount: number | null;
  difference_amount: number | null;
  currency: string | null;
  source_entity_type: string;
  source_entity_id: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  detected_at: string;
  run_id: string;
  rule_code: string;
  
  investigation_status: string | null;
  investigation_id: string | null;
  root_cause: string | null;
  investigation_explanation: string | null;
  
  policy_decision: string | null;
  policy_action: string | null;
  policy_rule_code: string | null;
  policy_reason: string | null;
  
  action_request_id: string | null;
  action_request_status: string | null;
  action_request_action: string | null;
  
  execution_id: string | null;
  execution_status: string | null;
  execution_error: string | null;
}

export async function fetchExceptions(params?: {
  page?: number;
  size?: number;
  type?: string;
  state?: string;
  transaction_type?: string;
}): Promise<ExceptionListResponse> {
  const url = new URL(`${bffBase()}/api/v1/exceptions`);
  if (params?.page && params?.size) {
    url.searchParams.set("offset", String((params.page - 1) * params.size));
    url.searchParams.set("limit", String(params.size));
  }
  if (params?.type && params.type !== "ALL") url.searchParams.set("type", params.type);
  if (params?.state && params.state !== "ALL") url.searchParams.set("state", params.state);
  if (params?.transaction_type && params.transaction_type !== "ALL") url.searchParams.set("transaction_type", params.transaction_type);

  const res = await fetchAuthenticated(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch exceptions: ${res.statusText}`);
  return res.json();
}

export async function fetchException(id: string): Promise<ExceptionDetail> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/exceptions/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch exception: ${res.statusText}`);
  return res.json();
}

// ─── Financial Periods (M11) ──────────────────────────────────────────────

export type PeriodStatus = "OPEN" | "CLOSING" | "CLOSED";
export type ControlStatus = "NOT_EVALUATED" | "READY" | "BLOCKED";

export interface PeriodMetrics {
  total_payments: number;
  total_settlements: number;
  total_refunds: number;
  total_fees: number;
}

export interface ControlDetail {
  status: ControlStatus;
  blocking_count: number;
  message?: string;
}

export interface PeriodReadiness {
  is_ready: boolean;
  controls: {
    unreconciled_transactions: ControlDetail;
    unresolved_exceptions: ControlDetail;
    pending_investigations: ControlDetail;
    pending_action_requests: ControlDetail;
    running_executions: ControlDetail;
  };
}

export interface FinancialPeriod {
  id: string;
  period_name: string;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  created_at: string;
  updated_at: string;
}

export interface PeriodDetailResponse {
  period: FinancialPeriod;
  metrics: PeriodMetrics;
  readiness: PeriodReadiness | null;
}

export interface PeriodListResponse {
  items: FinancialPeriod[];
  total: number;
  page: number;
  size: number;
}

export async function fetchPeriods(params?: {
  page?: number;
  size?: number;
  status?: string;
}): Promise<PeriodListResponse> {
  const url = new URL(`${bffBase()}/api/v1/periods`);
  if (params?.page && params?.size) {
    url.searchParams.set("offset", String((params.page - 1) * params.size));
    url.searchParams.set("limit", String(params.size));
  }
  if (params?.status && params.status !== "ALL") {
    url.searchParams.set("status", params.status);
  }

  const res = await fetchAuthenticated(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch periods: ${res.statusText}`);
  return res.json();
}

export async function fetchPeriod(id: string): Promise<PeriodDetailResponse> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/periods/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch period: ${res.statusText}`);
  return res.json();
}

export async function createPeriod(payload: {
  period_name: string;
  start_date: string;
  end_date: string;
}): Promise<FinancialPeriod> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/periods`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to create period: ${res.statusText}`);
  }
  return res.json();
}

export async function evaluatePeriodClose(id: string): Promise<PeriodReadiness> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/periods/${id}/evaluate`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to evaluate period close: ${res.statusText}`);
  }
  return res.json();
}

export async function closePeriod(id: string): Promise<FinancialPeriod> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/periods/${id}/close`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to close period: ${res.statusText}`);
  }
  return res.json();
}

// ─── Financial Reports (M12) ──────────────────────────────────────────────────

export interface AmountByCurrency {
  currency: string;
  count: number;
  total_amount: string; // Decimal comes as string from JSON
}

export interface ExecutiveSummary {
  period_start: string | null;
  period_end: string | null;
  period_id: string | null;
  payment_volume: AmountByCurrency[];
  refund_volume: AmountByCurrency[];
  fee_volume: AmountByCurrency[];
  settlement_volume: AmountByCurrency[];
  bank_transaction_volume: AmountByCurrency[];
  total_payment_count: number;
  total_refund_count: number;
  total_fee_count: number;
  total_settlement_count: number;
  total_bank_transaction_count: number;
  reconciled_count: number;
  unreconciled_count: number;
  discrepancy_count: number;
  unresolved_exception_count: number;
  investigation_count: number;
  pending_action_request_count: number;
  failed_execution_count: number;
  unknown_execution_count: number;
}

export interface FinancialFlowStage {
  stage: string;
  currency: string;
  count: number;
  total_amount: string;
}

export interface FinancialFlowSummary {
  period_start: string | null;
  period_end: string | null;
  stages: FinancialFlowStage[];
}

export interface ReconciliationAnalytics {
  period_start: string | null;
  period_end: string | null;
  total_payments_eligible: number;
  reconciled_count: number;
  unreconciled_count: number;
  reconciliation_rate: number | null;
  discrepancy_count: number;
  discrepancy_amount_by_currency: AmountByCurrency[];
  relationship_reconciled: number;
  relationship_discrepancy: number;
  relationship_unresolved: number;
}

export interface ExceptionStateCount {
  state: string;
  count: number;
}

export interface ExceptionTypeCount {
  type: string;
  count: number;
}

export interface RootCauseCount {
  root_cause: string;
  count: number;
}

export interface ExceptionAnalytics {
  period_start: string | null;
  period_end: string | null;
  total_exceptions: number;
  by_state: ExceptionStateCount[];
  by_type: ExceptionTypeCount[];
  by_root_cause: RootCauseCount[];
  unresolved_amount_by_currency: AmountByCurrency[];
}

export interface OperationalRiskSummary {
  unresolved_exceptions: number;
  pending_investigations: number;
  failed_investigations: number;
  pending_action_requests: number;
  failed_executions: number;
  unknown_executions: number;
  unreconciled_transaction_count: number;
  open_periods: number;
  closing_periods: number;
  blocked_periods: number;
}

export interface PeriodReportRow {
  id: string;
  period_name: string;
  start_date: string;
  end_date: string;
  status: string;
  last_readiness: boolean | null;
  last_blocker_count: number | null;
  last_evaluated_at: string | null;
  payment_count: number;
  settlement_count: number;
  exception_count: number;
}

export interface PeriodAnalyticsResponse {
  items: PeriodReportRow[];
  total: number;
}

export interface TrendPoint {
  bucket: string;
  currency: string | null;
  metric: string;
  value: string;
}

export interface TrendResponse {
  metric: string;
  granularity: string;
  timezone: string;
  data: TrendPoint[];
}

export interface BreakdownItem {
  dimension: string;
  currency: string;
  payment_count: number;
  payment_volume: string;
  refund_count: number;
  refund_volume: string;
  exception_count: number;
}

export type ReportGranularity = "day" | "week" | "month";
export type TrendMetric =
  | "payment_count"
  | "payment_volume"
  | "refund_count"
  | "refund_volume"
  | "settlement_count"
  | "settlement_volume"
  | "exception_count";
export type BreakdownDimension = "provider" | "payment_method" | "merchant_id";

function buildReportUrl(path: string, params: Record<string, string | undefined | null>): string {
  const url = new URL(`${bffBase()}/api/v1/reports/${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") url.searchParams.set(k, v);
  }
  return url.toString();
}

export async function fetchReportSummary(params?: {
  start_date?: string;
  end_date?: string;
  period_id?: string;
  currency?: string;
}): Promise<ExecutiveSummary> {
  const res = await fetchAuthenticated(buildReportUrl("summary", {
    start_date: params?.start_date,
    end_date: params?.end_date,
    period_id: params?.period_id,
    currency: params?.currency,
  }));
  if (!res.ok) throw new Error(`Failed to fetch report summary: ${res.statusText}`);
  return res.json();
}

export async function fetchFinancialFlow(params?: {
  start_date?: string;
  end_date?: string;
  period_id?: string;
}): Promise<FinancialFlowSummary> {
  const res = await fetchAuthenticated(buildReportUrl("financial-flow", {
    start_date: params?.start_date,
    end_date: params?.end_date,
    period_id: params?.period_id,
  }));
  if (!res.ok) throw new Error(`Failed to fetch financial flow: ${res.statusText}`);
  return res.json();
}

export async function fetchReconciliationAnalytics(params?: {
  start_date?: string;
  end_date?: string;
  period_id?: string;
}): Promise<ReconciliationAnalytics> {
  const res = await fetchAuthenticated(buildReportUrl("reconciliation", {
    start_date: params?.start_date,
    end_date: params?.end_date,
    period_id: params?.period_id,
  }));
  if (!res.ok) throw new Error(`Failed to fetch reconciliation analytics: ${res.statusText}`);
  return res.json();
}

export async function fetchExceptionAnalytics(params?: {
  start_date?: string;
  end_date?: string;
  period_id?: string;
}): Promise<ExceptionAnalytics> {
  const res = await fetchAuthenticated(buildReportUrl("exceptions", {
    start_date: params?.start_date,
    end_date: params?.end_date,
    period_id: params?.period_id,
  }));
  if (!res.ok) throw new Error(`Failed to fetch exception analytics: ${res.statusText}`);
  return res.json();
}

export async function fetchOperationalRisk(): Promise<OperationalRiskSummary> {
  const res = await fetchAuthenticated(`${bffBase()}/api/v1/reports/operations`);
  if (!res.ok) throw new Error(`Failed to fetch operational risk: ${res.statusText}`);
  return res.json();
}

export async function fetchReportPeriods(params?: {
  limit?: number;
  offset?: number;
}): Promise<PeriodAnalyticsResponse> {
  const url = new URL(`${bffBase()}/api/v1/reports/periods`);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.offset) url.searchParams.set("offset", String(params.offset));
  const res = await fetchAuthenticated(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch period analytics: ${res.statusText}`);
  return res.json();
}

export async function fetchTrends(params: {
  metric: TrendMetric;
  granularity?: ReportGranularity;
  start_date?: string;
  end_date?: string;
}): Promise<TrendResponse> {
  const res = await fetchAuthenticated(buildReportUrl("trends", {
    metric: params.metric,
    granularity: params.granularity ?? "day",
    start_date: params.start_date,
    end_date: params.end_date,
  }));
  if (!res.ok) throw new Error(`Failed to fetch trends: ${res.statusText}`);
  return res.json();
}

export async function fetchBreakdowns(params: {
  dimension: BreakdownDimension;
  start_date?: string;
  end_date?: string;
  period_id?: string;
}): Promise<BreakdownItem[]> {
  const res = await fetchAuthenticated(buildReportUrl("breakdowns", {
    dimension: params.dimension,
    start_date: params.start_date,
    end_date: params.end_date,
    period_id: params.period_id,
  }));
  if (!res.ok) throw new Error(`Failed to fetch breakdowns: ${res.statusText}`);
  return res.json();
}
