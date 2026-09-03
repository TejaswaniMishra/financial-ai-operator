"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  busy?: boolean;
  busyLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  busy = false,
  busyLabel = "Working...",
  tone = "danger",
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="px-6 py-4 border-b border-border flex items-center gap-3">
          <AlertTriangle
            className={
              tone === "danger"
                ? "w-5 h-5 text-rose-500"
                : "w-5 h-5 text-primary"
            }
          />
          <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        </div>
        <div className="p-6">
          <p className="text-sm text-secondary">{message}</p>
        </div>
        <div className="px-6 py-4 bg-surface-muted/50 border-t border-border flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={busy}
            className="px-4 py-2 text-sm font-medium text-secondary hover:text-foreground hover:bg-surface-muted rounded-md transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className={
              tone === "danger"
                ? "inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-md transition-colors shadow-sm disabled:opacity-50"
                : "inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm disabled:opacity-50"
            }
          >
            {busy && (
              <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
            )}
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}