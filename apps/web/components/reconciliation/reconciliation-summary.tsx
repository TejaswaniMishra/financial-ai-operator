import { ReconciliationRunResponse } from "../../lib/api/reconciliation";
import { Card } from "../ui/card";
import { CheckCircle2, AlertCircle, Percent } from "lucide-react";

export function ReconciliationSummary({ runs }: { runs: ReconciliationRunResponse[] }) {
  if (!runs || runs.length === 0) return null;

  // Aggregate metrics across recent runs (up to what API returned)
  const totalProcessed = runs.reduce((acc, run) => acc + run.total_records_processed, 0);
  const totalMatched = runs.reduce((acc, run) => acc + run.matches_created, 0);
  const totalDiscrepancies = runs.reduce((acc, run) => acc + run.discrepancies_found, 0);

  // Compute aggregate match rate safely
  const matchRate = totalProcessed > 0 ? (totalMatched / totalProcessed) * 100 : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <Card className="p-6 bg-slate-900/40 border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-400">Total Matched</h3>
          <div className="p-2 bg-emerald-500/10 rounded-lg">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
        </div>
        <div>
          <div className="text-3xl font-bold text-slate-100">{totalMatched}</div>
          <p className="text-xs text-slate-500 mt-1">Records successfully reconciled</p>
        </div>
      </Card>

      <Card className="p-6 bg-slate-900/40 border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-400">Total Discrepancies</h3>
          <div className="p-2 bg-rose-500/10 rounded-lg">
            <AlertCircle className="w-5 h-5 text-rose-400" />
          </div>
        </div>
        <div>
          <div className="text-3xl font-bold text-slate-100">{totalDiscrepancies}</div>
          <p className="text-xs text-slate-500 mt-1">Exceptions requiring investigation</p>
        </div>
      </Card>

      <Card className="p-6 bg-slate-900/40 border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-400">Aggregate Match Rate</h3>
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Percent className="w-5 h-5 text-blue-400" />
          </div>
        </div>
        <div>
          <div className="text-3xl font-bold text-slate-100">{matchRate.toFixed(1)}%</div>
          <p className="text-xs text-slate-500 mt-1">Across all {runs.length} loaded runs</p>
        </div>
      </Card>
    </div>
  );
}
