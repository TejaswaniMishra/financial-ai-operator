"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  fetchTransactionDetail,
  fetchTransactionLineage,
  TransactionDetail,
  TransactionLineageResponse,
  LineageNode,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TYPE_TONES: Record<string, "blue" | "amber" | "violet" | "emerald" | "cyan" | "neutral"> = {
  PAYMENT: "blue",
  REFUND: "amber",
  FEE: "violet",
  SETTLEMENT: "emerald",
  BANK_TRANSACTION: "cyan",
};

function StatusPill({ status }: { status: string }) {
  const tone: "red" | "amber" | "emerald" = /FAILED|REJECTED|DENIED|UNRESOLVED/i.test(status)
    ? "red"
    : /PENDING|RUNNING|UNKNOWN/i.test(status)
      ? "amber"
      : "emerald";
  return <Badge tone={tone}>{status}</Badge>;
}

function formatAmount(amount: string | null, currency: string | null) {
  if (amount === null || amount === undefined) return "—";
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(n);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <div className="text-sm text-foreground mt-0.5">{children}</div>
    </div>
  );
}

function LineageNodeRow({ node }: { node: LineageNode }) {
  const isSource = node.role === "SOURCE";
  return (
    <div className="relative flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "w-3 h-3 rounded-full mt-1.5 ring-4",
            isSource
              ? "bg-blue-500 ring-blue-500/20 dark:ring-blue-400/20"
              : "bg-amber-500 ring-amber-500/20 dark:ring-amber-400/20"
          )}
        />
        <div className="w-px flex-1 bg-border" />
      </div>
      <div className="pb-5 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TYPE_TONES[node.kind] ?? "neutral"}>
            {node.kind.replace("_", " ")}
          </Badge>
          <Badge tone={isSource ? "blue" : "amber"}>
            {node.role}
          </Badge>
          {node.status && <StatusPill status={node.status} />}
        </div>
        <p className="text-sm text-foreground mt-1.5 font-mono text-xs">{node.label}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {node.amount !== null && node.amount !== undefined && (
            <span className="text-foreground font-medium">
              {formatAmount(node.amount, node.currency)} ·{" "}
            </span>
          )}
          {node.timestamp ? new Date(node.timestamp).toLocaleString() : ""}
        </p>
        {node.detail && Object.keys(node.detail).length > 0 && (
          <details className="text-xs text-muted-foreground mt-1">
            <summary className="cursor-pointer text-primary hover:text-primary/80">
              Details
            </summary>
            <pre className="mt-1 p-2 bg-surface-muted rounded border border-border whitespace-pre-wrap break-all text-foreground">
              {JSON.stringify(node.detail, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

export default function TransactionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [lineage, setLineage] = useState<TransactionLineageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [d, l] = await Promise.all([
        fetchTransactionDetail(id),
        fetchTransactionLineage(id),
      ]);
      setDetail(d);
      setLineage(l);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transaction.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-muted-foreground text-sm">
            Loading transaction…
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-destructive text-sm">{error}</p>
            <Button onClick={load} variant="outline" size="sm">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!detail) return null;

  const discrepancy = detail.discrepancies[0];
  const hasException = detail.discrepancies.length > 0;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Badge tone={TYPE_TONES[detail.record_type] ?? "neutral"}>
              {detail.record_type.replace("_", " ")}
            </Badge>
            <StatusPill status={detail.status} />
          </div>
          <h1 className="text-page-title mt-2 font-mono">
            {detail.id}
          </h1>
          <p className="text-secondary mt-1">
            {detail.external_id && <>External: {detail.external_id} · </>}
            {new Date(detail.created_at).toLocaleString()}
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-foreground">
            {formatAmount(detail.amount, detail.currency)}
          </p>
          <p className="text-sm text-muted-foreground">{detail.currency}</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5 space-y-3">
            <Field label="Merchant">{detail.merchant.name}</Field>
            <Field label="Provider">
              {detail.provider || "—"}
            </Field>
            {detail.order && (
              <Field label="Order">
                <Link href={`/transactions/${detail.order.id}`} className="text-primary hover:text-primary/80 font-mono">
                  {detail.order.id}
                </Link>
                <span className="text-muted-foreground text-xs block mt-0.5">
                  {detail.order.status} · {formatAmount(detail.order.amount, detail.order.currency)}
                </span>
              </Field>
            )}
            {detail.customer && (
              <Field label="Customer">{detail.customer.display_name}</Field>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Reconciliation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.reconciliation.length === 0 ? (
              <p className="text-sm text-muted-foreground">No reconciliation relationship established.</p>
            ) : (
              detail.reconciliation.map((rel) => (
                <div key={rel.relationship_id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <StatusPill status={rel.relationship_status} />
                    <span className="text-xs text-muted-foreground">
                      {rel.relationship_type.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Financial: {rel.financial_status} · Run: {rel.run_status}
                  </p>
                  <p className="text-xs text-muted-foreground font-mono">
                    {rel.source_entity_type} {rel.source_entity_id.slice(0, 8)} →{" "}
                    {rel.target_entity_type} {rel.target_entity_id.slice(0, 8)}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Exception state</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!hasException ? (
              <p className="text-sm text-muted-foreground">No discrepancies for this record.</p>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <StatusPill status={discrepancy.severity} />
                  <span className="text-xs text-muted-foreground">
                    {discrepancy.discrepancy_type.replace("_", " ")}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Rule {discrepancy.rule_code} · diff{" "}
                  {formatAmount(discrepancy.difference_amount, discrepancy.currency)}
                </p>
                {detail.investigation && (
                  <p className="text-xs text-muted-foreground">
                    Investigation:{" "}
                    <Link
                      href={`/investigations/${detail.investigation.id}`}
                      className="text-primary hover:text-primary/80"
                    >
                      {detail.investigation.status}
                    </Link>
                  </p>
                )}
              </>
            )}
            {detail.action_requests.length > 0 && (
              <div className="pt-2 border-t border-border">
                <p className="text-xs text-muted-foreground mb-1">Action requests</p>
                {detail.action_requests.map((ar) => (
                  <div key={ar.id} className="flex items-center gap-2">
                    <StatusPill status={ar.status} />
                    <span className="text-xs text-muted-foreground">{ar.action.replace("_", " ")}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Financial details / related records */}
      {detail.related.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Financial details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-border overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-muted-foreground bg-surface-muted uppercase border-b border-border">
                  <tr>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {detail.related.map((r) => (
                    <tr key={`${r.record_type}-${r.id}`} className="hover:bg-surface-muted/50 transition-colors">
                      <td className="px-4 py-3">
                        <Badge tone={TYPE_TONES[r.record_type] ?? "neutral"}>
                          {r.record_type.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/transactions/${r.id}`}
                          className="text-primary hover:text-primary/80 font-mono text-xs"
                        >
                          {r.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right text-foreground font-medium">
                        {formatAmount(r.amount, r.currency)}
                      </td>
                      <td className="px-4 py-3">{r.status ? <StatusPill status={r.status} /> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Lineage */}
      <Card>
        <CardHeader>
          <CardTitle>Financial lineage</CardTitle>
          <p className="text-xs text-muted-foreground">
            <span className="text-blue-700 dark:text-blue-300">SOURCE</span> = authoritative
            financial facts · <span className="text-amber-700 dark:text-amber-300">DERIVED</span> =
            reconciliation / investigation / action state
          </p>
        </CardHeader>
        <CardContent>
          {!lineage || lineage.nodes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No lineage established.</p>
          ) : (
            <div className="space-y-0">
              {lineage.nodes.map((node) => (
                <LineageNodeRow key={`${node.role}-${node.kind}-${node.id}`} node={node} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Actions — only for applicable, permitted flows */}
      {(hasException || detail.investigation || detail.action_requests.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {hasException && (
              <Link
                href="/discrepancies"
                className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-surface hover:text-foreground transition-colors"
              >
                View Exception
              </Link>
            )}
            {detail.investigation && (
              <Link
                href={`/investigations/${detail.investigation.id}`}
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Investigate
              </Link>
            )}
            {detail.action_requests.length > 0 && (
              <Link
                href="/action-requests"
                className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-surface hover:text-foreground transition-colors"
              >
                View Action Requests
              </Link>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}