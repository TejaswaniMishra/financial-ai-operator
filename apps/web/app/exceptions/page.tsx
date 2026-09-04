"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchExceptions, ExceptionListResponse, OverallExceptionState } from "../../lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "../../lib/utils";

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
          <h1 className="text-2xl font-semibold text-slate-100">Exception Management</h1>
          <p className="text-sm text-slate-400 mt-1">
            Investigate and resolve operational discrepancies.
          </p>
        </div>
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">State</label>
              <select
                value={state}
                onChange={(e) => {
                  setState(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
              >
                <option value="ALL">All States</option>
                {Object.keys(STATE_COLORS).map(s => (
                  <option key={s} value={s}>{s.replace("_", " ")}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Type</label>
              <select
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
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
              className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2"
            >
              Clear filters
            </button>
          )}
        </CardContent>
      </Card>

      {error ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-red-400 text-sm">{error}</p>
            <button onClick={load} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm">Retry</button>
          </CardContent>
        </Card>
      ) : loading ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-slate-400 text-sm">Loading exceptions...</CardContent>
        </Card>
      ) : !data || data.items.length === 0 ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="p-6 text-center">
            <p className="text-slate-300 font-medium">No exceptions found</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-slate-100">Exceptions</CardTitle>
            <span className="text-sm text-slate-400">{data.total.toLocaleString()} total</span>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-slate-800 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">State</th>
                    <th className="px-4 py-3">Transaction</th>
                    <th className="px-4 py-3 text-right">Difference</th>
                    <th className="px-4 py-3">Detected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/40">
                      <td className="px-4 py-3">
                        <Link href={`/exceptions/${item.id}`} className="text-blue-400 hover:text-blue-300 font-mono text-xs">
                          {item.id.split("-")[0]}...
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {item.type.replace("_", " ")}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border", STATE_COLORS[item.overall_state] || STATE_COLORS.OPEN)}>
                          {item.overall_state.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/transactions/${item.source_entity_id}`} className="text-blue-400 hover:text-blue-300 font-mono text-xs">
                          {item.source_entity_type}: {item.source_entity_id.split("-")[0]}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-200 font-medium">
                        {item.amount != null ? (() => {
                          const amount = Number(item.amount);
                          return (
                            <span className={amount > 0 ? "text-amber-400" : "text-emerald-400"}>
                              {amount > 0 ? "+" : ""}{amount.toFixed(2)} {item.currency}
                            </span>
                          );
                        })() : "N/A"}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {new Date(item.detected_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-slate-500">
                Page {page} (Max {Math.ceil(data.total / size) || 1})
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page * size >= data.total}
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
