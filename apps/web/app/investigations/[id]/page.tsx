
"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  ArrowLeft, 
  ChevronRight, 
  Activity, 
  AlertTriangle,
  BrainCircuit,
  ShieldCheck,
  CheckCircle2,
  Clock,
  FileText
} from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchInvestigation, InvestigationResponse, fetchInvestigationAttempts, InvestigationAttempt } from "../../../lib/api";

export default function InvestigationDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Attempts state
  const [attempts, setAttempts] = useState<InvestigationAttempt[] | null>(null);
  const [attemptsLoading, setAttemptsLoading] = useState<boolean>(false);
  const [attemptsError, setAttemptsError] = useState<string | null>(null);

  const loadInvestigation = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInvestigation(id);
      setInvestigation(data);
    } catch (err: any) {
      setError(err.message || "Failed to load investigation details");
    } finally {
      setLoading(false);
    }
  };

  const loadAttempts = async () => {
    setAttemptsLoading(true);
    setAttemptsError(null);
    try {
      const data = await fetchInvestigationAttempts(id);
      setAttempts(data);
    } catch (err: any) {
      setAttemptsError(err.message || "Failed to load attempts");
    } finally {
      setAttemptsLoading(false);
    }
  };

  useEffect(() => {
    loadInvestigation();
  }, [id]);

  // Load attempts after investigation is fetched (or regardless)
  useEffect(() => {
    if (id) {
      loadAttempts();
    }
  }, [id]);

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center text-sm text-muted-foreground font-medium">
        <Link href="/" className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="hover:text-foreground transition-colors cursor-pointer">
          Investigations
        </span>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="text-foreground">Investigation Detail</span>
      </nav>

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link 
              href="/" 
              className="p-1 -ml-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-surface-muted focus-ring"
              aria-label="Back to Dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Investigation
            </h1>
            {investigation && (
              <span className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
                investigation.status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" :
                investigation.status === "FAILED" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20" :
                investigation.status === "IN_PROGRESS" ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20" :
                "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20"
              )}>
                {investigation.status}
              </span>
            )}
          </div>
          <div className="flex items-center text-sm text-muted-foreground font-mono mt-1 ml-9">
            {id}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Approval Action Area */}
          <button 
            disabled
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            <ShieldCheck className="w-4 h-4 mr-2" />
            Approve Investigation
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Overview and Evidence */}
        <div className="lg:col-span-1 space-y-6">
          {/* Overview Card */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <h2 className="text-card-title text-base mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-muted-foreground" />
              Overview
            </h2>
            <div className="space-y-4">
              {loading ? (
                <div className="text-sm text-secondary animate-pulse">Loading overview...</div>
              ) : error ? (
                <div className="text-sm text-destructive flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{error}</span>
                  </div>
                  <button
                    onClick={loadInvestigation}
                    className="text-xs font-medium px-3 py-1.5 bg-destructive/10 hover:bg-destructive/20 text-destructive rounded-md w-fit transition-colors"
                  >
                    Retry
                  </button>
                </div>
              ) : investigation ? (
                <>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Status</div>
                    <div className="font-medium text-sm text-secondary">
                      {investigation.status}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Created</div>
                    <div className="font-medium text-sm text-secondary flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      {investigation.created_at ? new Date(investigation.created_at).toLocaleString() : "Unknown"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Discrepancy ID</div>
                    <div className="font-mono text-xs text-secondary truncate" title={investigation.discrepancy_id}>
                      {investigation.discrepancy_id}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Active Attempt</div>
                    <div className="font-mono text-xs text-secondary truncate" title={investigation.active_attempt_id || "None"}>
                      {investigation.active_attempt_id ? investigation.active_attempt_id : <span className="text-muted-foreground">None</span>}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>

          {/* Evidence Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <h2 className="text-card-title text-base flex items-center gap-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                Discrepancy Evidence
              </h2>
            </div>
            <div className="p-6 text-center text-sm text-muted-foreground">
              Evidence details will appear here.
            </div>
          </div>
        </div>

        {/* Right Column: AI Investigation and Attempts */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* AI Investigation Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden flex flex-col min-h-[300px]">
            <div className="px-5 py-4 border-b border-border bg-surface-muted/30">
              <h2 className="text-card-title text-base flex items-center gap-2">
                <BrainCircuit className="w-5 h-5 text-primary" />
                AI Investigation Result
              </h2>
            </div>
            <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-full bg-surface-muted flex items-center justify-center mb-4">
                <BrainCircuit className="w-6 h-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-medium text-foreground mb-1">No results available yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm">
                Investigation results, resolution paths, and agent reasoning will be displayed here once an attempt completes.
              </p>
            </div>
          </div>

          {/* Investigation Attempts Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-card-title text-base">Investigation Attempts</h2>
            </div>
            <div className="p-0 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-surface-muted border-b border-border text-secondary">
                  <tr>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Attempt ID</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Model</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Prompt Version</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Validity</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Created At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                    {attemptsLoading && (
                      <tr>
                        <td colSpan={5} className="px-5 py-8 text-center text-secondary text-sm">
                          Loading attempts...
                        </td>
                      </tr>
                    )}
                    {attemptsError && (
                      <tr>
                        <td colSpan={5} className="px-5 py-8 text-center text-destructive text-sm">
                          <div className="flex flex-col items-center gap-2">
                            <span>{attemptsError}</span>
                            <button onClick={loadAttempts} className="text-xs font-medium px-3 py-1.5 bg-destructive/10 hover:bg-destructive/20 text-destructive rounded-md transition-colors">
                              Retry
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                    {!attemptsLoading && !attemptsError && attempts && attempts.length > 0 && attempts.map((attempt) => (
                      <tr key={attempt.id} className="border-t border-border">
                        <td className="px-5 py-3 text-sm font-medium text-foreground">{attempt.id}</td>
                        <td className="px-5 py-3 text-sm text-foreground">{attempt.model_used ?? "-"}</td>
                        <td className="px-5 py-3 text-sm text-foreground">{attempt.prompt_version ?? "-"}</td>
                        <td className="px-5 py-3 text-sm text-foreground">
                          {attempt.is_valid ? (
                            <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 border-emerald-500/20">Valid</span>
                          ) : (
                            <span className="inline-flex items-center rounded-full bg-rose-500/10 px-2.5 py-0.5 text-xs font-medium text-rose-600 border-rose-500/20">Invalid</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-sm text-right text-foreground">
                          {attempt.created_at ? new Date(attempt.created_at).toLocaleString() : "-"}
                        </td>
                      </tr>
                    ))}
                    {!attemptsLoading && !attemptsError && attempts && attempts.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground text-sm">
                          No attempts found.
                        </td>
                      </tr>
                    )}
                </tbody>
              </table>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
