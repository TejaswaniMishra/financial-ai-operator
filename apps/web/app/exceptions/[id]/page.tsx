"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchException, ExceptionDetail, runInvestigation, approveActionRequest, rejectActionRequest, executeActionRequest } from "../../../lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "../../../lib/utils";
import { CheckCircle2, AlertCircle, Loader2, ArrowRight } from "lucide-react";

const STATE_TONES: Record<string, "neutral" | "blue" | "amber" | "indigo" | "purple" | "emerald" | "red"> = {
  OPEN: "neutral",
  INVESTIGATING: "blue",
  AWAITING_APPROVAL: "amber",
  APPROVED: "indigo",
  EXECUTING: "purple",
  RESOLVED: "emerald",
  FAILED: "red",
  UNKNOWN: "neutral",
};

export default function ExceptionDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();

  const [data, setData] = useState<ExceptionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState(false);
  // Guards against duplicate requests from rapid repeated clicks before React
  // has committed the disabled state.
  const actionInFlightRef = useRef(false);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchException(id);
      setData(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleInvestigate() {
    if (actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    try {
      setActionLoading(true);
      // Create the investigation through the real backend, then navigate to
      // its detail workspace — never a fake local transition. Navigation only
      // happens after the backend run actually returns.
      const result = await runInvestigation(id);
      if (result && result.investigation_id) {
        router.push(`/investigations/${result.investigation_id}`);
        return;
      }
      await load();
    } catch(err: any) {
      alert("Failed to investigate: " + err.message);
    } finally {
      actionInFlightRef.current = false;
      setActionLoading(false);
    }
  }

  async function handleApprove(reqId: string) {
    try {
      setActionLoading(true);
      await approveActionRequest(reqId);
      await load();
    } catch(err: any) {
      alert("Failed to approve: " + err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject(reqId: string) {
    try {
      setActionLoading(true);
      await rejectActionRequest(reqId, "Rejected by user");
      await load();
    } catch(err: any) {
      alert("Failed to reject: " + err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleExecute(reqId: string) {
    try {
      setActionLoading(true);
      await executeActionRequest(reqId);
      await load();
    } catch(err: any) {
      alert("Failed to execute: " + err.message);
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="p-6 text-muted-foreground">Loading...</div>;
  if (error) return <div className="p-6 text-destructive">{error}</div>;
  if (!data) return null;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">

      {/* HEADER */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-page-title flex items-center gap-3">
            Exception {data.id.split("-")[0]}
            <Badge tone={STATE_TONES[data.overall_state] ?? "neutral"}>
              {data.overall_state.replace("_", " ")}
            </Badge>
          </h1>
          <p className="text-secondary mt-1 flex items-center gap-2">
            {data.type.replace("_", " ")} · Detected {new Date(data.detected_at).toLocaleString()}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* FINANCIAL CONTEXT */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Financial Context</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs">Difference Amount</p>
                {(() => {
                  const diff = data.difference_amount != null ? Number(data.difference_amount) : null;
                  return (
                    <p className={cn("font-medium text-lg", diff !== null && diff > 0 ? "text-amber-700 dark:text-amber-400" : "text-emerald-700 dark:text-emerald-400")}>
                      {diff !== null && diff > 0 ? "+" : ""}{data.difference_amount} {data.currency}
                    </p>
                  );
                })()}
              </div>
              <div>
                <p className="text-muted-foreground text-xs">Reconciliation Rule</p>
                <p className="text-foreground font-mono text-xs mt-1">{data.rule_code}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">Source Entity</p>
                <Link href={`/transactions/${data.source_entity_id}`} className="text-primary hover:text-primary/80 font-mono text-xs mt-1 block">
                  {data.source_entity_type}: {data.source_entity_id.split("-")[0]}
                </Link>
              </div>
              {data.related_entity_id && (
                <div>
                  <p className="text-muted-foreground text-xs">Related Entity</p>
                  <Link href={`/transactions/${data.related_entity_id}`} className="text-primary hover:text-primary/80 font-mono text-xs mt-1 block">
                    {data.related_entity_type}: {data.related_entity_id.split("-")[0]}
                  </Link>
                </div>
              )}
            </div>

            <div className="flex gap-4 pt-4 border-t border-border">
              <div className="flex-1">
                <p className="text-muted-foreground text-xs mb-1">Expected</p>
                <p className="text-foreground font-mono">{data.expected_amount ?? "N/A"}</p>
              </div>
              <div className="flex-1">
                <p className="text-muted-foreground text-xs mb-1">Actual</p>
                <p className="text-foreground font-mono">{data.actual_amount ?? "N/A"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* INVESTIGATION */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">AI Investigation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!data.investigation_status ? (
              <div className="text-center py-6">
                <p className="text-muted-foreground mb-4">No investigation has been run yet.</p>
                <Button
                  onClick={handleInvestigate}
                  disabled={actionLoading}
                >
                  {actionLoading ? "Starting..." : "Run AI Investigation"}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Status</span>
                  <Badge
                    tone={
                      data.investigation_status === "COMPLETED"
                        ? "emerald"
                        : data.investigation_status === "FAILED" || data.investigation_status === "UNAVAILABLE"
                          ? "red"
                          : data.investigation_status === "PENDING"
                            ? "blue"
                            : "neutral"
                    }
                  >
                    {data.investigation_status}
                  </Badge>
                </div>

                {data.root_cause && (
                  <div>
                    <span className="text-muted-foreground block mb-1">Root Cause</span>
                    <span className="text-foreground font-medium">{data.root_cause.replace(/_/g, " ")}</span>
                  </div>
                )}

                {data.investigation_explanation && (
                  <div>
                    <span className="text-muted-foreground block mb-1">Explanation</span>
                    <p className="text-foreground text-xs leading-relaxed">{data.investigation_explanation}</p>
                  </div>
                )}

                {(data.investigation_status === "FAILED" ||
                  data.investigation_status === "UNAVAILABLE") && (
                  <Button
                    onClick={handleInvestigate}
                    disabled={actionLoading}
                    variant="outline"
                    className="mt-4 w-full"
                  >
                    {actionLoading ? "Starting..." : "Retry Investigation"}
                  </Button>
                )}

                {data.investigation_status === "UNAVAILABLE" && (
                  <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                    The AI provider was unavailable when this investigation ran. Retrying starts a new attempt.
                  </p>
                )}

                {data.investigation_id && (
                  <Link
                    href={`/investigations/${data.investigation_id}`}
                    className="mt-3 inline-flex w-full items-center justify-center gap-2 px-4 py-2 rounded-md border border-input bg-background text-foreground text-sm hover:bg-surface transition-colors"
                  >
                    View Investigation Detail
                  </Link>
                )}
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* POLICY & ACTION */}
      {data.policy_decision && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Resolution Action</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* POLICY */}
              <div className="space-y-2">
                <h3 className="text-muted-foreground text-xs uppercase font-semibold">Policy Engine</h3>
                <div className="bg-surface-muted rounded p-3 border border-border">
                  <p className="text-sm font-medium text-foreground">{data.policy_decision}</p>
                  <p className="text-xs text-muted-foreground mt-1">{data.policy_reason}</p>
                  <p className="text-xs text-muted-foreground font-mono mt-2">{data.policy_rule_code}</p>
                </div>
              </div>

              {/* ACTION REQUEST */}
              <div className="space-y-2">
                <h3 className="text-muted-foreground text-xs uppercase font-semibold">Action Request</h3>
                <div className="bg-surface-muted rounded p-3 border border-border h-full">
                  {data.action_request_status ? (
                    <>
                      <p className="text-sm font-medium text-foreground">{data.action_request_action}</p>
                      <p className="text-xs text-muted-foreground mt-1">Status: {data.action_request_status}</p>

                      {data.action_request_status === "PENDING_APPROVAL" && (
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={() => handleApprove(data.action_request_id!)}
                            disabled={actionLoading}
                            className="flex-1 px-2 py-1.5 rounded bg-emerald-600/15 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-600/25 text-xs border border-emerald-500/30 transition-colors"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(data.action_request_id!)}
                            disabled={actionLoading}
                            className="flex-1 px-2 py-1.5 rounded bg-red-600/15 text-red-700 dark:text-red-300 hover:bg-red-600/25 text-xs border border-red-500/30 transition-colors"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No action requested</p>
                  )}
                </div>
              </div>

              {/* EXECUTION */}
              <div className="space-y-2">
                <h3 className="text-muted-foreground text-xs uppercase font-semibold">Execution</h3>
                <div className="bg-surface-muted rounded p-3 border border-border h-full">
                  {data.execution_status ? (
                    <>
                      <div className="flex items-center gap-2">
                        {data.execution_status === "SUCCEEDED" && <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
                        {data.execution_status === "FAILED" && <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />}
                        {data.execution_status === "RUNNING" && <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />}
                        <p className="text-sm font-medium text-foreground">{data.execution_status}</p>
                      </div>
                      {data.execution_error && (
                        <p className="text-xs text-red-700 dark:text-red-400 mt-1">{data.execution_error}</p>
                      )}
                    </>
                  ) : data.action_request_status === "APPROVED" ? (
                    <Button
                      onClick={() => handleExecute(data.action_request_id!)}
                      disabled={actionLoading}
                      size="sm"
                      className="w-full"
                    >
                      Execute Now
                    </Button>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">Pending approval</p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* LINEAGE */}
      <Card>
        <CardContent className="p-4 flex justify-between items-center">
          <div>
            <h3 className="text-foreground font-medium">Financial Lineage</h3>
            <p className="text-xs text-muted-foreground mt-1">View the full deterministic flow of related transactions.</p>
          </div>
          <Link
            href={`/transactions/${data.source_entity_id}`}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-input bg-background text-foreground text-sm hover:bg-surface transition-colors"
          >
            View Lineage <ArrowRight className="w-4 h-4" />
          </Link>
        </CardContent>
      </Card>

    </div>
  );
}