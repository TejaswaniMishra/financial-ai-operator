"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Search, Filter, AlertCircle, AlertTriangle, ArrowRight, RefreshCw, FileSearch, ShieldCheck, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchInvestigations, InvestigationListItem } from "../../lib/api";

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<InvestigationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInvestigations();
      setInvestigations(data || []);
    } catch (err: any) {
      setError(err.message || "Failed to load investigations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const totalInvestigations = investigations.length;
  const runningCount = investigations.filter(inv => inv.status === "PENDING" || inv.status === "RUNNING").length;
  const completedValidCount = investigations.filter(inv => inv.status === "COMPLETED").length;
  const failedInvalidCount = investigations.filter(inv => inv.status === "FAILED").length;

  const uniqueStatuses = useMemo(() => Array.from(new Set(investigations.map(i => i.status))), [investigations]);

  const filteredInvestigations = useMemo(() => {
    return investigations.filter(inv => {
      if (statusFilter !== "ALL" && inv.status !== statusFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        const matches = 
          inv.id.toLowerCase().includes(q) || 
          inv.discrepancy_id.toLowerCase().includes(q) ||
          (inv.active_attempt_id && inv.active_attempt_id.toLowerCase().includes(q));
        if (!matches) return false;
      }
      return true;
    });
  }, [investigations, search, statusFilter]);

  const router = useRouter();

  const handleRowClick = (id: string) => {
    router.push(`/investigations/${id}`);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "COMPLETED":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-matched/10 text-matched border border-matched/20">Completed</span>;
      case "FAILED":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-error/10 text-error border border-error/20">Failed</span>;
      case "PENDING":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-warning/10 text-warning border border-warning/20">Pending</span>;
      case "RUNNING":
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info/10 text-info border border-info/20">Running</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-muted text-foreground border border-border">{status}</span>;
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-12 w-1/3 bg-surface-muted rounded"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="h-24 bg-surface-muted rounded-xl"></div>
          <div className="h-24 bg-surface-muted rounded-xl"></div>
          <div className="h-24 bg-surface-muted rounded-xl"></div>
          <div className="h-24 bg-surface-muted rounded-xl"></div>
        </div>
        <div className="h-96 w-full bg-surface-muted rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Investigations</h1>
        <p className="text-secondary max-w-2xl">
          Track and manage AI-assisted investigation cases. Monitor ongoing analysis, review completed reports, and take action on discrepancies.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Total Investigations</h3>
            <AlertCircle className="w-4 h-4 text-discrepancy" />
          </div>
          <div className="text-kpi">{totalInvestigations}</div>
          <p className="text-status text-muted-foreground mt-2">All cases</p>
        </div>

        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Running</h3>
            <RefreshCw className="w-4 h-4 text-info" />
          </div>
          <div className="text-kpi">{runningCount}</div>
          <p className="text-status text-muted-foreground mt-2">In progress</p>
        </div>

        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Completed / Valid</h3>
            <ShieldCheck className="w-4 h-4 text-matched" />
          </div>
          <div className="text-kpi">{completedValidCount}</div>
          <p className="text-status text-muted-foreground mt-2">Ready for review</p>
        </div>

        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Failed / Invalid</h3>
            <XCircle className="w-4 h-4 text-error" />
          </div>
          <div className="text-kpi">{failedInvalidCount}</div>
          <p className="text-status text-muted-foreground mt-2">Requires manual intervention</p>
        </div>
      </div>

      {error ? (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between shadow-subtle">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button
            onClick={loadData}
            className="px-4 py-1.5 bg-destructive/20 hover:bg-destructive/30 rounded text-sm font-medium transition-colors focus-ring"
          >
            Retry
          </button>
        </div>
      ) : investigations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center border border-dashed border-border rounded-xl bg-surface/50 shadow-subtle">
          <FileSearch className="w-10 h-10 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">
            No investigations yet
          </h3>
          <p className="text-muted-foreground text-sm max-w-sm">
            There are currently no investigation records.
          </p>
        </div>
      ) : (
        <div className="bg-card border border-border shadow-subtle rounded-xl overflow-hidden flex flex-col min-h-[400px]">
          {/* Toolbar */}
          <div className="p-4 sm:p-5 border-b border-border flex flex-col sm:flex-row gap-4 justify-between bg-surface-muted/30">
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search IDs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground transition-all"
              />
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
              <div className="flex items-center space-x-2 shrink-0">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-sm bg-surface border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <option value="ALL">All Statuses</option>
                  {uniqueStatuses.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-muted border-b border-border">
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Investigation</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Discrepancy</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Status</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Active Attempt</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">Created</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredInvestigations.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-sm text-muted-foreground">
                      No investigations match the current filters. 
                      <button 
                        onClick={() => { setSearch(""); setStatusFilter("ALL"); }} 
                        className="text-primary hover:underline ml-1 font-medium focus-ring rounded"
                      >
                        Clear filters
                      </button>
                    </td>
                  </tr>
                ) : (
                  filteredInvestigations.map((inv) => (
                    <tr key={inv.id} onClick={() => handleRowClick(inv.id)} className="hover:bg-surface-muted/50 transition-colors group cursor-pointer">
                      <td className="px-5 py-3">
                        <div className="font-medium text-sm text-foreground">Inv</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5" title={inv.id}>
                          {inv.id.substring(0, 8)}...
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="font-medium text-sm text-foreground">Discrepancy</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5" title={inv.discrepancy_id}>
                          {inv.discrepancy_id.substring(0, 8)}...
                        </div>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        {getStatusBadge(inv.status)}
                      </td>
                      <td className="px-5 py-3">
                        {inv.active_attempt_id ? (
                          <div className="text-xs text-muted-foreground font-mono" title={inv.active_attempt_id}>
                            {inv.active_attempt_id.substring(0, 8)}...
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-secondary whitespace-nowrap">
                        {inv.created_at ? new Date(inv.created_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-5 py-3 text-right whitespace-nowrap">
                        <button className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded transition-colors focus-ring shadow-sm">
                          View
                          <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
