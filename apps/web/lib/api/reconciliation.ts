import { fetchClient } from "../api-client";

export interface ReconciliationRun {
  run_id: string;
  status: string;
  total_records_processed: number;
  matches_created: number;
  discrepancies_found: number;
}

// We will use standard primitive number mapping for 'int' in TypeScript,
// so redefining:
export interface ReconciliationRunResponse {
  run_id: string;
  status: string;
  total_records_processed: number;
  matches_created: number;
  discrepancies_found: number;
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
  /** Decimal amounts arrive as JSON strings (Pydantic Decimal serialization). */
  difference_amount: string | null;
  currency: string | null;
  created_at: string;
}

export const reconciliationApi = {
  /**
   * Triggers a new deterministic reconciliation engine run synchronously.
   */
  runReconciliation: () => 
    fetchClient<ReconciliationRunResponse>("/api/v1/reconciliation/run", {
      method: "POST",
    }),

  /**
   * Retrieves the history of reconciliation runs.
   */
  getReconciliationRuns: () =>
    fetchClient<ReconciliationRunResponse[]>("/api/v1/reconciliation/runs"),

  /**
   * Retrieves current discrepancies.
   */
  getDiscrepancies: () =>
    fetchClient<DiscrepancyResponse[]>("/api/v1/reconciliation/discrepancies"),
};
