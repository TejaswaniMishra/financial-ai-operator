"use client";

import React, { useState } from "react";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { updateAdminUserRoles, type AdminUser } from "@/lib/api";

const FIXED_ROLES = ["OPERATOR", "FINANCE_MANAGER", "ADMIN"] as const;

const ROLE_STYLES: Record<string, string> = {
  OPERATOR:
    "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20",
  FINANCE_MANAGER:
    "bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20",
  ADMIN:
    "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
};

interface ManageRolesModalProps {
  user: AdminUser;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function ManageRolesModal({
  user,
  open,
  onClose,
  onSaved,
}: ManageRolesModalProps) {
  const [selected, setSelected] = useState<string[]>(user.roles);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset local state each time the modal targets a different user
  const [targetId, setTargetId] = useState<string | null>(null);
  if (targetId !== user.id) {
    setTargetId(user.id);
    setSelected(user.roles);
    setError(null);
  }

  if (!open) return null;

  const grantingAdmin =
    !user.roles.includes("ADMIN") && selected.includes("ADMIN");

  const toggle = (role: string) => {
    setError(null);
    setSelected((prev) =>
      prev.includes(role)
        ? prev.filter((r) => r !== role)
        : [...prev, role]
    );
  };

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    try {
      await updateAdminUserRoles(user.id, selected);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update roles.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-primary" />
            Manage Roles
          </h3>
          <p className="text-sm text-secondary mt-1 truncate">
            {user.display_name || user.email}
          </p>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-xs text-muted-foreground">
            Role assignments are applied by the backend on save. Existing
            assignments are replaced.
          </p>

          <div className="space-y-2">
            {FIXED_ROLES.map((role) => (
              <label
                key={role}
                className={cn(
                  "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors",
                  selected.includes(role)
                    ? "border-primary/40 bg-primary/5"
                    : "border-border bg-surface hover:border-border-subtle"
                )}
              >
                <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="checkbox"
                    checked={selected.includes(role)}
                    onChange={() => toggle(role)}
                    className="accent-[var(--primary)]"
                  />
                  {role}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider",
                    ROLE_STYLES[role] ||
                      "bg-surface-muted text-secondary border border-border"
                  )}
                >
                  Fixed
                </span>
              </label>
            ))}
          </div>

          {grantingAdmin && (
            <div className="flex items-start gap-2 text-sm font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2.5 rounded-md">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              Granting ADMIN gives this user platform-management permissions.
              Continue?
            </div>
          )}

          {error && (
            <div className="text-sm font-medium text-destructive flex items-center gap-1.5 bg-destructive/10 px-3 py-2 rounded-md border border-destructive/20">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}
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
            onClick={handleSave}
            disabled={busy}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm disabled:opacity-50"
          >
            {busy && (
              <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
            )}
            {busy ? "Saving..." : "Save Roles"}
          </button>
        </div>
      </div>
    </div>
  );
}