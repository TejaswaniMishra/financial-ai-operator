"use client";

import React, { useEffect, useState, useMemo } from "react";
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
        {/* Placeholder for table */}
        <div className="p-8 text-center text-muted-foreground flex flex-col items-center justify-center flex-1">
          <FileSearch className="w-10 h-10 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">Investigations Loading...</h3>
        </div>
      </div>
    </div>
  );
}
