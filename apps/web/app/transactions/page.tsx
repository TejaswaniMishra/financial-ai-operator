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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const RECORD_TYPES: Array<{ value: TransactionRecordType | ""; label: string }> = [
  { value: "", label: "All types" },
  { value: "PAYMENT", label: "Payments" },
  { value: "REFUND", label: "Refunds" },
  { value: "FEE", label: "Fees" },
  { value: "SETTLEMENT", label: "Settlements" },
  { value: "BANK_TRANSACTION", label: "Bank transactions" },
];

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

function formatAmount(amount: string, currency: string) {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(n);
}

const selectClass =
  "w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2";

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
          <h1 className="text-page-title">
            Transactions
          </h1>
          <p className="text-secondary mt-1">
            Authoritative financial records across payments, refunds, fees,
            settlements, and bank transactions — with reconciliation and
            exception state.
          </p>
        </div>
      </div>

      {/* KPI cards — real backend counts for the current filter set */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="p-4">
              <p className="text-card-title">
                {kpi.label}
              </p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {kpi.value.toLocaleString()}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search + filters */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Search</Label>
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Transaction ID, external ID, merchant…"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Type</Label>
              <select
                value={recordType}
                onChange={(e) => {
                  setRecordType(e.target.value as TransactionRecordType | "");
                  setOffset(0);
                }}
                className={selectClass}
              >
                {RECORD_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Status</Label>
              <Input
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                }}
                placeholder="e.g. CAPTURED, SETTLED, COMPLETED"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Currency</Label>
              <Input
                value={currency}
                onChange={(e) => {
                  setCurrency(e.target.value.toUpperCase());
                  setOffset(0);
                }}
                placeholder="USD"
                maxLength={3}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Reconciled</Label>
              <select
                value={reconciled}
                onChange={(e) => {
                  setReconciled(e.target.value as "" | "true" | "false");
                  setOffset(0);
                }}
                className={selectClass}
              >
                <option value="">Any</option>
                <option value="true">Reconciled</option>
                <option value="false">Unreconciled</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Exception</Label>
              <select
                value={hasDiscrepancy}
                onChange={(e) => {
                  setHasDiscrepancy(e.target.value as "" | "true" | "false");
                  setOffset(0);
                }}
                className={selectClass}
              >
                <option value="">Any</option>
                <option value="true">Has discrepancy</option>
                <option value="false">No discrepancy</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">From</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">To</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
          </div>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-primary hover:underline underline-offset-2"
            >
              Clear filters
            </button>
          )}
        </CardContent>
      </Card>

      {/* States */}
      {error ? (
        <Card>
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-destructive text-sm">{error}</p>
            <Button onClick={load} variant="outline" size="sm">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : loading ? (
        <Card>
          <CardContent className="p-6 text-muted-foreground text-sm">
            Loading transactions…
          </CardContent>
        </Card>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-foreground font-medium">No transactions found</p>
            <p className="text-muted-foreground text-sm mt-1">
              Try adjusting the search or filters.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Records</CardTitle>
            <span className="text-sm text-muted-foreground">
              {data.total.toLocaleString()} total
            </span>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-border overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-muted-foreground bg-surface-muted uppercase border-b border-border">
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
                <tbody className="divide-y divide-border">
                  {data.items.map((item: TransactionRecord) => (
                    <tr key={`${item.record_type}-${item.id}`} className="hover:bg-surface-muted/50 transition-colors">
                      <td className="px-4 py-3">
                        <Badge tone={TYPE_TONES[item.record_type] ?? "neutral"}>
                          {item.record_type.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/transactions/${item.id}`}
                          className="text-primary hover:text-primary/80 font-mono text-xs"
                        >
                          {item.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-foreground">{item.merchant_name}</td>
                      <td className="px-4 py-3 text-right text-foreground font-medium">
                        {formatAmount(item.amount, item.currency)}
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={item.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          {item.reconciled && (
                            <Badge tone="emerald">
                              Reconciled
                            </Badge>
                          )}
                          {item.has_discrepancy && (
                            <Badge tone="red">
                              Exception
                            </Badge>
                          )}
                          {!item.reconciled && !item.has_discrepancy && (
                            <span className="text-xs text-muted-foreground">—</span>
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
              <span className="text-xs text-muted-foreground">
                Showing {data.items.length ? offset + 1 : 0}–
                {offset + data.items.length} of {data.total}
              </span>
              <div className="flex gap-2">
                <Button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  variant="outline"
                  size="sm"
                >
                  Previous
                </Button>
                <Button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= data.total}
                  variant="outline"
                  size="sm"
                >
                  Next
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}