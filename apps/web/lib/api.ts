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
