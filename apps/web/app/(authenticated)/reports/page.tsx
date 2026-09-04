"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { format, subDays, subMonths } from "date-fns";
import {
  AlertCircle, ArrowRight, BarChart3, CheckCircle2, RefreshCw,
  TrendingUp, XCircle, AlertTriangle, Shield, Calendar,
} from "lucide-react";

import {
  fetchReportSummary, fetchFinancialFlow, fetchReconciliationAnalytics,
  fetchExceptionAnalytics, fetchOperationalRisk, fetchReportPeriods,
  fetchTrends,
  ExecutiveSummary, ReconciliationAnalytics, ExceptionAnalytics,
  OperationalRiskSummary, PeriodReportRow, TrendPoint,
  FinancialFlowSummary,
} from "@/lib/api";

// ─── Design tokens ────────────────────────────────────────────────────────────
const CHART_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#ec4899", "#10b981", "#8b5cf6"];
const STATE_COLORS: Record<string, string> = {
  OPEN: "#ef4444",
  INVESTIGATING: "#f59e0b",
  AWAITING_APPROVAL: "#6366f1",
  APPROVED: "#3b82f6",
  EXECUTING: "#8b5cf6",
  RESOLVED: "#10b981",
  FAILED: "#dc2626",
  UNKNOWN: "#6b7280",
};

// ─── Helper components ────────────────────────────────────────────────────────

function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  color = "text-primary",
  href,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ElementType;
  color?: string;
  href?: string;
}) {
  const inner = (
    <div className="rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
          {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
        </div>
        {Icon && (
          <div className="p-2 rounded-lg bg-muted/50">
            <Icon className={`h-5 w-5 ${color}`} />
          </div>
        )}
      </div>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

function AlertCard({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-error/30 bg-error/5 p-4 text-sm text-error">
      <AlertCircle className="h-4 w-4 shrink-0" />
      {message}
    </div>
  );
}

function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 rounded-lg bg-muted/50" />
      ))}
    </div>
  );
}

// ─── Filters ──────────────────────────────────────────────────────────────────

type DatePreset = "7d" | "30d" | "90d" | "all";

