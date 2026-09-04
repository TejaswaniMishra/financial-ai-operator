"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Filter,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  FileSearch,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DiscrepancyResponse,
  fetchReconciliationDiscrepancies,
  runInvestigation,
} from "../../lib/api";

function formatCurrency(amount: number | string, currency: string) {
  try {
    // Backend Decimal amounts arrive as JSON strings — coerce for formatting.
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(Number(amount));
  } catch (e) {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
}

function SeverityBadge({ severity }: { severity: string }) {
  switch (severity.toUpperCase()) {
    case "HIGH":
    case "CRITICAL":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-error/10 text-error-foreground border border-error/20">
          {severity}
        </span>
      );
    case "MEDIUM":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-warning/10 text-warning border border-warning/20">
          {severity}
        </span>
      );
    case "LOW":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info/10 text-info border border-info/20">
          {severity}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-muted text-foreground border border-border">
          {severity}
        </span>
      );
  }
}

export default function DiscrepanciesPage() {
  const router = useRouter();

  const [discrepancies, setDiscrepancies] = useState<DiscrepancyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");

  const [investigatingIds, setInvestigatingIds] = useState<Set<string>>(
    new Set(),
  );
  const [investigationError, setInvestigationError] = useState<string | null>(
    null,
  );
  // Ref mirror of in-flight runs: guards against duplicate requests from rapid
  // repeated clicks before React has committed the disabled state.
  const investigatingRef = useRef<Set<string>>(new Set());

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReconciliationDiscrepancies();
      setDiscrepancies(data || []);
    } catch (err: any) {
      setError(err.message || "Failed to load discrepancies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleInvestigate = async (id: string) => {
    if (investigatingIds.has(id) || investigatingRef.current.has(id)) return;
    investigatingRef.current.add(id);

    setInvestigatingIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
    setInvestigationError(null);

    try {
      const result = await runInvestigation(id);
      router.push(`/investigations/${result.investigation_id}`);
    } catch (err: any) {
      setInvestigationError(err.message || "Failed to start investigation");
      investigatingRef.current.delete(id);
      setInvestigatingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // Derived metrics and filters
  const uniqueSeverities = useMemo(
    () => Array.from(new Set(discrepancies.map((d) => d.severity))),
    [discrepancies],
  );
  const uniqueTypes = useMemo(
    () => Array.from(new Set(discrepancies.map((d) => d.discrepancy_type))),
    [discrepancies],
  );

  const filteredData = useMemo(() => {
    return discrepancies.filter((d) => {
      if (severityFilter !== "ALL" && d.severity !== severityFilter)
        return false;
      if (typeFilter !== "ALL" && d.discrepancy_type !== typeFilter)
        return false;

      if (search) {
        const q = search.toLowerCase();
        const matches =
          d.rule_code.toLowerCase().includes(q) ||
          d.discrepancy_type.toLowerCase().includes(q) ||
          d.source_entity_id.toLowerCase().includes(q) ||
          (d.related_entity_id &&
            d.related_entity_id.toLowerCase().includes(q));
        if (!matches) return false;
      }
      return true;
    });
  }, [discrepancies, search, severityFilter, typeFilter]);

  const totalCriticalHigh = discrepancies.filter((d) =>
    ["CRITICAL", "HIGH"].includes(d.severity.toUpperCase()),
  ).length;

  // Calculate total absolute difference if possible
  const totalDifference = useMemo(() => {
    let sum = 0;
    discrepancies.forEach((d) => {
      if (d.difference_amount !== null) sum += Math.abs(Number(d.difference_amount));
    });
    return sum;
  }, [discrepancies]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-12 w-1/3 bg-surface-muted rounded"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-24 bg-surface-muted rounded-xl"></div>
          <div className="h-24 bg-surface-muted rounded-xl"></div>
          <div className="h-24 bg-surface-muted rounded-xl"></div>
        </div>
        <div className="h-96 w-full bg-surface-muted rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Discrepancies</h1>
        <p className="text-secondary max-w-2xl">
          Review exceptions and mismatched records identified during
          reconciliation. Investigate these discrepancies to resolve underlying
          data issues.
        </p>
      </div>

      {error ? (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between shadow-subtle">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button
            onClick={loadData}
            className="px-4 py-1.5 bg-destructive/20 hover:bg-destructive/30 rounded text-sm font-medium transition-colors focus-ring"
          >
            Retry
          </button>
        </div>
      ) : discrepancies.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center border border-dashed border-border rounded-xl bg-surface/50 shadow-subtle">
          <FileSearch className="w-10 h-10 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">
            No active discrepancies
          </h3>
          <p className="text-muted-foreground text-sm max-w-sm">
            All reconciliation runs are clean. There are no exceptions requiring
            your attention at this time.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
            <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-card-title text-sm">Total Discrepancies</h3>
                <AlertCircle className="w-4 h-4 text-discrepancy" />
              </div>
              <div className="text-kpi">{discrepancies.length}</div>
              <p className="text-status text-muted-foreground mt-2">
                Active exceptions
              </p>
            </div>

            <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-card-title text-sm">
                  Critical / High Severity
                </h3>
                <AlertTriangle className="w-4 h-4 text-error" />
              </div>
              <div className="text-kpi">{totalCriticalHigh}</div>
              <p className="text-status text-muted-foreground mt-2">
                Require immediate action
              </p>
            </div>

            <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-card-title text-sm">Absolute Exposure</h3>
                <span className="w-4 h-4 text-secondary font-serif italic flex items-center justify-center">
                  $
                </span>
              </div>
              <div className="text-kpi">
                {totalDifference > 0
                  ? formatCurrency(totalDifference, "USD")
                  : "$0.00"}
              </div>
              <p className="text-status text-muted-foreground mt-2">
                Total unresolved value
              </p>
            </div>
          </div>

          <div className="bg-card border border-border shadow-subtle rounded-xl overflow-hidden flex flex-col">
            {/* Toolbar */}
            <div className="p-4 sm:p-5 border-b border-border flex flex-col sm:flex-row gap-4 justify-between bg-surface-muted/30">
              <div className="relative w-full sm:max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search rules, entities..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground transition-all"
                />
              </div>
              <div className="flex items-center gap-3 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
                <div className="flex items-center space-x-2 shrink-0">
                  <Filter className="w-4 h-4 text-muted-foreground" />
                  <select
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                    className="text-sm bg-surface border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    <option value="ALL">All Severities</option>
                    {uniqueSeverities.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="shrink-0">
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="text-sm bg-surface border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 max-w-[150px] sm:max-w-[200px]"
                  >
                    <option value="ALL">All Types</option>
                    {uniqueTypes.map((t) => (
                      <option key={t} value={t}>
                        {t.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {investigationError && (
              <div className="px-5 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{investigationError}</span>
                </div>
                <button
                  onClick={() => setInvestigationError(null)}
                  className="text-xs font-medium px-2 py-1 bg-destructive/20 hover:bg-destructive/30 rounded transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">
                      Severity
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">
                      Type & Rule
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">
                      Source Entity
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">
                      Related Entity
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">
                      Difference
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">
                      Created
                    </th>
                    <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredData.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-5 py-8 text-center text-sm text-muted-foreground"
                      >
                        No discrepancies match the current filters.
                      </td>
                    </tr>
                  ) : (
                    filteredData.map((disc) => (
                      <tr
                        key={disc.id}
                        className="hover:bg-surface-muted/50 transition-colors group"
                      >
                        <td className="px-5 py-3 whitespace-nowrap">
                          <SeverityBadge severity={disc.severity} />
                        </td>
                        <td className="px-5 py-3">
                          <div className="font-medium text-sm text-foreground">
                            {disc.discrepancy_type.replace(/_/g, " ")}
                          </div>
                          <div className="text-xs text-muted-foreground font-mono mt-0.5">
                            {disc.rule_code}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <div className="font-medium text-xs text-foreground">
                            {disc.source_entity_type}
                          </div>
                          <div
                            className="text-xs text-muted-foreground font-mono mt-0.5"
                            title={disc.source_entity_id}
                          >
                            {disc.source_entity_id.length > 12
                              ? `${disc.source_entity_id.substring(0, 12)}...`
                              : disc.source_entity_id}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          {disc.related_entity_type ? (
                            <>
                              <div className="font-medium text-xs text-foreground">
                                {disc.related_entity_type}
                              </div>
                              <div
                                className="text-xs text-muted-foreground font-mono mt-0.5"
                                title={disc.related_entity_id || ""}
                              >
                                {disc.related_entity_id &&
                                disc.related_entity_id.length > 12
                                  ? `${disc.related_entity_id.substring(0, 12)}...`
                                  : disc.related_entity_id}
                              </div>
                            </>
                          ) : (
                            <span className="text-muted-foreground text-xs">
                              —
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-right whitespace-nowrap">
                          {disc.difference_amount !== null ? (
                            <div className="font-mono text-sm font-semibold text-discrepancy">
                              {formatCurrency(
                                disc.difference_amount,
                                disc.currency || "USD",
                              )}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-right font-mono text-xs text-secondary whitespace-nowrap">
                          {new Date(disc.created_at).toLocaleString()}
                        </td>
                        <td className="px-5 py-3 text-right whitespace-nowrap">
                          <button
                            onClick={() => handleInvestigate(disc.id)}
                            disabled={investigatingIds.has(disc.id)}
                            className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded transition-colors focus-ring disabled:opacity-50 shadow-sm"
                          >
                            {investigatingIds.has(disc.id) ? (
                              <>
                                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                                Starting...
                              </>
                            ) : (
                              <>
                                Investigate
                                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                              </>
                            )}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
