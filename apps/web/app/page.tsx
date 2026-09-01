"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  Layers,
  RefreshCw,
  ShieldCheck,
  Zap,
  Server,
  AlertTriangle,
  Code2,
} from "lucide-react";
import {
  HealthResponse,
  SystemInfoResponse,
  MetricsOverviewResponse,
  fetchHealth,
  fetchSystemInfo,
  fetchMetricsOverview
} from "../lib/api";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfoResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsOverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s, m] = await Promise.all([
        fetchHealth(),
        fetchSystemInfo(),
        fetchMetricsOverview()
      ]);
      setHealth(h);
      setSystemInfo(s);
      setMetrics(m);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err.message || "Failed to communicate with API server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-page-title">Dashboard</h1>
          <p className="text-secondary mt-1">
            System overview, operational health, and core infrastructure metrics.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-primary bg-primary/10 hover:bg-primary/20 rounded-md transition-colors focus-ring disabled:opacity-50"
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            {loading ? "Refreshing..." : "Refresh Status"}
          </button>
        </div>
      </div>

        {/* Status Error Display if API is down */}
        {error && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-start space-x-3 text-sm">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
            <div>
              <div className="font-semibold">Backend Connection Notice</div>
              <div className="text-slate-300 text-xs mt-1">
                {error}. Ensure the FastAPI server is running on <code className="bg-slate-900 px-1 py-0.5 rounded text-amber-200">http://localhost:8000</code>.
              </div>
            </div>
          </div>
        )}

        {/* Metrics & Health Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {/* Card 1: Total Volume */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Total Volume</span>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.total_volume !== undefined 
                ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(metrics.total_volume) 
                : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Processed lifetime volume
            </p>
          </div>

          {/* Card 2: Payments */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Payments</span>
              <Database className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.payments !== undefined ? metrics.payments.toLocaleString() : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Total registered payments
            </p>
          </div>

          {/* Card 3: Settlements */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Settlements</span>
              <Layers className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.settlements !== undefined ? metrics.settlements.toLocaleString() : "---"}
            </div>
            <p className="text-status text-muted-foreground mt-2">
              Reconciled settlement batches
            </p>
          </div>

          {/* Card 4: Merchants */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-card-title">Active Merchants</span>
              <ShieldCheck className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="text-kpi">
              {metrics?.merchants !== undefined ? metrics.merchants.toLocaleString() : "---"}
            </div>
            <p className="text-status text-matched mt-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verified operational
            </p>
          </div>
        </div>

        {/* Architecture & Verification Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Target Architecture Flow */}
          <div className="glass-panel rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-white text-base">
                  Target Vertical Slice Architecture
                </h3>
              </div>
              <span className="text-[11px] font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                Deterministic First
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-emerald-400">1. Data Sources</span>
                <span className="text-slate-400">MockPaymentGateway / MockBank / MockERP CSV</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-cyan-400">2. Normalization & Ingestion</span>
                <span className="text-slate-400">Canonical Transaction Schemas</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-purple-400">3. Immutable Ledger</span>
                <span className="text-slate-400">Double-Entry Debits == Credits</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-amber-400">4. Deterministic Reconciliation</span>
                <span className="text-slate-400">Rule-based 1:1, 1:N & Discrepancies</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-center justify-between">
                <span className="font-semibold text-rose-400">5. Governance & Audit</span>
                <span className="text-slate-400">Append-Only Audit Logs & Policy Gate</span>
              </div>
            </div>
          </div>

          {/* Core System Verification Checklist */}
          <div className="glass-panel rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Code2 className="w-5 h-5 text-cyan-400" />
                <h3 className="font-semibold text-white text-base">
                  Milestone 1 Verification Status
                </h3>
              </div>
              <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                Verified
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>FastAPI Async REST API configured with versioned routes (<code className="text-emerald-300">/health</code>, <code className="text-emerald-300">/api/v1/system/info</code>)</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Strict Decimal Money value object with banker's rounding & currency mismatch rejection</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>SQLAlchemy 2.0 connection engine with automatic async SQLite / PostgreSQL dual-mode</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Next.js 14 App Router + Tailwind CSS dark-mode dashboard shell</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Pytest async unit and integration test suite passing 100%</span>
              </div>
              <div className="flex items-center space-x-2.5 text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Docker Compose environment with PostgreSQL 16 Alpine container configuration</span>
              </div>
            </div>
          </div>
        </div>
      <div className="text-center text-xs text-muted-foreground font-mono mt-8">
        Last API Probe: {lastUpdated ? lastUpdated.toLocaleTimeString() : "Never"}
      </div>
    </div>
  );
}
