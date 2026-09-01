import { ReconciliationRunResponse } from "../../lib/api/reconciliation";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { CheckCircle2, XCircle, Clock, AlertTriangle, ListFilter } from "lucide-react";

function StatusBadge({ status }: { status: string }) {
  switch (status.toUpperCase()) {
    case "COMPLETED":
      return (
        <Badge variant="success" className="flex items-center space-x-1 px-2 py-0.5 w-fit">
          <CheckCircle2 className="w-3 h-3" />
          <span>COMPLETED</span>
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="error" className="flex items-center space-x-1 px-2 py-0.5 w-fit">
          <XCircle className="w-3 h-3" />
          <span>FAILED</span>
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="warning" className="flex items-center space-x-1 px-2 py-0.5 w-fit">
          <Clock className="w-3 h-3 animate-pulse" />
          <span>RUNNING</span>
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="flex items-center space-x-1 px-2 py-0.5 w-fit">
          <AlertTriangle className="w-3 h-3" />
          <span>{status.toUpperCase()}</span>
        </Badge>
      );
  }
}

export function ReconciliationRunHistory({ runs }: { runs: ReconciliationRunResponse[] }) {
  if (!runs || runs.length === 0) {
    return (
      <Card className="flex flex-col items-center justify-center p-12 bg-slate-900/40 border-slate-800 text-center">
        <ListFilter className="w-8 h-8 text-slate-600 mb-3" />
        <h3 className="text-sm font-medium text-slate-300">No Run History</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-sm">
          No reconciliation runs have been executed yet. Run reconciliation to generate history.
        </p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col bg-slate-900/40 border-slate-800 overflow-hidden">
      <div className="p-4 sm:p-5 border-b border-slate-800/80">
        <h3 className="text-sm font-semibold text-slate-200">Reconciliation Run History</h3>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/50">
              <th className="px-4 sm:px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                Run ID
              </th>
              <th className="px-4 sm:px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                Status
              </th>
              <th className="px-4 sm:px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap text-right">
                Processed
              </th>
              <th className="px-4 sm:px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap text-right">
                Matches
              </th>
              <th className="px-4 sm:px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap text-right">
                Discrepancies
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {runs.map((run) => (
              <tr 
                key={run.run_id} 
                className="hover:bg-slate-800/20 transition-colors group"
              >
                <td className="px-4 sm:px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-mono text-slate-300 group-hover:text-emerald-400 transition-colors">
                    {run.run_id}
                  </div>
                </td>
                <td className="px-4 sm:px-6 py-4 whitespace-nowrap">
                  <StatusBadge status={run.status} />
                </td>
                <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-right">
                  <div className="text-sm text-slate-300 font-medium">
                    {run.total_records_processed}
                  </div>
                </td>
                <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-right">
                  <div className="text-sm font-medium text-emerald-400/90">
                    {run.matches_created}
                  </div>
                </td>
                <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-right">
                  <div className={`text-sm font-medium ${run.discrepancies_found > 0 ? 'text-rose-400' : 'text-slate-500'}`}>
                    {run.discrepancies_found}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
