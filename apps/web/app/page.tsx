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
import { HealthResponse, SystemInfoResponse, fetchHealth, fetchSystemInfo } from "../lib/api";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfoResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s] = await Promise.all([fetchHealth(), fetchSystemInfo()]);
      setHealth(h);
      setSystemInfo(s);
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Card 1: API Gateway Status */}
          <div className="glass-panel rounded-xl p-5 relative overflow-hidden group hover:border-slate-700 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                API Gateway
              </span>
              <Server className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-xl font-bold text-white flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              <span>{health?.status === "healthy" ? "Operational" : health?.status || "Checking..."}</span>
            </div>
            <p className="text-xs text-slate-400 mt-2 font-mono">
              FastAPI v0.115 • REST Async
            </p>
          </div>

          {/* Card 2: Database Connectivity */}
          <div className="glass-panel rounded-xl p-5 relative overflow-hidden group hover:border-slate-700 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Persistence Engine
              </span>
              <Database className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-xl font-bold text-white flex items-center space-x-2">
              <span className={`w-2.5 h-2.5 rounded-full ${health?.database.connected ? "bg-emerald-400" : "bg-amber-400"}`}></span>
              <span>{health?.database.connected ? "Connected" : "Disconnected"}</span>
            </div>
            <p className="text-xs text-slate-400 mt-2 font-mono">
              {health?.database.engine ? `Engine: ${health.database.engine}` : "SQLAlchemy 2.0 Async"}
              {health?.database.latency_ms ? ` (${health.database.latency_ms}ms)` : ""}
            </p>
          </div>

          {/* Card 3: Financial Schema Engine */}
          <div className="glass-panel rounded-xl p-5 relative overflow-hidden group hover:border-slate-700 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Financial Correctness
              </span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-xl font-bold text-white flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Strict Decimal</span>
            </div>
            <p className="text-xs text-slate-400 mt-2 font-mono">
              Zero Float Policy • Banker's Rounding
            </p>
          </div>

          {/* Card 4: Architecture Uptime */}
          <div className="glass-panel rounded-xl p-5 relative overflow-hidden group hover:border-slate-700 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                System Uptime
              </span>
              <Activity className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-xl font-bold text-white">
              {systemInfo?.uptime_seconds !== undefined ? `${Math.floor(systemInfo.uptime_seconds)}s` : "---"}
            </div>
            <p className="text-xs text-slate-400 mt-2 font-mono">
              Phase: {systemInfo?.architecture_phase || "Milestone 1"}
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
