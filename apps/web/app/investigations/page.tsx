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

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Investigations</h1>
        <p className="text-secondary max-w-2xl">
          Track and manage AI-assisted investigation cases. Monitor ongoing analysis, review completed reports, and take action on discrepancies.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 sm:gap-6">
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

      <div className="bg-card border border-border shadow-subtle rounded-xl overflow-hidden flex flex-col min-h-[400px]">
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
              {investigations.map((inv) => (
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
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
