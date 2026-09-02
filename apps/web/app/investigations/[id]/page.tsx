
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
import {
  fetchInvestigation,
  InvestigationResponse,
  fetchInvestigationAttempts,
  InvestigationAttempt,
  fetchInvestigationAttemptResult,
  InvestigationAttemptResultResponse,
  approveInvestigation,
  InvestigationApprovalResponse
} from "../../../lib/api";

export default function InvestigationDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Attempts state
  const [attempts, setAttempts] = useState<InvestigationAttempt[] | null>(null);
  const [attemptsLoading, setAttemptsLoading] = useState<boolean>(false);
  const [attemptsError, setAttemptsError] = useState<string | null>(null);

  // Result state
  const [attemptResult, setAttemptResult] = useState<InvestigationAttemptResultResponse | null>(null);
  const [resultLoading, setResultLoading] = useState<boolean>(false);
  const [resultError, setResultError] = useState<string | null>(null);

  // Approval state
  const [approving, setApproving] = useState<boolean>(false);
  const [approvalResult, setApprovalResult] = useState<InvestigationApprovalResponse | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);

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

  const loadAttemptResult = async (invId: string, attId: string) => {
    setResultLoading(true);
    setResultError(null);
    try {
      const data = await fetchInvestigationAttemptResult(invId, attId);
      setAttemptResult(data);
    } catch (err: any) {
      setResultError(err.message || "Failed to load investigation result");
    } finally {
      setResultLoading(false);
    }
  };

  useEffect(() => {
    if (investigation?.active_attempt_id && attempts && attempts.length > 0) {
      const activeAttemptExists = attempts.some(a => a.id === investigation.active_attempt_id);
      if (activeAttemptExists) {
        loadAttemptResult(investigation.id, investigation.active_attempt_id);
      }
    }
  }, [investigation?.active_attempt_id, attempts, investigation?.id]);

  const handleApprove = async () => {
    if (!investigation || investigation.status !== "COMPLETED") return;
    setApproving(true);
    setApprovalError(null);
    try {
      const data = await approveInvestigation(investigation.id);
      setApprovalResult(data);
      loadInvestigation(); // refresh to get the updated status
    } catch (err: any) {
      setApprovalError(err.message || "Failed to approve investigation.");
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center text-sm text-muted-foreground font-medium mb-2">
        <Link href="/" className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <Link href="/investigations" className="hover:text-foreground transition-colors">
          Investigations
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="text-foreground">Investigation Detail</span>
      </nav>

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link 
              href="/investigations" 
              className="p-1 -ml-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-surface-muted focus-ring"
              aria-label="Back to Investigations"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Investigation
            </h1>
            {investigation ? (
              <span className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
                investigation.status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" :
                investigation.status === "FAILED" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20" :
                investigation.status === "PENDING" ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20" :
                investigation.status === "UNAVAILABLE" ? "bg-surface-muted text-muted-foreground border-border" :
                "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20"
              )}>
                {investigation.status}
              </span>
            ) : loading ? (
              <div className="h-5 w-20 bg-surface-muted rounded animate-pulse" />
            ) : null}
          </div>
          <div className="flex items-center text-sm text-muted-foreground font-mono mt-1 ml-9">
            {id}
          </div>
        </div>
        
        <div className="flex flex-col items-end gap-2">
          {/* Approval Action Area */}
          <div className="flex items-center gap-3">
            {!approvalResult && (
              <button
                disabled={!investigation || investigation.status !== "COMPLETED" || approving}
                onClick={handleApprove}
                className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {approving ? (
                  <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <ShieldCheck className="w-4 h-4 mr-2" />
                )}
                {approving ? "Approving..." : "Approve Investigation"}
              </button>
            )}
          </div>

          {!approvalResult && (
            <div className="text-xs text-muted-foreground max-w-[280px] text-right mt-1">
              {investigation?.status !== "COMPLETED" 
                ? "Approval is unavailable until the investigation is completed." 
                : "Approval queues the AI's recommended action for Policy Engine evaluation. No direct financial changes are executed."}
            </div>
          )}

          {approvalError && (
            <div className="text-xs font-medium text-destructive max-w-xs text-right flex items-center gap-1.5 justify-end bg-destructive/10 px-3 py-2 rounded-md border border-destructive/20">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>{approvalError}</span>
            </div>
          )}

          {approvalResult && (
            <div className="flex flex-col items-end bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 rounded-md text-right max-w-md">
              <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-2 mb-1 justify-end">
                <CheckCircle2 className="w-4 h-4" /> Approval Successful
              </div>
              <div className="text-xs text-emerald-600/90 dark:text-emerald-400/90 font-medium mb-1">
                Action: <span className="font-mono bg-emerald-500/10 px-1 py-0.5 rounded text-emerald-700 dark:text-emerald-300">{approvalResult.action}</span>
              </div>
              <div className="text-xs text-emerald-600/80 dark:text-emerald-400/80">
                {approvalResult.message}
              </div>
            </div>
          )}
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

            {resultLoading ? (
              <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
                <div className="w-12 h-12 rounded-full bg-surface-muted flex items-center justify-center mb-4">
                  <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                </div>
                <h3 className="text-sm font-medium text-foreground mb-1">Loading Result...</h3>
              </div>
            ) : resultError ? (
              <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
                <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
                  <AlertTriangle className="w-6 h-6 text-destructive" />
                </div>
                <h3 className="text-sm font-medium text-foreground mb-1">Failed to load result</h3>
                <p className="text-sm text-muted-foreground mb-4">{resultError}</p>
                <button
                  onClick={() => investigation?.active_attempt_id && loadAttemptResult(investigation.id, investigation.active_attempt_id)}
                  className="text-xs font-medium px-4 py-2 bg-destructive/10 hover:bg-destructive/20 text-destructive rounded-md transition-colors"
                >
                  Retry
                </button>
              </div>
            ) : attemptResult ? (
              attemptResult.is_valid === false ? (
                <div className="flex-1 p-6">
                  <div className="bg-rose-500/10 border border-rose-500/20 rounded-md p-4 mb-4">
                    <h3 className="text-sm font-semibold text-rose-600 dark:text-rose-400 flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4" /> Validation Failed
                    </h3>
                    <p className="text-sm text-rose-600/80 dark:text-rose-400/80">The AI response did not pass schema validation.</p>
                  </div>
                  {attemptResult.errors != null && (
                    <div className="mt-4">
                      <h4 className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Validation Errors</h4>
                      <pre className="text-xs bg-surface-muted p-3 rounded-md overflow-x-auto text-foreground whitespace-pre-wrap">
                        {JSON.stringify(attemptResult.errors, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ) : attemptResult.result ? (
                <div className="flex-1 p-0 divide-y divide-border">
                  {(() => {
                    const res = attemptResult.result;
                    if (!res) return null;
                    return (
                      <>
                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-surface-muted/10">
                          {res.root_cause_category && (
                            <div>
                              <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Root Cause Category</div>
                              <div className="font-medium text-sm text-foreground">{res.root_cause_category}</div>
                            </div>
                          )}
                          {res.ai_confidence !== undefined && (
                            <div>
                              <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Confidence</div>
                              <div className="flex items-center gap-2">
                                <div className="w-full bg-border rounded-full h-2 max-w-[150px]">
                                  <div
                                    className="bg-primary h-2 rounded-full"
                                    style={{ width: `${Math.min(Math.max(res.ai_confidence * 100, 0), 100)}%` }}
                                  ></div>
                                </div>
                                <span className="font-mono text-sm text-secondary">
                                  {Math.round(res.ai_confidence * 100)}%
                                </span>
                              </div>
                            </div>
                          )}
                        </div>

                        {res.summary && (
                          <div className="p-6">
                            <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider font-semibold">Summary</div>
                            <p className="text-sm text-foreground leading-relaxed">{res.summary}</p>
                          </div>
                        )}

                        {res.claims && Array.isArray(res.claims) && res.claims.length > 0 && (
                          <div className="p-6">
                            <div className="text-xs text-muted-foreground mb-3 uppercase tracking-wider font-semibold flex items-center gap-2">
                              <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                              Evidence Claims
                            </div>
                            <div className="space-y-4">
                              {res.claims.map((claim, idx) => (
                                <div key={idx} className="bg-surface-muted/50 rounded-md p-4 border border-border/50">
                                  <div className="text-sm font-medium text-foreground mb-2">{claim.claim}</div>
                                  {claim.evidence && Array.isArray(claim.evidence) && (
                                    <div className="flex flex-wrap gap-2 mt-3">
                                      {claim.evidence.map((ev, evIdx) => (
                                        <span key={evIdx} className="inline-flex items-center px-2 py-1 rounded bg-background border border-border text-xs text-muted-foreground font-mono">
                                          {ev.field}: <span className="text-foreground ml-1 font-medium">{String(ev.value)}</span>
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {res.recommendations && Array.isArray(res.recommendations) && res.recommendations.length > 0 && (
                          <div className="p-6">
                            <div className="text-xs text-muted-foreground mb-3 uppercase tracking-wider font-semibold flex items-center gap-2">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                              Recommended Actions
                            </div>
                            <ul className="space-y-2">
                              {res.recommendations.map((rec, idx) => (
                                <li key={idx} className="flex gap-3 text-sm text-foreground items-start">
                                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary/60 shrink-0"></div>
                                  <span className="leading-relaxed">{rec}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              ) : (
                <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
                  <div className="w-12 h-12 rounded-full bg-surface-muted flex items-center justify-center mb-4">
                    <FileText className="w-6 h-6 text-muted-foreground" />
                  </div>
                  <h3 className="text-sm font-medium text-foreground mb-1">Result Empty</h3>
                  <p className="text-sm text-muted-foreground max-w-sm">
                    The valid result contains no data.
                  </p>
                </div>
              )
            ) : (
              <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
                <div className="w-12 h-12 rounded-full bg-surface-muted flex items-center justify-center mb-4">
                  <BrainCircuit className="w-6 h-6 text-muted-foreground" />
                </div>
                <h3 className="text-sm font-medium text-foreground mb-1">No results available yet</h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                  Investigation results, resolution paths, and agent reasoning will be displayed here once an attempt completes.
                </p>
              </div>
            )}
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
                    {!attemptsLoading && !attemptsError && attempts && attempts.length > 0 && attempts.map((attempt) => {
                      const isActive = attempt.id === investigation?.active_attempt_id;
                      return (
                      <tr key={attempt.id} className={cn("transition-colors group", isActive ? "bg-primary/5" : "hover:bg-surface-muted/50")}>
                        <td className="px-5 py-3 text-sm font-medium text-foreground">
                          {attempt.id}
                          {isActive && <span className="ml-2 inline-flex items-center rounded-full bg-primary/20 px-1.5 py-0.5 text-[10px] font-bold text-primary uppercase tracking-wider">Active</span>}
                        </td>
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
                      );
                    })}
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
