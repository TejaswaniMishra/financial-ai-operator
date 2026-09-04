"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchException, ExceptionDetail, runInvestigation, approveActionRequest, rejectActionRequest, executeActionRequest } from "../../../lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "../../../lib/utils";
import { CheckCircle2, AlertCircle, Loader2, ArrowRight } from "lucide-react";

const STATE_COLORS: Record<string, string> = {
  OPEN: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  INVESTIGATING: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  AWAITING_APPROVAL: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  APPROVED: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  EXECUTING: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  RESOLVED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  FAILED: "bg-red-500/15 text-red-300 border-red-500/30",
  UNKNOWN: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

export default function ExceptionDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [data, setData] = useState<ExceptionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    load();
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
    try {
      setActionLoading(true);
      await runInvestigation(id);
      await load();
    } catch(err: any) {
      alert("Failed to investigate: " + err.message);
    } finally {
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

  if (loading) return <div className="p-6 text-slate-400">Loading...</div>;
  if (error) return <div className="p-6 text-red-400">{error}</div>;
  if (!data) return null;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      
      {/* HEADER */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-3">
            Exception {data.id.split("-")[0]}
            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border", STATE_COLORS[data.overall_state] || STATE_COLORS.OPEN)}>
              {data.overall_state.replace("_", " ")}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1 flex items-center gap-2">
            {data.type.replace("_", " ")} ?· Detected {new Date(data.detected_at).toLocaleString()}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* FINANCIAL CONTEXT */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-lg">Financial Context</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-400 text-xs">Difference Amount</p>
                <p className={cn("font-medium text-lg", (data.difference_amount ?? 0) > 0 ? "text-amber-400" : "text-emerald-400")}>
                  {(data.difference_amount ?? 0) > 0 ? "+" : ""}{data.difference_amount} {data.currency}
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Reconciliation Rule</p>
                <p className="text-slate-200 font-mono text-xs mt-1">{data.rule_code}</p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Source Entity</p>
                <Link href={`/transactions/${data.source_entity_id}`} className="text-blue-400 hover:text-blue-300 font-mono text-xs mt-1 block">
                  {data.source_entity_type}: {data.source_entity_id.split("-")[0]}
                </Link>
              </div>
              {data.related_entity_id && (
                <div>
                  <p className="text-slate-400 text-xs">Related Entity</p>
                  <Link href={`/transactions/${data.related_entity_id}`} className="text-blue-400 hover:text-blue-300 font-mono text-xs mt-1 block">
                    {data.related_entity_type}: {data.related_entity_id.split("-")[0]}
                  </Link>
                </div>
              )}
            </div>
            
            <div className="flex gap-4 pt-4 border-t border-slate-800">
              <div className="flex-1">
                <p className="text-slate-400 text-xs mb-1">Expected</p>
                <p className="text-slate-300 font-mono">{data.expected_amount ?? "N/A"}</p>
              </div>
              <div className="flex-1">
                <p className="text-slate-400 text-xs mb-1">Actual</p>
                <p className="text-slate-300 font-mono">{data.actual_amount ?? "N/A"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* INVESTIGATION */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-lg">AI Investigation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!data.investigation_status ? (
              <div className="text-center py-6">
                <p className="text-slate-400 mb-4">No investigation has been run yet.</p>
                <button
                  onClick={handleInvestigate}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
                >
                  {actionLoading ? "Starting..." : "Run AI Investigation"}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Status</span>
                  <span className={cn("px-2 py-0.5 rounded text-xs font-medium border", data.investigation_status === "COMPLETED" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : "bg-blue-500/15 text-blue-400 border-blue-500/30")}>
                    {data.investigation_status}
                  </span>
                </div>
                
                {data.root_cause && (
                  <div>
                    <span className="text-slate-400 block mb-1">Root Cause</span>
                    <span className="text-slate-200 font-medium">{data.root_cause.replace(/_/g, " ")}</span>
                  </div>
                )}
                
                {data.investigation_explanation && (
                  <div>
                    <span className="text-slate-400 block mb-1">Explanation</span>
                    <p className="text-slate-300 text-xs leading-relaxed">{data.investigation_explanation}</p>
                  </div>
                )}
                
                {data.investigation_status === "FAILED" && (
                  <button
                    onClick={handleInvestigate}
                    disabled={actionLoading}
                    className="mt-4 w-full px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
                  >
                    Retry Investigation
                  </button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* POLICY & ACTION */}
      {data.policy_decision && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-lg">Resolution Action</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* POLICY */}
              <div className="space-y-2">
                <h3 className="text-slate-400 text-xs uppercase font-semibold">Policy Engine</h3>
                <div className="bg-slate-800/50 rounded p-3 border border-slate-800">
                  <p className="text-sm font-medium text-slate-200">{data.policy_decision}</p>
                  <p className="text-xs text-slate-400 mt-1">{data.policy_reason}</p>
                  <p className="text-xs text-slate-500 font-mono mt-2">{data.policy_rule_code}</p>
                </div>
              </div>

              {/* ACTION REQUEST */}
              <div className="space-y-2">
                <h3 className="text-slate-400 text-xs uppercase font-semibold">Action Request</h3>
                <div className="bg-slate-800/50 rounded p-3 border border-slate-800 h-full">
                  {data.action_request_status ? (
                    <>
                      <p className="text-sm font-medium text-slate-200">{data.action_request_action}</p>
                      <p className="text-xs text-slate-400 mt-1">Status: {data.action_request_status}</p>
                      
                      {data.action_request_status === "PENDING_APPROVAL" && (
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={() => handleApprove(data.action_request_id!)}
                            disabled={actionLoading}
                            className="flex-1 px-2 py-1.5 rounded bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 text-xs border border-emerald-500/30"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(data.action_request_id!)}
                            disabled={actionLoading}
                            className="flex-1 px-2 py-1.5 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30 text-xs border border-red-500/30"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No action requested</p>
                  )}
                </div>
              </div>

              {/* EXECUTION */}
              <div className="space-y-2">
                <h3 className="text-slate-400 text-xs uppercase font-semibold">Execution</h3>
                <div className="bg-slate-800/50 rounded p-3 border border-slate-800 h-full">
                  {data.execution_status ? (
                    <>
                      <div className="flex items-center gap-2">
                        {data.execution_status === "SUCCEEDED" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                        {data.execution_status === "FAILED" && <AlertCircle className="w-4 h-4 text-red-400" />}
                        {data.execution_status === "RUNNING" && <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />}
                        <p className="text-sm font-medium text-slate-200">{data.execution_status}</p>
                      </div>
                      {data.execution_error && (
                        <p className="text-xs text-red-400 mt-1">{data.execution_error}</p>
                      )}
                    </>
                  ) : data.action_request_status === "APPROVED" ? (
                    <button
                      onClick={() => handleExecute(data.action_request_id!)}
                      disabled={actionLoading}
                      className="w-full px-2 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs"
                    >
                      Execute Now
                    </button>
                  ) : (
                    <p className="text-xs text-slate-500 italic">Pending approval</p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* LINEAGE */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4 flex justify-between items-center">
          <div>
            <h3 className="text-slate-200 font-medium">Financial Lineage</h3>
            <p className="text-xs text-slate-400 mt-1">View the full deterministic flow of related transactions.</p>
          </div>
          <Link
            href={`/transactions/${data.source_entity_id}`}
            className="flex items-center gap-2 px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm border border-slate-700"
          >
            View Lineage <ArrowRight className="w-4 h-4" />
          </Link>
        </CardContent>
      </Card>
      
    </div>
  );
}
