"use client";

import { useEffect, useState, useCallback } from "react";
import { ReconciliationHeader } from "../../components/reconciliation/reconciliation-header";
import { ReconciliationRunHistory } from "../../components/reconciliation/reconciliation-run-history";
import { ReconciliationSummary } from "../../components/reconciliation/reconciliation-summary";
import { ReconciliationStatus } from "../../components/reconciliation/reconciliation-status";
import { ReconciliationDiscrepancies } from "../../components/reconciliation/reconciliation-discrepancies";
import { ReconciliationSkeleton } from "../../components/reconciliation/reconciliation-skeleton";
import { ReconciliationExplanation } from "../../components/reconciliation/reconciliation-explanation";
import { reconciliationApi, ReconciliationRunResponse, DiscrepancyResponse } from "../../lib/api/reconciliation";

export default function ReconciliationWorkspace() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [runs, setRuns] = useState<ReconciliationRunResponse[]>([]);
  const [discrepancies, setDiscrepancies] = useState<DiscrepancyResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [runsData, discrepanciesData] = await Promise.all([
        reconciliationApi.getReconciliationRuns(),
        reconciliationApi.getDiscrepancies().catch(() => []) // Partial failure fallback for discrepancies
      ]);
      setRuns(runsData);
      setDiscrepancies(discrepanciesData);
    } catch (err: any) {
      setError(err.message || "Failed to load reconciliation data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return <ReconciliationSkeleton />;
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-12">
      <ReconciliationHeader 
        onRunComplete={() => loadData(true)} 
        isRefreshing={refreshing} 
      />

      {error ? (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button 
            onClick={() => loadData(true)}
            className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 rounded transition-colors"
          >
            Retry
          </button>
        </div>
      ) : runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/20">
          <h3 className="text-lg font-medium text-slate-300 mb-2">No reconciliation runs yet</h3>
          <p className="text-slate-500 text-sm mb-6 max-w-sm">
            Run reconciliation to analyze the current financial records.
          </p>
        </div>
      ) : (
        <>
          <ReconciliationStatus latestRun={runs[0]} />
          <ReconciliationSummary runs={runs} />
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <ReconciliationRunHistory runs={runs} />
            </div>
            <div className="space-y-6">
              <ReconciliationDiscrepancies discrepancies={discrepancies} />
              <ReconciliationExplanation />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
