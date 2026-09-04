"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  fetchPeriod,
  evaluatePeriodClose,
  closePeriod,
  PeriodDetailResponse,
  PeriodReadiness,
  ControlDetail,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, ArrowLeft, CheckCircle2, Lock, Play, RefreshCw, XCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import Link from "next/link";
import { format } from "date-fns";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";
import { Progress } from "@/components/ui/progress";

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "OPEN":
      return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">OPEN</Badge>;
    case "CLOSING":
      return <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">CLOSING</Badge>;
    case "CLOSED":
      return <Badge className="bg-slate-100 text-slate-800 hover:bg-slate-100">CLOSED</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function ControlBadge({ status }: { status: string }) {
  switch (status) {
    case "READY":
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 gap-1">
          <CheckCircle2 className="h-3 w-3" /> READY
        </Badge>
      );
    case "BLOCKED":
      return (
        <Badge className="bg-red-100 text-red-800 hover:bg-red-100 gap-1">
          <XCircle className="h-3 w-3" /> BLOCKED
        </Badge>
      );
    case "NOT_EVALUATED":
      return <Badge variant="outline">NOT EVALUATED</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function ControlRow({ title, control }: { title: string; control: ControlDetail }) {
  return (
    <div className="flex items-center justify-between p-4 border rounded-md">
      <div>
        <div className="font-medium">{title}</div>
        <div className="text-sm text-muted-foreground">
          {control.status === "BLOCKED" && control.blocking_count > 0 ? (
            <span className="text-red-600 font-medium">{control.blocking_count} blocking items</span>
          ) : (
            control.message || (control.status === "READY" ? "All clear" : "Pending evaluation")
          )}
        </div>
      </div>
      <ControlBadge status={control.status} />
    </div>
  );
}

export default function PeriodDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();
  const { user } = useAuth();

  const [data, setData] = useState<PeriodDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canEvaluate = hasPermission(user, PERMISSIONS.EVALUATE_PERIOD_CLOSE);
  const canApprove = hasPermission(user, PERMISSIONS.APPROVE_PERIOD_CLOSE); // Used to gate the actual close action
  const canClose = hasPermission(user, PERMISSIONS.CLOSE_PERIOD);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchPeriod(id);
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load period");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const handleEvaluate = async () => {
    if (!canEvaluate) return;
    try {
      setEvaluating(true);
      setError(null);
      const readiness = await evaluatePeriodClose(id);
      setData((prev) => prev ? { ...prev, readiness } : null);
    } catch (err: any) {
      setError(err.message || "Failed to evaluate readiness");
    } finally {
      setEvaluating(false);
    }
  };

  const handleClose = async () => {
    if (!canClose) return;
    if (!confirm("Are you sure you want to close this period? This action is irreversible.")) return;
    
    try {
      setClosing(true);
      setError(null);
      const res = await closePeriod(id);
      setData((prev) => (prev ? { ...prev, period: res } : null));
    } catch (err: any) {
      setError(err.message || "Failed to close period");
    } finally {
      setClosing(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-1/3 bg-muted rounded"></div>
        <div className="h-64 bg-muted rounded"></div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const { period, metrics, readiness } = data;
  const isClosed = period.status === "CLOSED";

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="flex items-center gap-4">
        <Link href="/periods">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{period.period_name}</h1>
          <p className="text-muted-foreground font-mono text-sm">
            ID: {period.id}
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          {!isClosed && canEvaluate && (
            <Button variant="outline" onClick={handleEvaluate} disabled={evaluating || closing}>
              {evaluating ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Evaluate Readiness
            </Button>
          )}
          {!isClosed && canClose && (
            <Button
              onClick={handleClose}
              disabled={closing || evaluating || !readiness?.is_ready}
              className={readiness?.is_ready ? "bg-green-600 hover:bg-green-700" : ""}
            >
              {closing ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Lock className="mr-2 h-4 w-4" />
              )}
              Close Period
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle>Period Details</CardTitle>
                <CardDescription>Boundary and status</CardDescription>
              </div>
              <StatusBadge status={period.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-1">Start Date</div>
                <div>{format(new Date(period.start_date), "PPpp")}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-1">End Date</div>
                <div>{format(new Date(period.end_date), "PPpp")}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-1">Created At</div>
                <div>{format(new Date(period.created_at), "PPpp")}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-1">Updated At</div>
                <div>{format(new Date(period.updated_at), "PPpp")}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Volume Metrics</CardTitle>
            <CardDescription>Transactions within this period</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center border-b pb-2">
              <span className="text-sm font-medium text-muted-foreground">Payments</span>
              <span className="font-semibold">{metrics.total_payments}</span>
            </div>
            <div className="flex justify-between items-center border-b pb-2">
              <span className="text-sm font-medium text-muted-foreground">Settlements</span>
              <span className="font-semibold">{metrics.total_settlements}</span>
            </div>
            <div className="flex justify-between items-center border-b pb-2">
              <span className="text-sm font-medium text-muted-foreground">Refunds</span>
              <span className="font-semibold">{metrics.total_refunds}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-muted-foreground">Fees</span>
              <span className="font-semibold">{metrics.total_fees}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Close Readiness Controls</CardTitle>
              <CardDescription>
                Deterministic evaluation of outstanding operational states.
              </CardDescription>
            </div>
            {readiness && (
              <Badge variant={readiness.is_ready ? "default" : "error"} className="text-sm px-3 py-1">
                {readiness.is_ready ? "READY TO CLOSE" : "BLOCKED"}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!readiness ? (
            <div className="text-center py-12 text-muted-foreground bg-muted/30 rounded-md border border-dashed">
              <Play className="h-10 w-10 mx-auto mb-4 opacity-50" />
              <p>Controls have not been evaluated recently.</p>
              {canEvaluate && (
                <Button variant="link" onClick={handleEvaluate}>
                  Evaluate now
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <ControlRow title="Unreconciled Transactions" control={readiness.controls.unreconciled_transactions} />
              <ControlRow title="Unresolved Exceptions" control={readiness.controls.unresolved_exceptions} />
              <ControlRow title="Pending Investigations" control={readiness.controls.pending_investigations} />
              <ControlRow title="Pending Action Requests" control={readiness.controls.pending_action_requests} />
              <ControlRow title="Running Action Executions" control={readiness.controls.running_executions} />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
