import { ReconciliationRunResponse } from "../../lib/api/reconciliation";
import { Card } from "../ui/card";
import { CheckCircle2, AlertCircle, Percent } from "lucide-react";

export function ReconciliationSummary({
  runs,
}: {
  runs: ReconciliationRunResponse[];
}) {
  if (!runs || runs.length === 0) return null;

  // Aggregate metrics across recent runs (up to what API returned)
  const totalProcessed = runs.reduce(
    (acc, run) => acc + run.total_records_processed,
    0,
  );
  const totalMatched = runs.reduce((acc, run) => acc + run.matches_created, 0);
  const totalDiscrepancies = runs.reduce(
    (acc, run) => acc + run.discrepancies_found,
    0,
  );

  // Compute aggregate match rate safely
  const matchRate =
    totalProcessed > 0 ? (totalMatched / totalProcessed) * 100 : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <Card className="p-5 shadow-subtle border-border bg-card">
        <div className="flex items-center justify-between mb-3">
          <span className="text-card-title">Total Matched</span>
          <CheckCircle2 className="w-4 h-4 text-matched" />
        </div>
        <div className="text-kpi">{totalMatched}</div>
        <p className="text-status text-muted-foreground mt-2">
          Records successfully reconciled
        </p>
      </Card>

      <Card className="p-5 shadow-subtle border-border bg-card">
        <div className="flex items-center justify-between mb-3">
          <span className="text-card-title">Total Discrepancies</span>
          <AlertCircle className="w-4 h-4 text-discrepancy" />
        </div>
        <div className="text-kpi">{totalDiscrepancies}</div>
        <p className="text-status text-muted-foreground mt-2">
          Exceptions requiring investigation
        </p>
      </Card>

      <Card className="p-5 shadow-subtle border-border bg-card">
        <div className="flex items-center justify-between mb-3">
          <span className="text-card-title">Aggregate Match Rate</span>
          <Percent className="w-4 h-4 text-primary" />
        </div>
        <div className="text-kpi">{matchRate.toFixed(1)}%</div>
        <p className="text-status text-muted-foreground mt-2">
          Across all {runs.length} loaded runs
        </p>
      </Card>
    </div>
  );
}
