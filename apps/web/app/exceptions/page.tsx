"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchExceptions, ExceptionListResponse } from "../../lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

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

const selectClass =
  "w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2";

export default function ExceptionsPage() {
  const [data, setData] = useState<ExceptionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [type, setType] = useState("ALL");
  const [state, setState] = useState("ALL");
  const [page, setPage] = useState(1);
  const size = 50;

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, state, page]);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchExceptions({
        page,
        size,
        type,
        state,
      });
      setData(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function clearFilters() {
    setType("ALL");
    setState("ALL");
    setPage(1);
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-page-title">Exception Management</h1>
          <p className="text-secondary mt-1">
            Investigate and resolve operational discrepancies.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">State</Label>
              <select
                value={state}
                onChange={(e) => {
                  setState(e.target.value);
                  setPage(1);
                }}
                className={selectClass}
              >
                <option value="ALL">All States</option>
                {Object.keys(STATE_TONES).map(s => (
                  <option key={s} value={s}>{s.replace("_", " ")}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-muted-foreground">Type</Label>
              <select
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                  setPage(1);
                }}
                className={selectClass}
              >
                <option value="ALL">All Types</option>
                <option value="FEE_MISMATCH">Fee Mismatch</option>
                <option value="AMOUNT_MISMATCH">Amount Mismatch</option>
                <option value="MISSING_BANK_TX">Missing Bank Tx</option>
                <option value="MISSING_SETTLEMENT">Missing Settlement</option>
                <option value="LATE_ARRIVAL">Late Arrival</option>
                <option value="CURRENCY_MISMATCH">Currency Mismatch</option>
                <option value="ORPHAN_RECORD">Orphan Record</option>
              </select>
            </div>
          </div>
          {(type !== "ALL" || state !== "ALL") && (
            <button
              onClick={clearFilters}
              className="text-xs text-primary hover:underline underline-offset-2"
            >
              Clear filters
            </button>
          )}
        </CardContent>
      </Card>

      {error ? (
        <Card>
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-destructive text-sm">{error}</p>
            <Button onClick={load} variant="outline" size="sm">Retry</Button>
          </CardContent>
        </Card>
      ) : loading ? (
        <Card>
          <CardContent className="p-6 text-muted-foreground text-sm">Loading exceptions...</CardContent>
        </Card>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-foreground font-medium">No exceptions found</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Exceptions</CardTitle>
            <span className="text-sm text-muted-foreground">{data.total.toLocaleString()} total</span>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-border overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-muted-foreground bg-surface-muted uppercase border-b border-border">
                  <tr>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">State</th>
                    <th className="px-4 py-3">Transaction</th>
                    <th className="px-4 py-3 text-right">Difference</th>
                    <th className="px-4 py-3">Detected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-surface-muted/50 transition-colors">
                      <td className="px-4 py-3">
                        <Link href={`/exceptions/${item.id}`} className="text-primary hover:text-primary/80 font-mono text-xs">
                          {item.id.split("-")[0]}...
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {item.type.replace("_", " ")}
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={STATE_TONES[item.overall_state] ?? "neutral"}>
                          {item.overall_state.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/transactions/${item.source_entity_id}`} className="text-primary hover:text-primary/80 font-mono text-xs">
                          {item.source_entity_type}: {item.source_entity_id.split("-")[0]}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right text-foreground font-medium">
                        {item.amount != null ? (() => {
                          const amount = Number(item.amount);
                          return (
                            <span className={amount > 0 ? "text-amber-700 dark:text-amber-400" : "text-emerald-700 dark:text-emerald-400"}>
                              {amount > 0 ? "+" : ""}{amount.toFixed(2)} {item.currency}
                            </span>
                          );
                        })() : "N/A"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {new Date(item.detected_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-muted-foreground">
                Page {page} (Max {Math.ceil(data.total / size) || 1})
              </span>
              <div className="flex gap-2">
                <Button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  variant="outline"
                  size="sm"
                >
                  Previous
                </Button>
                <Button
                  onClick={() => setPage(page + 1)}
                  disabled={page * size >= data.total}
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