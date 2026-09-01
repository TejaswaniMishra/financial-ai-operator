"use client";

import React from "react";
import Link from "next/link";
import { 
  ArrowLeft, 
  ChevronRight, 
  Activity, 
  AlertTriangle,
  BrainCircuit,
  ShieldCheck,
  CheckCircle2,
  Clock,
  FileText
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function InvestigationDetailPage({ params }: { params: { id: string } }) {
  // Static placeholders for the shell
  const id = params.id;
  const isLoading = true;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center text-sm text-muted-foreground font-medium">
        <Link href="/" className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="hover:text-foreground transition-colors cursor-pointer">
          Investigations
        </span>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="text-foreground">Investigation Detail</span>
      </nav>

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link 
              href="/" 
              className="p-1 -ml-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-surface-muted focus-ring"
              aria-label="Back to Dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Investigation
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
              PENDING
            </span>
          </div>
          <div className="flex items-center text-sm text-muted-foreground font-mono mt-1 ml-9">
            {id}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Approval Action Area */}
          <button 
            disabled
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            <ShieldCheck className="w-4 h-4 mr-2" />
            Approve Investigation
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Overview and Evidence */}
        <div className="lg:col-span-1 space-y-6">
          {/* Overview Card */}
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <h2 className="text-card-title text-base mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-muted-foreground" />
              Overview
            </h2>
            <div className="space-y-4">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Status</div>
                <div className="font-medium text-sm text-secondary">
                  -- Loading --
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Created</div>
                <div className="font-medium text-sm text-secondary flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  -- Loading --
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Discrepancy ID</div>
                <div className="font-mono text-xs text-secondary truncate">
                  -- Loading --
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Active Attempt</div>
                <div className="font-mono text-xs text-secondary truncate">
                  -- Loading --
                </div>
              </div>
            </div>
          </div>

          {/* Evidence Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <h2 className="text-card-title text-base flex items-center gap-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                Discrepancy Evidence
              </h2>
            </div>
            <div className="p-6 text-center text-sm text-muted-foreground">
              Evidence details will appear here.
            </div>
          </div>
        </div>

        {/* Right Column: AI Investigation and Attempts */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* AI Investigation Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden flex flex-col min-h-[300px]">
            <div className="px-5 py-4 border-b border-border bg-surface-muted/30">
              <h2 className="text-card-title text-base flex items-center gap-2">
                <BrainCircuit className="w-5 h-5 text-primary" />
                AI Investigation Result
              </h2>
            </div>
            <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-full bg-surface-muted flex items-center justify-center mb-4">
                <BrainCircuit className="w-6 h-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-medium text-foreground mb-1">No results available yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm">
                Investigation results, resolution paths, and agent reasoning will be displayed here once an attempt completes.
              </p>
            </div>
          </div>

          {/* Investigation Attempts Section */}
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-card-title text-base">Investigation Attempts</h2>
            </div>
            <div className="p-0 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-surface-muted border-b border-border text-secondary">
                  <tr>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Attempt ID</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Model</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Prompt Version</th>
                    <th className="px-5 py-3 font-medium whitespace-nowrap">Validity</th>
                    <th className="px-5 py-3 font-medium text-right whitespace-nowrap">Created At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-secondary text-sm">
                      Loading attempts...
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
