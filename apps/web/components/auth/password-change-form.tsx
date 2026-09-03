"use client";

import React, { useState } from "react";
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle2 } from "lucide-react";
import { changePassword, type ChangePasswordRequest } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { cn } from "@/lib/utils";

export const PASSWORD_MIN_LENGTH = 12;

interface PasswordChangeFormProps {
  /** "self" = normal self-service change (Settings). "forced" = the backend
   * requires a change before protected access (admin reset flow). */
  mode: "self" | "forced";
}

/**
 * Current + new + confirm password form that posts to the BFF
 * change-password endpoint. Never optimistically reports success: the
 * backend must confirm. On success the credential version is bumped and the
 * current session is invalid by design, so the user is signed out and must
 * sign in again with the new password.
 */
export function PasswordChangeForm({ mode }: PasswordChangeFormProps) {
  const { logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Client-side validation mirrors the backend's centralized policy
    // (12 characters minimum) — the backend remains authoritative.
    if (!currentPassword) {
      setError("Enter your current password.");
      return;
    }
    if (newPassword.length < PASSWORD_MIN_LENGTH) {
      setError(
        `New password must be at least ${PASSWORD_MIN_LENGTH} characters long.`
      );
      return;
    }
    if (newPassword === currentPassword) {
      setError("New password must be different from the current password.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: ChangePasswordRequest = {
        current_password: currentPassword,
        new_password: newPassword,
      };
      await changePassword(payload);
      setSuccess(true);
      // Clear all password state from the form — never retain credentials.
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      // The backend invalidated this session on success (credential version
      // bump). Sign out cleanly so the user re-authenticates with the new
      // password through the normal login flow.
      setTimeout(() => {
        void logout();
      }, 900);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Password change failed. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm flex items-start gap-3">
        <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium">
            {mode === "forced"
              ? "Password updated."
              : "Password changed successfully."}
          </p>
          <p className="mt-1 text-xs opacity-90">
            All existing sessions were signed out for security. Sign in again
            with your new password.
          </p>
        </div>
      </div>
    );
  }

  const inputClass = cn(
    "w-full pl-10 pr-10 py-2.5 text-sm rounded-lg border bg-background text-foreground",
    "placeholder:text-muted-foreground/60",
    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary",
    "transition-colors"
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      {error && (
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-1.5">
        <label
          htmlFor="current-password"
          className="text-sm font-medium text-foreground"
        >
          Current password
        </label>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            id="current-password"
            type={showCurrent ? "text" : "password"}
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="••••••••••••"
            className={inputClass}
          />
          <button
            type="button"
            onClick={() => setShowCurrent((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label={showCurrent ? "Hide current password" : "Show current password"}
          >
            {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="new-password" className="text-sm font-medium text-foreground">
          New password
        </label>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            id="new-password"
            type={showNew ? "text" : "password"}
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="••••••••••••"
            minLength={PASSWORD_MIN_LENGTH}
            className={inputClass}
          />
          <button
            type="button"
            onClick={() => setShowNew((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label={showNew ? "Hide new password" : "Show new password"}
          >
            {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          At least {PASSWORD_MIN_LENGTH} characters. Must differ from your
          current password.
        </p>
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="confirm-password"
          className="text-sm font-medium text-foreground"
        >
          Confirm new password
        </label>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            id="confirm-password"
            type={showNew ? "text" : "password"}
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••••••"
            className={inputClass}
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full sm:w-auto py-2.5 px-6 rounded-lg text-sm font-semibold text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {isSubmitting
          ? mode === "forced"
            ? "Updating password..."
            : "Changing password..."
          : mode === "forced"
            ? "Set new password"
            : "Update password"}
      </button>

      {mode === "self" && (
        <p className="text-xs text-muted-foreground">
          After a successful change, all existing sessions are signed out and
          you will need to sign in again.
        </p>
      )}
    </form>
  );
}
