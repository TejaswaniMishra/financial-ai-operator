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
import { cn } from "@/lib/utils";

const TYPE_COLORS: Record<string, string> = {
  PAYMENT: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  REFUND: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  FEE: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  SETTLEMENT: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  BANK_TRANSACTION: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
};

function StatusPill({ status }: { status: string }) {
  const tone = /FAILED|REJECTED|DENIED|UNRESOLVED/i.test(status)
    ? "bg-red-500/15 text-red-300 border-red-500/30"
    : /PENDING|RUNNING|UNKNOWN/i.test(status)
      ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
      : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        tone
      )}
    >
      {status}
    </span>
  );
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
      <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
      <div className="text-sm text-slate-200 mt-0.5">{children}</div>
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
              ? "bg-blue-400 ring-blue-500/20"
              : "bg-amber-400 ring-amber-500/20"
          )}
        />
        <div className="w-px flex-1 bg-slate-800" />
      </div>
      <div className="pb-5 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
              TYPE_COLORS[node.kind] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30"
            )}
          >
            {node.kind.replace("_", " ")}
          </span>
          <span
            className={cn(
              "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase border",
              isSource
                ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
                : "bg-amber-500/10 text-amber-300 border-amber-500/30"
            )}
          >
            {node.role}
          </span>
          {node.status && <StatusPill status={node.status} />}
        </div>
        <p className="text-sm text-slate-200 mt-1.5 font-mono text-xs">{node.label}</p>
        <p className="text-xs text-slate-400 mt-0.5">
          {node.amount !== null && node.amount !== undefined && (
            <span className="text-slate-300 font-medium">
              {formatAmount(node.amount, node.currency)} ·{" "}
            </span>
          )}
          {node.timestamp ? new Date(node.timestamp).toLocaleString() : ""}
        </p>
        {node.detail && Object.keys(node.detail).length > 0 && (
          <details className="text-xs text-slate-400 mt-1">
            <summary className="cursor-pointer text-blue-400 hover:text-blue-300">
              Details
            </summary>
            <pre className="mt-1 p-2 bg-slate-950 rounded border border-slate-800 whitespace-pre-wrap break-all">
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
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-slate-400 text-sm">
            Loading transaction…
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={load}
              className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm"
            >
              Retry
            </button>
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
            <span
              className={cn(
                "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border",
                TYPE_COLORS[detail.record_type] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30"
              )}
            >
              {detail.record_type.replace("_", " ")}
            </span>
            <StatusPill status={detail.status} />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-50 mt-2 font-mono">
            {detail.id}
          </h1>
          <p className="text-slate-400 mt-1">
            {detail.external_id && <>External: {detail.external_id} · </>}
            {new Date(detail.created_at).toLocaleString()}
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-slate-50">
            {formatAmount(detail.amount, detail.currency)}
          </p>
          <p className="text-sm text-slate-400">{detail.currency}</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-5 space-y-3">
            <Field label="Merchant">{detail.merchant.name}</Field>
            <Field label="Provider">
              {detail.provider || "—"}
            </Field>
            {detail.order && (
              <Field label="Order">
                <Link href={`/transactions/${detail.order.id}`} className="text-blue-400 hover:text-blue-300 font-mono">
                  {detail.order.id}
                </Link>
                <span className="text-slate-400 text-xs block mt-0.5">
                  {detail.order.status} · {formatAmount(detail.order.amount, detail.order.currency)}
                </span>
              </Field>
            )}
            {detail.customer && (
              <Field label="Customer">{detail.customer.display_name}</Field>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-sm">Reconciliation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.reconciliation.length === 0 ? (
              <p className="text-sm text-slate-500">No reconciliation relationship established.</p>
            ) : (
              detail.reconciliation.map((rel) => (
                <div key={rel.relationship_id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <StatusPill status={rel.relationship_status} />
                    <span className="text-xs text-slate-400">
                      {rel.relationship_type.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Financial: {rel.financial_status} · Run: {rel.run_status}
                  </p>
                  <p className="text-xs text-slate-600 font-mono">
                    {rel.source_entity_type} {rel.source_entity_id.slice(0, 8)} →{" "}
                    {rel.target_entity_type} {rel.target_entity_id.slice(0, 8)}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-sm">Exception state</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!hasException ? (
              <p className="text-sm text-slate-500">No discrepancies for this record.</p>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <StatusPill status={discrepancy.severity} />
                  <span className="text-xs text-slate-400">
                    {discrepancy.discrepancy_type.replace("_", " ")}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Rule {discrepancy.rule_code} · diff{" "}
                  {formatAmount(discrepancy.difference_amount, discrepancy.currency)}
                </p>
                {detail.investigation && (
                  <p className="text-xs text-slate-400">
                    Investigation:{" "}
                    <Link
                      href={`/investigations/${detail.investigation.id}`}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      {detail.investigation.status}
                    </Link>
                  </p>
                )}
              </>
            )}
            {detail.action_requests.length > 0 && (
              <div className="pt-2 border-t border-slate-800">
                <p className="text-xs text-slate-500 mb-1">Action requests</p>
                {detail.action_requests.map((ar) => (
                  <div key={ar.id} className="flex items-center gap-2">
                    <StatusPill status={ar.status} />
                    <span className="text-xs text-slate-400">{ar.action.replace("_", " ")}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Financial details / related records */}
      {detail.related.length > 0 && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-sm">Financial details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-slate-800 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {detail.related.map((r) => (
                    <tr key={`${r.record_type}-${r.id}`} className="hover:bg-slate-800/40">
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
                            TYPE_COLORS[r.record_type] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30"
                          )}
                        >
                          {r.record_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/transactions/${r.id}`}
                          className="text-blue-400 hover:text-blue-300 font-mono text-xs"
                        >
                          {r.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-200 font-medium">
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
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-slate-100">Financial lineage</CardTitle>
          <p className="text-xs text-slate-500">
            <span className="text-blue-300">SOURCE</span> = authoritative
            financial facts · <span className="text-amber-300">DERIVED</span> =
            reconciliation / investigation / action state
          </p>
        </CardHeader>
        <CardContent>
          {!lineage || lineage.nodes.length === 0 ? (
            <p className="text-sm text-slate-500">No lineage established.</p>
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
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-100 text-sm">Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {hasException && (
              <Link
                href="/discrepancies"
                className="px-4 py-2 rounded bg-slate-800 border border-slate-700 text-slate-200 text-sm hover:bg-slate-700"
              >
                View Exception
              </Link>
            )}
            {detail.investigation && (
              <Link
                href={`/investigations/${detail.investigation.id}`}
                className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm"
              >
                Investigate
              </Link>
            )}
            {detail.action_requests.length > 0 && (
              <Link
                href="/action-requests"
                className="px-4 py-2 rounded bg-slate-800 border border-slate-700 text-slate-200 text-sm hover:bg-slate-700"
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