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
  result: unknown | null;
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
