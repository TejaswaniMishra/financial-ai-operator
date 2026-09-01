import { ReconciliationRunResponse } from "../../lib/api/reconciliation";
import { Badge } from "../ui/badge";
import { CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react";
import { Card } from "../ui/card";

function StatusBadge({ status }: { status: string }) {
  switch (status.toUpperCase()) {
    case "COMPLETED":
      return (
        <Badge variant="success" className="flex items-center space-x-1 px-2.5 py-1">
          <CheckCircle2 className="w-3 h-3" />
          <span>COMPLETED</span>
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="error" className="flex items-center space-x-1 px-2.5 py-1">
          <XCircle className="w-3 h-3" />
          <span>FAILED</span>
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="warning" className="flex items-center space-x-1 px-2.5 py-1">
          <Clock className="w-3 h-3 animate-pulse" />
          <span>RUNNING</span>
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="flex items-center space-x-1 px-2.5 py-1">
          <AlertTriangle className="w-3 h-3" />
          <span>{status.toUpperCase()}</span>
        </Badge>
      );
  }
}

export function ReconciliationStatus({ latestRun }: { latestRun: ReconciliationRunResponse | undefined }) {
  if (!latestRun) return null;

  return (
    <Card className="p-4 sm:p-6 bg-slate-900/40 border-slate-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h2 className="text-lg font-medium text-slate-100">Latest Run Status</h2>
            <StatusBadge status={latestRun.status} />
          </div>
          <div className="text-sm text-slate-400 font-mono">
            Run ID: {latestRun.run_id}
          </div>
        </div>
        
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex flex-col">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Processed</span>
            <span className="text-xl font-semibold text-slate-200">{latestRun.total_records_processed}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Matched</span>
            <span className="text-xl font-semibold text-emerald-400">{latestRun.matches_created}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Discrepancies</span>
            <span className="text-xl font-semibold text-rose-400">{latestRun.discrepancies_found}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
