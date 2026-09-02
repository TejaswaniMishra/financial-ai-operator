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

export interface SystemInfoResponse {
  name: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  active_services: Record<string, "healthy" | "degraded" | "unhealthy">;
  architecture_phase: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch health status: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSystemInfo(): Promise<SystemInfoResponse> {
  const res = await fetch(`${API_BASE}/api/v1/system/info`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch system info: ${res.statusText}`);
  }
  return res.json();
}

export interface MetricsOverviewResponse {
  merchants: number;
  payments: number;
  settlements: number;
  bank_transactions: number;
  total_volume: number;
}

export async function fetchMetricsOverview(): Promise<MetricsOverviewResponse> {
  const res = await fetch(`${API_BASE}/api/v1/metrics/overview`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch metrics overview: ${res.statusText}`);
  }
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
  const res = await fetch(`${API_BASE}/api/v1/reconciliation/runs`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch reconciliation runs: ${res.statusText}`);
  }
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
  const res = await fetch(`${API_BASE}/api/v1/reconciliation/discrepancies`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch reconciliation discrepancies: ${res.statusText}`);
  }
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
  const res = await fetch(`${API_BASE}/api/v1/investigations/discrepancy/${discrepancyId}/run`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(`Failed to run investigation: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchInvestigations(): Promise<InvestigationListItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/investigations`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch investigations: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchInvestigation(investigationId: string): Promise<InvestigationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/investigations/${investigationId}`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch investigation: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchInvestigationAttempts(investigationId: string): Promise<InvestigationAttempt[]> {
  const res = await fetch(`${API_BASE}/api/v1/investigations/${investigationId}/attempts`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch investigation attempts: ${res.statusText}`);
  }
  return res.json();
}

export async function approveInvestigation(investigationId: string): Promise<InvestigationApprovalResponse> {
  const res = await fetch(`${API_BASE}/api/v1/investigations/${investigationId}/approve`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(`Failed to approve investigation: ${res.statusText}`);
  }
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
  const res = await fetch(`${API_BASE}/api/v1/investigations/${investigationId}/attempts/${attemptId}`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch investigation attempt result: ${res.statusText}`);
  }
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
  const res = await fetch(`${API_BASE}/api/v1/action-requests`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch action requests: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchActionRequest(id: string): Promise<ActionRequestResponse> {
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch action request: ${res.statusText}`);
  }
  return res.json();
}

export async function approveActionRequest(id: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to approve action request: ${res.statusText}`);
  }
  return res.json();
}

export async function rejectActionRequest(id: string, reason: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, actor })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to reject action request: ${res.statusText}`);
  }
  return res.json();
}

export async function cancelActionRequest(id: string, reason: string, actor: string = "system"): Promise<ActionRequestResponse> {
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, actor })
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
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}/executions`, {
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch action executions: ${res.statusText}`);
  }
  return res.json();
}

export async function executeActionRequest(id: string, idempotency_key?: string): Promise<ActionExecutionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/action-requests/${id}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idempotency_key })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to execute action request: ${res.statusText}`);
  }
  return res.json();
}
