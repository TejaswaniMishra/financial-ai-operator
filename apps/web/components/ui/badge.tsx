import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "error" | "info";
  /**
   * Soft (tinted) status tone. Theme-aware: dark text on light backgrounds,
   * light text on dark backgrounds. Use this for status pills and type badges
   * so the same component is readable in both themes.
   */
  tone?: "neutral" | "blue" | "amber" | "violet" | "emerald" | "cyan" | "indigo" | "purple" | "red" | "rose";
}

function Badge({ className, variant = "default", tone, ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-primary text-primary-foreground",
    secondary: "border-transparent bg-secondary text-secondary-foreground",
    outline: "text-foreground",
    success: "border-transparent bg-success text-success-foreground",
    warning: "border-transparent bg-warning text-warning-foreground",
    error: "border-transparent bg-error text-error-foreground",
    info: "border-transparent bg-info text-info-foreground",
  };

  const tones = {
    neutral: "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300",
    blue: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    amber: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    violet: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
    emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    cyan: "border-cyan-500/30 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
    indigo: "border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
    purple: "border-purple-500/30 bg-purple-500/10 text-purple-700 dark:text-purple-300",
    red: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
    rose: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2",
        tone ? "font-medium " + tones[tone] : "font-semibold " + variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };