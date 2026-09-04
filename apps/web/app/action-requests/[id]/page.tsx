"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  ArrowLeft, 
  ChevronRight, 
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  XCircle,
  XSquare,
  FileText,
  Activity,
  BrainCircuit
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";
import { 
  fetchActionRequest, 
  approveActionRequest, 
  rejectActionRequest, 
  cancelActionRequest,
  ActionRequestResponse,
  fetchActionExecutions,
  executeActionRequest,
  ActionExecutionResponse
} from "../../../lib/api";

export default function ActionRequestDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  // Authorization state comes from AuthProvider (backend-resolved). These
  // checks are UX only — the backend independently enforces permissions.
  const { user } = useAuth();
  const canApprove = hasPermission(user, PERMISSIONS.APPROVE_ACTION_REQUEST);
  const canReject = hasPermission(user, PERMISSIONS.REJECT_ACTION_REQUEST);
  const canCancel = hasPermission(user, PERMISSIONS.CANCEL_ACTION_REQUEST);
  const canExecute = hasPermission(user, PERMISSIONS.EXECUTE_ACTION);
  const [request, setRequest] = useState<ActionRequestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog state
  const [actionType, setActionType] = useState<"approve" | "reject" | "cancel" | null>(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Execution state
  const [executions, setExecutions] = useState<ActionExecutionResponse[]>([]);
  const [executionsLoading, setExecutionsLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActionRequest(id);
      setRequest(data);
      if (data.status !== "PENDING_APPROVAL") {
        await loadExecutions();
      }
    } catch (err: any) {
      setError(err.message || "Failed to load action request");
    } finally {
      setLoading(false);
    }
  };

  const loadExecutions = async () => {
    setExecutionsLoading(true);
    try {
      const data = await fetchActionExecutions(id);
      setExecutions(data);
    } catch (err: any) {
      console.error("Failed to load executions:", err);
    } finally {
      setExecutionsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleSubmit = async () => {
    if (!actionType || !request) return;
    
    if (actionType !== "approve" && !reason.trim()) {
      setSubmitError("Reason is required.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      if (actionType === "approve") {
        await approveActionRequest(request.id);
        setSubmitSuccess("Action request approved successfully.");
      } else if (actionType === "reject") {
        await rejectActionRequest(request.id, reason);
        setSubmitSuccess("Action request rejected successfully.");
      } else if (actionType === "cancel") {
        await cancelActionRequest(request.id, reason);
        setSubmitSuccess("Action request cancelled successfully.");
      }
      
      setActionType(null);
      setReason("");
      loadData();
    } catch (err: any) {
      setSubmitError(err.message || `Failed to ${actionType} request`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleExecute = async () => {
    if (!request) return;
    setExecuting(true);
    setExecutionError(null);
    try {
      await executeActionRequest(request.id);
      await loadExecutions();
    } catch (err: any) {
      setExecutionError(err.message || "Failed to execute action.");
    } finally {
      setExecuting(false);
    }
  };

  const openDialog = (type: "approve" | "reject" | "cancel") => {
    setActionType(type);
    setReason("");
    setSubmitError(null);
    setSubmitSuccess(null);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center text-sm text-muted-foreground font-medium mb-2">
        <Link href="/" className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <Link href="/action-requests" className="hover:text-foreground transition-colors">
          Action Requests
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="text-foreground">Review Request</span>
      </nav>

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link 
              href="/action-requests" 
              className="p-1 -ml-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-surface-muted focus-ring"
              aria-label="Back to Action Requests"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Action Request
            </h1>
            {request ? (
              <span className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
                request.status === "APPROVED" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" :
                request.status === "REJECTED" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20" :
                request.status === "PENDING_APPROVAL" ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20" :
                "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20"
              )}>
                {request.status.replace("_", " ")}
              </span>
            ) : loading ? (
              <div className="h-5 w-20 bg-surface-muted rounded animate-pulse" />
            ) : null}
          </div>
          <div className="flex items-center text-sm text-muted-foreground font-mono mt-1 ml-9">
            {id}
          </div>
        </div>
        
        {submitSuccess && (
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-md text-emerald-600 dark:text-emerald-400 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" />
            {submitSuccess}
          </div>
        )}
        
        {request?.status === "APPROVED" && (
          <div className="flex items-center gap-3">
            {canExecute ? (
              <button
                onClick={handleExecute}
                disabled={executing}
                className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm disabled:opacity-50"
              >
                {executing ? (
                  <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <BrainCircuit className="w-4 h-4 mr-2" />
                )}
                {executing ? "Executing..." : "Execute Action"}
              </button>
            ) : (
              <div className="flex items-center gap-2 text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2 rounded-md">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                You do not have permission to execute this action.
              </div>
            )}
          </div>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-pulse">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-surface-muted h-64 rounded-xl w-full"></div>
            <div className="bg-surface-muted h-48 rounded-xl w-full"></div>
          </div>
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-surface-muted h-80 rounded-xl w-full"></div>
          </div>
        </div>
      ) : error ? (
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
      ) : request ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Details */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
              <div className="px-5 py-4 border-b border-border bg-surface-muted/30 flex items-center justify-between">
                <h2 className="text-card-title text-base flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  Request Details
                </h2>
              </div>
              <div className="p-0 divide-y divide-border">
                <div className="grid grid-cols-1 sm:grid-cols-2 p-5 gap-6">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Action</div>
                    <div className="font-medium text-sm text-foreground bg-surface-muted/50 inline-block px-2 py-1 rounded border border-border/50">
                      {request.action}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Requested Source</div>
                    <div className="font-medium text-sm text-foreground">
                      {request.requested_source || <span className="text-muted-foreground">—</span>}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 p-5 gap-6 bg-surface-muted/10">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Investigation ID</div>
                    <Link 
                      href={`/investigations/${request.investigation_id}`}
                      className="font-mono text-sm text-primary hover:underline"
                    >
                      {request.investigation_id}
                    </Link>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Discrepancy ID</div>
                    {request.discrepancy_id ? (
                      <Link 
                        href={`/discrepancies/${request.discrepancy_id}`}
                        className="font-mono text-sm text-primary hover:underline"
                      >
                        {request.discrepancy_id}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground text-sm font-mono">—</span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 p-5 gap-6">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Policy Evaluation ID</div>
                    <div className="font-mono text-sm text-foreground">
                      {request.policy_evaluation_id}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Decision Status Section (If not pending) */}
            {request.status !== "PENDING_APPROVAL" && (
              <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
                <div className="px-5 py-4 border-b border-border bg-surface-muted/30">
                  <h2 className="text-card-title text-base">Final Decision</h2>
                </div>
                <div className="p-5 space-y-4">
                  {request.status === "APPROVED" && (
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-medium">
                        <CheckCircle2 className="w-5 h-5" />
                        Approved
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground block text-xs mb-1">Approved By</span>
                          <span className="text-foreground font-medium">{request.approved_by || "Unknown"}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block text-xs mb-1">Approved At</span>
                          <span className="text-foreground font-medium flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5" />
                            {request.approved_at ? new Date(request.approved_at).toLocaleString() : "Unknown"}
                          </span>
                        </div>
                      </div>
                      
                      {executionError && (
                        <div className="mt-2 text-sm font-medium text-destructive flex items-center gap-1.5 bg-destructive/10 px-3 py-2 rounded-md border border-destructive/20">
                          <AlertTriangle className="w-4 h-4 shrink-0" />
                          {executionError}
                        </div>
                      )}
                    </div>
                  )}

                  {request.status === "REJECTED" && (
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-medium">
                        <XCircle className="w-5 h-5" />
                        Rejected
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground block text-xs mb-1">Reason</span>
                        <div className="text-foreground bg-surface-muted/50 p-3 rounded border border-border/50">
                          {request.rejection_reason || "No reason provided."}
                        </div>
                      </div>
                    </div>
                  )}

                  {request.status === "CANCELLED" && (
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400 font-medium">
                        <XSquare className="w-5 h-5" />
                        Cancelled
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground block text-xs mb-1">Reason</span>
                        <div className="text-foreground bg-surface-muted/50 p-3 rounded border border-border/50">
                          {request.rejection_reason || "No reason provided."}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Executions Section */}
            {request.status !== "PENDING_APPROVAL" && (
              <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden mt-6">
                <div className="px-5 py-4 border-b border-border bg-surface-muted/30">
                  <h2 className="text-card-title text-base flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    Action Executions
                  </h2>
                </div>
                <div className="p-0 overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-surface-muted border-b border-border text-secondary">
                      <tr>
                        <th className="px-5 py-3 font-medium whitespace-nowrap">ID</th>
                        <th className="px-5 py-3 font-medium whitespace-nowrap">Status</th>
                        <th className="px-5 py-3 font-medium whitespace-nowrap">Adapter</th>
                        <th className="px-5 py-3 font-medium whitespace-nowrap">Result/Error</th>
                        <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Started At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {executionsLoading && executions.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-5 py-8 text-center text-secondary text-sm">
                            Loading executions...
                          </td>
                        </tr>
                      ) : executions.length > 0 ? (
                        executions.map((exec) => (
                          <tr key={exec.id} className="hover:bg-surface-muted/50 transition-colors">
                            <td className="px-5 py-3 font-mono text-xs text-foreground truncate max-w-[120px]" title={exec.id}>
                              {exec.id}
                            </td>
                            <td className="px-5 py-3">
                              <span className={cn(
                                "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border",
                                exec.status === "SUCCEEDED" ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" :
                                exec.status === "FAILED" ? "bg-rose-500/10 text-rose-600 border-rose-500/20" :
                                exec.status === "RUNNING" ? "bg-blue-500/10 text-blue-600 border-blue-500/20" :
                                exec.status === "UNKNOWN" ? "bg-amber-500/10 text-amber-600 border-amber-500/20" :
                                "bg-surface-muted text-secondary border-border"
                              )}>
                                {exec.status}
                              </span>
                            </td>
                            <td className="px-5 py-3 text-secondary text-xs">{exec.adapter}</td>
                            <td className="px-5 py-3 text-xs">
                              {exec.status === "SUCCEEDED" ? (
                                <span className="text-emerald-600 font-medium">Completed successfully</span>
                              ) : exec.status === "FAILED" ? (
                                <div className="text-rose-600 flex flex-col">
                                  <span className="font-semibold">{exec.error_code}</span>
                                  <span className="text-[10px] text-rose-600/80 truncate max-w-[200px]" title={exec.error_message || ""}>
                                    {exec.error_message}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-secondary">—</span>
                              )}
                            </td>
                            <td className="px-5 py-3 text-right text-secondary whitespace-nowrap">
                              {exec.started_at ? new Date(exec.started_at).toLocaleString() : "—"}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-5 py-8 text-center text-muted-foreground text-sm">
                            No executions found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Actions / Lifecycle */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
              <h2 className="text-card-title text-base mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                Lifecycle
              </h2>
              <div className="space-y-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Created</div>
                  <div className="font-medium text-sm text-secondary">
                    {request.created_at ? new Date(request.created_at).toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Last Updated</div>
                  <div className="font-medium text-sm text-secondary">
                    {request.updated_at ? new Date(request.updated_at).toLocaleString() : "—"}
                  </div>
                </div>
              </div>
            </div>

            {request.status === "PENDING_APPROVAL" && (
              <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
                <div className="px-5 py-4 border-b border-border bg-surface-muted/30">
                  <h2 className="text-card-title text-base flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                    Human Decision
                  </h2>
                </div>
                <div className="p-5 space-y-4">
                  <p className="text-xs text-muted-foreground mb-4">
                    Approval records a human decision. Financial execution is handled separately.
                  </p>
                  {!canApprove && !canReject && !canCancel ? (
                    <div className="flex items-center gap-2 text-sm font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2.5 rounded-md">
                      <ShieldCheck className="w-4 h-4 shrink-0" />
                      You do not have permission to make approval decisions.
                    </div>
                  ) : (
                    <>
                      {canApprove && (
                        <button
                          onClick={() => openDialog("approve")}
                          className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm"
                        >
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          Approve Request
                        </button>
                      )}
                      {canReject && (
                        <button
                          onClick={() => openDialog("reject")}
                          className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-rose-600 bg-rose-500/10 hover:bg-rose-500/20 rounded-md transition-colors border border-rose-500/20"
                        >
                          <XCircle className="w-4 h-4 mr-2" />
                          Reject
                        </button>
                      )}
                      {canCancel && (
                        <button
                          onClick={() => openDialog("cancel")}
                          className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-surface-muted rounded-md transition-colors border border-border"
                        >
                          <XSquare className="w-4 h-4 mr-2" />
                          Cancel Request
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Action Dialog */}
      {actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                {actionType === "approve" && "Approve Action Request?"}
                {actionType === "reject" && "Reject Action Request"}
                {actionType === "cancel" && "Cancel Action Request"}
              </h3>
            </div>
            
            <div className="p-6 space-y-4">
              {actionType === "approve" ? (
                <p className="text-sm text-secondary">
                  Approval records your decision. It does not directly execute a financial transaction.
                </p>
              ) : (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground block">
                    Reason <span className="text-destructive">*</span>
                  </label>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={`Enter reason for ${actionType === "reject" ? "rejection" : "cancellation"}...`}
                    className="w-full min-h-[100px] p-3 text-sm bg-surface border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground resize-y"
                  />
                </div>
              )}

              {submitError && (
                <div className="text-sm font-medium text-destructive flex items-center gap-1.5 bg-destructive/10 px-3 py-2 rounded-md border border-destructive/20">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  {submitError}
                </div>
              )}
            </div>

            <div className="px-6 py-4 bg-surface-muted/50 border-t border-border flex items-center justify-end gap-3">
              <button
                onClick={() => setActionType(null)}
                disabled={submitting}
                className="px-4 py-2 text-sm font-medium text-secondary hover:text-foreground hover:bg-surface-muted rounded-md transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className={cn(
                  "inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md transition-colors shadow-sm disabled:opacity-50",
                  actionType === "approve" ? "text-white bg-primary hover:bg-primary/90" :
                  actionType === "reject" ? "text-white bg-rose-600 hover:bg-rose-700" :
                  "text-white bg-slate-600 hover:bg-slate-700"
                )}
              >
                {submitting && (
                  <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
                )}
                {actionType === "approve" && (submitting ? "Approving..." : "Approve Request")}
                {actionType === "reject" && (submitting ? "Rejecting..." : "Reject Request")}
                {actionType === "cancel" && (submitting ? "Cancelling..." : "Cancel Request")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
