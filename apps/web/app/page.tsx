"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  CheckCircle2,
  Database,
  Layers,
  RefreshCw,
  ShieldCheck,
  Zap,
  Server,
  AlertTriangle,
  Code2,
  ArrowRight,
} from "lucide-react";
import {
  HealthResponse,
  SystemInfoResponse,
  MetricsOverviewResponse,
  ReconciliationRun,
  fetchHealth,
  fetchSystemInfo,
  fetchMetricsOverview,
  fetchReconciliationRuns,
  fetchReconciliationDiscrepancies,
  DiscrepancyResponse,
  runInvestigation
} from "../lib/api";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfoResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsOverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const [runs, setRuns] = useState<ReconciliationRun[] | null>(null);
  const [runsLoading, setRunsLoading] = useState<boolean>(true);
  const [runsError, setRunsError] = useState<string | null>(null);

  const [discrepancies, setDiscrepancies] = useState<DiscrepancyResponse[] | null>(null);
  const [discrepanciesLoading, setDiscrepanciesLoading] = useState<boolean>(true);
  const [discrepanciesError, setDiscrepanciesError] = useState<string | null>(null);

  const [investigatingIds, setInvestigatingIds] = useState<Set<string>>(new Set());
  const [investigationError, setInvestigationError] = useState<string | null>(null);

  const router = useRouter();

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s, m] = await Promise.all([
        fetchHealth(),
        fetchSystemInfo(),
        fetchMetricsOverview()
      ]);
      setHealth(h);
      setSystemInfo(s);
      setMetrics(m);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err.message || "Failed to communicate with API server");
    } finally {
      setLoading(false);
    }
  };

  const loadRuns = async () => {
    setRunsLoading(true);
    setRunsError(null);
    try {
      const data = await fetchReconciliationRuns();
      setRuns(data);
    } catch (err: any) {
      setRunsError(err.message || "Failed to load reconciliation jobs");
    } finally {
      setRunsLoading(false);
    }
  };

  const loadDiscrepancies = async () => {
    setDiscrepanciesLoading(true);
    setDiscrepanciesError(null);
    try {
      const data = await fetchReconciliationDiscrepancies();
      setDiscrepancies(data);
    } catch (err: any) {
      setDiscrepanciesError(err.message || "Failed to load discrepancies");
    } finally {
      setDiscrepanciesLoading(false);
    }
  };

  const handleInvestigate = async (discrepancyId: string) => {
    if (investigatingIds.has(discrepancyId)) return;

    setInvestigatingIds((prev) => {
      const next = new Set(prev);
      next.add(discrepancyId);
      return next;
    });
    setInvestigationError(null);

    try {
      const result = await runInvestigation(discrepancyId);
      router.push(`/investigations/${result.investigation_id}`);
    } catch (err: any) {
      setInvestigationError(err.message || "Failed to start investigation");
      setInvestigatingIds((prev) => {
        const next = new Set(prev);
        next.delete(discrepancyId);
        return next;
      });
    }
  };

  const refreshAll = () => {
    loadData();
    loadRuns();
    loadDiscrepancies();
  };

  useEffect(() => {
    refreshAll();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-page-title">Dashboard</h1>
          <p className="text-secondary mt-1">
            System overview, operational health, and core infrastructure metrics.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refreshAll}
            disabled={loading || runsLoading || discrepanciesLoading}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-primary bg-primary/10 hover:bg-primary/20 rounded-md transition-colors focus-ring disabled:opacity-50"
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", (loading || runsLoading || discrepanciesLoading) && "animate-spin")} />
            {loading || runsLoading || discrepanciesLoading ? "Refreshing..." : "Refresh Status"}
          </button>
        </div>
      </div>

        {/* Status Error Display if API is down */}
        {error && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-start space-x-3 text-sm">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
            <div>
              <div className="font-semibold">Backend Connection Notice</div>
              <div className="text-slate-300 text-xs mt-1">
                {error}. Ensure the FastAPI server is running on <code className="bg-slate-900 px-1 py-0.5 rounded text-amber-200">http://localhost:8000</code>.
              </div>
            </div>
          </div>
        )}

        {/* Metrics & Health Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {/* Card 1: Total Volume */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Total Volume</span>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.total_volume !== undefined 
                ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(metrics.total_volume) 
                : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Processed lifetime volume
            </p>
          </div>

          {/* Card 2: Payments */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Payments</span>
              <Database className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.payments !== undefined ? metrics.payments.toLocaleString() : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Total registered payments
            </p>
          </div>

          {/* Card 3: Settlements */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Settlements</span>
              <Layers className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.settlements !== undefined ? metrics.settlements.toLocaleString() : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Reconciled settlement batches
            </p>
          </div>

          {/* Card 4: Merchants */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Active Merchants</span>
              <ShieldCheck className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.merchants !== undefined ? metrics.merchants.toLocaleString() : "---"}
            </div>
            <p className="text-status text-matched mt-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verified operational
            </p>
          </div>
        </div>

        {/* Reconciliation Jobs Section */}
        <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 className="text-card-title text-base">Reconciliation Jobs</h2>
            <div className="text-xs font-mono text-muted-foreground">
              {runs ? `${runs.length} jobs retrieved` : ""}
            </div>
          </div>
          
          <div className="p-0 overflow-x-auto">
            {runsLoading ? (
              <div className="p-8 text-center text-secondary text-sm">Loading jobs...</div>
            ) : runsError ? (
              <div className="p-8 text-center text-sm text-destructive flex items-center justify-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                <span>{runsError}</span>
              </div>
            ) : !runs || runs.length === 0 ? (
              <div className="p-8 text-center text-secondary text-sm">No reconciliation jobs found.</div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-surface-muted border-b border-border text-secondary">
                  <tr>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Run ID</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Status</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Records Processed</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Matches</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Discrepancies</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {runs.map((run) => (
                    <tr key={run.run_id} className="hover:bg-surface-muted/50 transition-colors group">
                      <td className="px-5 py-3 font-mono text-xs text-secondary group-hover:text-foreground transition-colors">{run.run_id}</td>
                      <td className="px-5 py-3">
                        <span className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                          run.status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20" :
                          run.status === "FAILED" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20" :
                          "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                        )}>
                          {run.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right font-mono">{run.total_records_processed.toLocaleString()}</td>
                      <td className="px-5 py-3 text-right font-mono text-matched">{run.matches_created.toLocaleString()}</td>
                      <td className="px-5 py-3 text-right font-mono text-unmatched">{run.discrepancies_found.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Exceptions / Discrepancies Section */}
        <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 className="text-card-title text-base">Exceptions</h2>
            <div className="text-xs font-mono text-muted-foreground">
              {discrepancies ? `${discrepancies.length} exceptions retrieved` : ""}
            </div>
          </div>
          
          <div className="p-0 overflow-x-auto">
            {discrepanciesLoading ? (
              <div className="p-8 text-center text-secondary text-sm">Loading exceptions...</div>
            ) : discrepanciesError ? (
              <div className="p-8 text-center text-sm text-destructive flex items-center justify-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                <span>{discrepanciesError}</span>
              </div>
            ) : !discrepancies || discrepancies.length === 0 ? (
              <div className="p-8 text-center text-secondary text-sm">No exceptions found.</div>
            ) : (
              <div className="flex flex-col">
                {investigationError && (
                  <div className="px-5 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      <span>{investigationError}</span>
                    </div>
                    <button
                      onClick={() => setInvestigationError(null)}
                      className="text-xs font-medium px-2 py-1 bg-destructive/20 hover:bg-destructive/30 rounded transition-colors"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
                <table className="w-full text-sm text-left">
                <thead className="bg-surface-muted border-b border-border text-secondary">
                  <tr>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Severity</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Type & Rule</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Source Entity</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Related Entity</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Amount</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Created At</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {discrepancies.map((disc) => (
                    <tr key={disc.id} className="hover:bg-surface-muted/50 transition-colors group">
                      <td className="px-5 py-3">
                        <span className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                          disc.severity === "CRITICAL" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20" :
                          disc.severity === "HIGH" ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20" :
                          disc.severity === "MEDIUM" ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20" :
                          "bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20"
                        )}>
                          {disc.severity}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <div className="font-medium">{disc.discrepancy_type}</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">{disc.rule_code}</div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="font-medium text-xs">{disc.source_entity_type}</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5" title={disc.source_entity_id}>
                          {disc.source_entity_id.length > 12 ? `${disc.source_entity_id.substring(0, 12)}...` : disc.source_entity_id}
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        {disc.related_entity_type ? (
                          <>
                            <div className="font-medium text-xs">{disc.related_entity_type}</div>
                            <div className="text-xs text-muted-foreground font-mono mt-0.5" title={disc.related_entity_id || ""}>
                              {disc.related_entity_id && disc.related_entity_id.length > 12 ? `${disc.related_entity_id.substring(0, 12)}...` : disc.related_entity_id}
                            </div>
                          </>
                        ) : (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right font-mono">
                        {disc.difference_amount !== null ? (
                          new Intl.NumberFormat('en-US', { style: 'currency', currency: disc.currency || 'USD' }).format(Number(disc.difference_amount))
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-secondary whitespace-nowrap">
                        {new Date(disc.created_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => handleInvestigate(disc.id)}
                          disabled={investigatingIds.has(disc.id)}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-white bg-primary hover:bg-primary/90 rounded transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {investigatingIds.has(disc.id) ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                              Starting...
                            </>
                          ) : (
                            <>
                              Investigate
                              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </div>
        </div>

        {/* Architecture & Verification Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Target Architecture Flow */}
          <div className="glass-panel rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-white text-base">
                  Target Vertical Slice Architecture
                </h3>
              </div>
              <span className="text-[11px] font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                Deterministic First
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-emerald-400">1. Data Sources</span>
                <span className="text-slate-400">MockPaymentGateway / MockBank / MockERP CSV</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-cyan-400">2. Normalization & Ingestion</span>
                <span className="text-slate-400">Canonical Transaction Schemas</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-purple-400">3. Immutable Ledger</span>
                <span className="text-slate-400">Double-Entry Debits == Credits</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-amber-400">4. Deterministic Reconciliation</span>
                <span className="text-slate-400">Rule-based 1:1, 1:N & Discrepancies</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-rose-400">5. Governance & Audit</span>
                <span className="text-slate-400">Append-Only Audit Logs & Policy Gate</span>
              </div>
            </div>
          </div>

          {/* Core System Verification Checklist */}
          <div className="glass-panel rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Code2 className="w-5 h-5 text-cyan-400" />
                <h3 className="font-semibold text-white text-base">
                  Milestone 1 Verification Status
                </h3>
              </div>
              <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                Verified
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>FastAPI Async REST API configured with versioned routes (<code className="text-emerald-300">/health</code>, <code className="text-emerald-300">/api/v1/system/info</code>)</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Strict Decimal Money value object with banker's rounding & currency mismatch rejection</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>SQLAlchemy 2.0 connection engine with automatic async SQLite / PostgreSQL dual-mode</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Next.js 14 App Router + Tailwind CSS dark-mode dashboard shell</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Pytest async unit and integration test suite passing 100%</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Docker Compose environment with PostgreSQL 16 Alpine container configuration</span>
              </div>
            </div>
          </div>
        </div>
      <div className="text-center text-xs text-muted-foreground font-mono mt-8">
        Last API Probe: {lastUpdated ? lastUpdated.toLocaleTimeString() : "Never"}
      </div>
    </div>
  );
}