function filterDates(preset: DatePreset): { start?: string; end?: string } {
  const now = new Date();
  if (preset === "all") return {};
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  return {
    start: subDays(now, days).toISOString(),
    end: now.toISOString(),
  };
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [preset, setPreset] = useState<DatePreset>("30d");
  const [currency, setCurrency] = useState<string>("");

  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [flow, setFlow] = useState<FinancialFlowSummary | null>(null);
  const [recon, setRecon] = useState<ReconciliationAnalytics | null>(null);
  const [excAnalytics, setExcAnalytics] = useState<ExceptionAnalytics | null>(null);
  const [ops, setOps] = useState<OperationalRiskSummary | null>(null);
  const [periods, setPeriods] = useState<PeriodReportRow[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { start, end } = filterDates(preset);
      const params = { start_date: start, end_date: end, currency: currency || undefined };
      const [s, f, r, e, o, p, t] = await Promise.all([
        fetchReportSummary(params),
        fetchFinancialFlow({ start_date: start, end_date: end }),
        fetchReconciliationAnalytics({ start_date: start, end_date: end }),
        fetchExceptionAnalytics({ start_date: start, end_date: end }),
        fetchOperationalRisk(),
        fetchReportPeriods({ limit: 10 }),
        fetchTrends({ metric: "payment_volume", granularity: "day", start_date: start, end_date: end }),
      ]);
      setSummary(s);
      setFlow(f);
      setRecon(r);
      setExcAnalytics(e);
      setOps(o);
      setPeriods(p.items);
      setTrends(t.data);
    } catch (err: any) {
      setError(err.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }, [preset, currency]);

  useEffect(() => { load(); }, [load]);

  // Derive available currencies from summary for filter dropdown
  const availableCurrencies = Array.from(
    new Set((summary?.payment_volume ?? []).map((v) => v.currency))
  ).sort();

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Financial Reports</h1>
          <p className="text-muted-foreground text-sm mt-1">
            CFO analytics — all figures sourced from authoritative financial records.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {/* Date presets */}
          {(["7d", "30d", "90d", "all"] as DatePreset[]).map((p) => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                preset === p
                  ? "bg-primary text-primary-foreground border-primary"
                  : "text-muted-foreground border-border hover:border-primary/50"
              }`}
            >
              {p === "all" ? "All time" : `Last ${p}`}
            </button>
          ))}

          {/* Currency filter */}
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="text-xs px-3 py-1.5 rounded-full border border-border bg-background text-foreground"
          >
            <option value="">All currencies</option>
            {availableCurrencies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <button
            onClick={load}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-full border border-border text-muted-foreground hover:border-primary/50 transition-colors flex items-center gap-1"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && <AlertCard message={error} />}

      {/* ── Section 1: Executive KPIs ─────────────────────────────────────── */}
      <section>
        <SectionHeading title="Executive KPIs" subtitle="Volume metrics are currency-isolated — never aggregated across currencies." />
        {loading ? <LoadingSkeleton rows={2} /> : summary ? (
          <div className="space-y-4">
            {/* Volume cards per currency */}
            {(() => {
              const currencies = Array.from(
                new Set([
                  ...summary.payment_volume.map(v => v.currency),
                  ...summary.refund_volume.map(v => v.currency),
                ])
              ).sort();
              const filtered = currency ? currencies.filter(c => c === currency) : currencies;
              return filtered.map((ccy) => {
                const pay = summary.payment_volume.find(v => v.currency === ccy);
                const ref = summary.refund_volume.find(v => v.currency === ccy);
                const set = summary.settlement_volume.find(v => v.currency === ccy);
                return (
                  <div key={ccy}>
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">{ccy}</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                      <KpiCard label="Payment Volume" value={pay ? Number(pay.total_amount).toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0"} sub={`${pay?.count ?? 0} payments`} icon={TrendingUp} color="text-indigo-500" href="/transactions" />
                      <KpiCard label="Refund Volume" value={ref ? Number(ref.total_amount).toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0"} sub={`${ref?.count ?? 0} refunds`} icon={XCircle} color="text-pink-500" href="/transactions" />
                      <KpiCard label="Settlement Volume" value={set ? Number(set.total_amount).toLocaleString(undefined, { maximumFractionDigits: 2 }) : "0"} sub={`${set?.count ?? 0} settlements`} icon={CheckCircle2} color="text-emerald-500" />
                    </div>
                  </div>
                );
              });
            })()}

            {/* Operational counts */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <KpiCard
                label="Reconciled"
                value={summary.reconciled_count}
                sub={`${summary.unreconciled_count} unreconciled`}
                icon={CheckCircle2}
                color="text-emerald-500"
                href="/reconciliation"
              />
              <KpiCard
                label="Open Exceptions"
                value={summary.unresolved_exception_count}
                icon={AlertTriangle}
                color="text-amber-500"
                href="/exceptions"
              />
              <KpiCard
                label="Discrepancies"
                value={summary.discrepancy_count}
                icon={AlertCircle}
                color="text-red-500"
                href="/discrepancies"
              />
              <KpiCard
                label="Pending Actions"
                value={summary.pending_action_request_count}
                icon={Shield}
                color="text-indigo-500"
                href="/action-requests"
              />
              <KpiCard
                label="Failed Executions"
                value={summary.failed_execution_count}
                icon={XCircle}
                color="text-red-600"
              />
            </div>
          </div>
        ) : null}
      </section>

      {/* ── Section 2: Payment Volume Trend ────────────────────────────────── */}
      <section>
        <SectionHeading title="Payment Volume Trend" subtitle="Daily aggregation — UTC timezone." />
        {loading ? <LoadingSkeleton rows={1} /> : trends.length === 0 ? (
          <div className="flex items-center justify-center h-40 rounded-xl border border-dashed text-muted-foreground text-sm">
            No trend data available for this period.
          </div>
        ) : (
          <div className="rounded-xl border bg-card p-4 shadow-sm">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trends} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: 12 }}
                  formatter={(v: any) => [Number(v).toLocaleString(), "Volume"]}
                />
                <Area type="monotone" dataKey="value" stroke="#6366f1" fill="url(#colorVal)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* ── Section 3: Financial Flow ───────────────────────────────────────── */}
      <section>
        <SectionHeading title="Financial Flow" subtitle="Volume at each stage of the pipeline, by currency." />
        {loading ? <LoadingSkeleton rows={1} /> : flow ? (
          <div className="rounded-xl border bg-card p-4 shadow-sm">
            {flow.stages.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No financial flow data.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={Object.values(
                    flow.stages.reduce<Record<string, any>>((acc, s) => {
                      const key = `${s.stage}/${s.currency}`;
                      if (!acc[key]) acc[key] = { name: `${s.stage} (${s.currency})`, value: 0 };
                      acc[key].value += Number(s.total_amount);
                      return acc;
                    }, {})
                  )}
                  margin={{ top: 10, right: 20, left: 10, bottom: 40 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: 12 }}
                    formatter={(v: any) => [Number(v).toLocaleString(), "Amount"]}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {flow.stages.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        ) : null}
      </section>

      {/* ── Section 4: Reconciliation + Exceptions ─────────────────────────── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Reconciliation */}
        <section>
          <SectionHeading title="Reconciliation" />
          {loading ? <LoadingSkeleton rows={2} /> : recon ? (
            <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-2xl font-bold text-emerald-500">{recon.reconciled_count}</p>
                  <p className="text-xs text-muted-foreground">Reconciled</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-500">{recon.unreconciled_count}</p>
                  <p className="text-xs text-muted-foreground">Unreconciled</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-indigo-500">
                    {recon.reconciliation_rate != null ? `${(recon.reconciliation_rate * 100).toFixed(1)}%` : "N/A"}
                  </p>
                  <p className="text-xs text-muted-foreground">Rate</p>
                </div>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{ width: recon.reconciliation_rate != null ? `${(recon.reconciliation_rate * 100).toFixed(1)}%` : "0%" }}
                />
              </div>
              {recon.discrepancy_count > 0 && (
                <Link href="/discrepancies" className="flex items-center justify-between text-sm text-amber-600 hover:text-amber-500">
                  <span>{recon.discrepancy_count} discrepancies found</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </div>
          ) : null}
        </section>

        {/* Exception state distribution */}
        <section>
          <SectionHeading title="Exception States" />
          {loading ? <LoadingSkeleton rows={2} /> : excAnalytics ? (
            <div className="rounded-xl border bg-card p-5 shadow-sm">
              {excAnalytics.total_exceptions === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No exceptions found.</p>
              ) : (
                <div className="flex gap-4 items-center">
                  <ResponsiveContainer width={160} height={160}>
                    <PieChart>
                      <Pie
                        data={excAnalytics.by_state}
                        dataKey="count"
                        nameKey="state"
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={70}
                      >
                        {excAnalytics.by_state.map((entry, i) => (
                          <Cell key={entry.state} fill={STATE_COLORS[entry.state] ?? CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: 11 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex-1 space-y-1">
                    {excAnalytics.by_state.map((s) => (
                      <div key={s.state} className="flex items-center justify-between text-xs">
                        <span className="flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[s.state] ?? "#6b7280" }} />
                          {s.state}
                        </span>
                        <span className="font-medium">{s.count}</span>
                      </div>
                    ))}
                    <Link href="/exceptions" className="flex items-center gap-1 text-xs text-primary mt-2 hover:underline">
                      View all exceptions <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </section>
      </div>

      {/* ── Section 5: Operational Risk Indicators ─────────────────────────── */}
      <section>
        <SectionHeading title="Operational Risk Indicators" subtitle="These are operational counts, not financial-risk scores." />
        {loading ? <LoadingSkeleton rows={1} /> : ops ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <KpiCard label="Pending Investigations" value={ops.pending_investigations} icon={Shield} color="text-amber-500" href="/investigations" />
            <KpiCard label="Failed Investigations" value={ops.failed_investigations} icon={XCircle} color="text-red-500" href="/investigations" />
            <KpiCard label="Pending Approvals" value={ops.pending_action_requests} icon={AlertTriangle} color="text-indigo-500" href="/action-requests" />
            <KpiCard label="Failed Executions" value={ops.failed_executions} icon={XCircle} color="text-red-600" />
            <KpiCard label="Blocked Periods" value={ops.blocked_periods} icon={Calendar} color="text-amber-600" href="/periods" />
          </div>
        ) : null}
      </section>

      {/* ── Section 6: Period Performance ──────────────────────────────────── */}
      <section>
        <SectionHeading title="Period Performance" subtitle="Recent financial periods — click to navigate to full period workspace." />
        {loading ? <LoadingSkeleton rows={3} /> : periods.length === 0 ? (
          <div className="flex items-center justify-center h-32 rounded-xl border border-dashed text-muted-foreground text-sm">
            No financial periods found.
          </div>
        ) : (
          <div className="rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr>
                  {["Period", "Date Range", "Status", "Readiness", "Payments", "Settlements", "Exceptions"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {periods.map((p) => (
                  <tr key={p.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3">
                      <Link href={`/periods/${p.id}`} className="font-medium text-primary hover:underline">
                        {p.period_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs whitespace-nowrap">
                      {format(new Date(p.start_date), "MMM d")} – {format(new Date(p.end_date), "MMM d, yyyy")}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        p.status === "CLOSED" ? "bg-slate-100 text-slate-700" :
                        p.status === "CLOSING" ? "bg-amber-100 text-amber-700" :
                        "bg-green-100 text-green-700"
                      }`}>{p.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      {p.last_readiness === null ? (
                        <span className="text-muted-foreground text-xs">Not evaluated</span>
                      ) : p.last_readiness ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-600"><CheckCircle2 className="h-3 w-3" /> Ready</span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-red-600"><XCircle className="h-3 w-3" /> {p.last_blocker_count} blocker{p.last_blocker_count !== 1 ? "s" : ""}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">{p.payment_count}</td>
                    <td className="px-4 py-3 text-center">{p.settlement_count}</td>
                    <td className="px-4 py-3 text-center">
                      {p.exception_count > 0 ? (
                        <Link href="/exceptions" className="text-amber-600 font-medium hover:underline">{p.exception_count}</Link>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
