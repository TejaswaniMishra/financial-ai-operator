"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  fetchTransactions,
  TransactionListResponse,
  TransactionRecord,
  TransactionRecordType,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const RECORD_TYPES: Array<{ value: TransactionRecordType | ""; label: string }> = [
  { value: "", label: "All types" },
  { value: "PAYMENT", label: "Payments" },
  { value: "REFUND", label: "Refunds" },
  { value: "FEE", label: "Fees" },
  { value: "SETTLEMENT", label: "Settlements" },
  { value: "BANK_TRANSACTION", label: "Bank transactions" },
];

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

function formatAmount(amount: string, currency: string) {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(n);
}

export default function TransactionsPage() {
  const [data, setData] = useState<TransactionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [recordType, setRecordType] = useState<TransactionRecordType | "">("");
  const [status, setStatus] = useState("");
  const [currency, setCurrency] = useState("");
  const [reconciled, setReconciled] = useState<"" | "true" | "false">("");
  const [hasDiscrepancy, setHasDiscrepancy] = useState<"" | "true" | "false">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(search);
      setOffset(0);
    }, 400);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchTransactions({
        record_type: recordType || undefined,
        status: status || undefined,
        currency: currency || undefined,
        reconciled: reconciled === "" ? undefined : reconciled === "true",
        has_discrepancy:
          hasDiscrepancy === "" ? undefined : hasDiscrepancy === "true",
        date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
        search: debouncedSearch || undefined,
        limit,
        offset,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transactions.");
    } finally {
      setLoading(false);
    }
  }, [recordType, status, currency, reconciled, hasDiscrepancy, dateFrom, dateTo, debouncedSearch, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const hasFilters =
    recordType !== "" ||
    status !== "" ||
    currency !== "" ||
    reconciled !== "" ||
    hasDiscrepancy !== "" ||
    dateFrom !== "" ||
    dateTo !== "" ||
    search !== "";

  const clearFilters = () => {
    setRecordType("");
    setStatus("");
    setCurrency("");
    setReconciled("");
    setHasDiscrepancy("");
    setDateFrom("");
    setDateTo("");
    setSearch("");
    setDebouncedSearch("");
    setOffset(0);
  };

  const summary = data?.summary;
  const kpis = summary
    ? [
        { label: "Payments", value: summary.PAYMENT },
        { label: "Refunds", value: summary.REFUND },
        { label: "Fees", value: summary.FEE },
        { label: "Settlements", value: summary.SETTLEMENT },
        { label: "Bank transactions", value: summary.BANK_TRANSACTION },
        { label: "Total", value: summary.total },
      ]
    : [];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-50">
            Transactions
          </h1>
          <p className="text-slate-400 mt-1">
            Authoritative financial records across payments, refunds, fees,
            settlements, and bank transactions — with reconciliation and
            exception state.
          </p>
        </div>
      </div>

      {/* KPI cards — real backend counts for the current filter set */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label} className="bg-slate-900 border-slate-800">
            <CardContent className="p-4">
              <p className="text-xs text-slate-400 uppercase tracking-wide">
                {kpi.label}
              </p>
              <p className="text-2xl font-bold text-slate-50 mt-1">
                {kpi.value.toLocaleString()}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search + filters */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Search</label>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Transaction ID, external ID, merchant…"
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Type</label>
              <select
                value={recordType}
                onChange={(e) => {
                  setRecordType(e.target.value as TransactionRecordType | "");
                  setOffset(0);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              >
                {RECORD_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Status</label>
              <input
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                }}
                placeholder="e.g. CAPTURED, SETTLED, COMPLETED"
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 placeholder-slate-500 outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Currency</label>
              <input
                value={currency}
                onChange={(e) => {
                  setCurrency(e.target.value.toUpperCase());
                  setOffset(0);
                }}
                placeholder="USD"
                maxLength={3}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 placeholder-slate-500 outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Reconciled</label>
              <select
                value={reconciled}
                onChange={(e) => {
                  setReconciled(e.target.value as "" | "true" | "false");
                  setOffset(0);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              >
                <option value="">Any</option>
                <option value="true">Reconciled</option>
                <option value="false">Unreconciled</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Exception</label>
              <select
                value={hasDiscrepancy}
                onChange={(e) => {
                  setHasDiscrepancy(e.target.value as "" | "true" | "false");
                  setOffset(0);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              >
                <option value="">Any</option>
                <option value="true">Has discrepancy</option>
                <option value="false">No discrepancy</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setOffset(0);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setOffset(0);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              />
            </div>
          </div>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2"
            >
              Clear filters
            </button>
          )}
        </CardContent>
      </Card>

      {/* States */}
      {error ? (
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
      ) : loading ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-slate-400 text-sm">
            Loading transactions…
          </CardContent>
        </Card>
      ) : !data || data.items.length === 0 ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-center">
            <p className="text-slate-300 font-medium">No transactions found</p>
            <p className="text-slate-500 text-sm mt-1">
              Try adjusting the search or filters.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-slate-100">Records</CardTitle>
            <span className="text-sm text-slate-400">
              {data.total.toLocaleString()} total
            </span>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-slate-800 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Merchant</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3">State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.items.map((item: TransactionRecord) => (
                    <tr key={`${item.record_type}-${item.id}`} className="hover:bg-slate-800/40">
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
                            TYPE_COLORS[item.record_type] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30"
                          )}
                        >
                          {item.record_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/transactions/${item.id}`}
                          className="text-blue-400 hover:text-blue-300 font-mono text-xs"
                        >
                          {item.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-300">{item.merchant_name}</td>
                      <td className="px-4 py-3 text-right text-slate-200 font-medium">
                        {formatAmount(item.amount, item.currency)}
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={item.status} />
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          {item.reconciled && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                              Reconciled
                            </span>
                          )}
                          {item.has_discrepancy && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-red-500/15 text-red-300 border-red-500/30">
                              Exception
                            </span>
                          )}
                          {!item.reconciled && !item.has_discrepancy && (
                            <span className="text-xs text-slate-600">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-slate-500">
                Showing {data.items.length ? offset + 1 : 0}–
                {offset + data.items.length} of {data.total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="px-3 py-1.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= data.total}
                  className="px-3 py-1.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700"
                >
                  Next
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}