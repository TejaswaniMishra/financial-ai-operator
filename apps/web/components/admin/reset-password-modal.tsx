"use client";

import React, { useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  ShieldAlert,
} from "lucide-react";
import {
  adminResetPassword,
  type AdminPasswordResetResult,
  type AdminUser,
} from "@/lib/api";

interface ResetPasswordModalProps {
  user: AdminUser;
  open: boolean;
  onClose: () => void;
}

/**
 * ADMIN-only password reset (MANAGE_USERS): confirm phase, then a result
 * phase showing the one-time temporary credential. The credential lives only
 * in React state — never in localStorage/sessionStorage, URLs, or console
 * logs — and disappears when the modal closes or the page changes.
 */
export function ResetPasswordModal({
  user,
  open,
  onClose,
}: ResetPasswordModalProps) {
  const [phase, setPhase] = useState<"confirm" | "result">("confirm");
  const [result, setResult] = useState<AdminPasswordResetResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Reset internal state every time the modal opens, so a previously shown
  // temporary credential is never re-displayed for a later session/user.
  const prevOpen = useRef(false);
  if (open && !prevOpen.current) {
    setPhase("confirm");
    setResult(null);
    setError(null);
    setCopied(false);
  }
  prevOpen.current = open;

  if (!open) return null;

  const handleReset = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await adminResetPassword(user.id);
      setResult(data);
      setPhase("result");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Password reset failed. Please try again."
      );
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.temporary_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (e.g. permissions) — leave manual copy to the admin
    }
  };

  const handleClose = () => {
    // Deliberately discard the one-time credential from component state.
    setPhase("confirm");
    setResult(null);
    setCopied(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="px-6 py-4 border-b border-border flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-500" />
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {phase === "confirm" ? "Reset password?" : "Temporary password generated"}
            </h3>
            <p className="text-xs text-muted-foreground truncate">
              {user.display_name || user.email}
            </p>
          </div>
        </div>

        {phase === "confirm" ? (
          <>
            <div className="p-6">
              <p className="text-sm text-secondary">
                Reset the password for{" "}
                <span className="font-medium text-foreground">
                  {user.display_name || user.email}
                </span>
                ? A secure temporary password will be generated and shown once.
              </p>
              <div className="mt-4 flex items-start gap-2 text-sm text-rose-600 dark:text-rose-400 bg-rose-500/10 border border-rose-500/20 px-3 py-2.5 rounded-md">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                This signs the user out of every existing session. They must
                change the temporary password before accessing the platform
                again.
              </div>
              {error && (
                <div className="mt-4 text-sm font-medium text-destructive flex items-center gap-1.5 bg-destructive/10 px-3 py-2 rounded-md border border-destructive/20">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}
            </div>
            <div className="px-6 py-4 bg-surface-muted/50 border-t border-border flex items-center justify-end gap-3">
              <button
                onClick={handleClose}
                disabled={busy}
                className="px-4 py-2 text-sm font-medium text-secondary hover:text-foreground hover:bg-surface-muted rounded-md transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                disabled={busy}
                className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-md transition-colors shadow-sm disabled:opacity-50"
              >
                {busy && (
                  <div className="w-4 h-4 mr-2 border-2 border-white/60 border-t-white rounded-full animate-spin"></div>
                )}
                {busy ? "Resetting..." : "Reset Password"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="p-6 space-y-4">
              {result && (
                <>
                  <div className="flex items-start gap-2 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-2.5 rounded-md">
                    <Check className="w-4 h-4 shrink-0 mt-0.5" />
                    {result.message}
                  </div>

                  <div>
                    <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                      Temporary password — shown once
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 font-mono text-sm bg-surface-muted border border-border rounded-md px-3 py-2.5 select-all break-all">
                        {result.temporary_password}
                      </code>
                      <button
                        onClick={handleCopy}
                        className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-foreground bg-surface-muted hover:bg-surface-muted/80 rounded-md border border-border transition-colors"
                        aria-label="Copy temporary password"
                        title="Copy temporary password"
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2.5 rounded-md">
                    <KeyRound className="w-4 h-4 shrink-0 mt-0.5" />
                    <ul className="list-disc ml-4 space-y-1 text-xs">
                      <li>Hand this password to the user securely.</li>
                      <li>
                        It is temporary: the user is forced to change it on
                        next sign-in.
                      </li>
                      <li>
                        It will not be shown again — copy it before closing.
                      </li>
                    </ul>
                  </div>
                </>
              )}
            </div>
            <div className="px-6 py-4 bg-surface-muted/50 border-t border-border flex items-center justify-end gap-3">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm"
              >
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
