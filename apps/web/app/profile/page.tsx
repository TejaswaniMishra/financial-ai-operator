"use client";

import React, { useEffect, useState } from "react";
import { User, Shield, KeyRound, Mail, BadgeCheck, Save, Loader2, CheckCircle2, Smartphone, RefreshCw, XCircle } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import {
  updateProfile,
  mfaSetup,
  mfaVerifySetup,
  mfaDisable,
  mfaRegenerateCodes,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { PasswordChangeForm } from "@/components/auth/password-change-form";
export default function ProfilePage() {
  const { user, isLoading, refreshUser } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // MFA enrollment / management
  const [mfaStage, setMfaStage] = useState<
    "idle" | "setup" | "codes" | "disable" | "regenerate"
  >("idle");
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);
  const [mfaOtpauth, setMfaOtpauth] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaPassword, setMfaPassword] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [mfaBusy, setMfaBusy] = useState(false);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaNotice, setMfaNotice] = useState<string | null>(null);

  useEffect(() => {
    if (user) setDisplayName(user.display_name ?? user.email);
  }, [user]);

  async function handleSave() {
    const name = displayName.trim();
    if (!name) {
      setError("Display name cannot be empty.");
      return;
    }
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await updateProfile({ display_name: name });
      await refreshUser();
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  }

  // ─── MFA handlers ─────────────────────────────────────────────────────────
  async function startMfaSetup() {
    setMfaBusy(true);
    setMfaError(null);
    setMfaNotice(null);
    try {
      const res = await mfaSetup();
      setMfaSecret(res.secret);
      setMfaOtpauth(res.otpauth_url);
      setMfaCode("");
      setMfaStage("setup");
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Could not start enrollment.");
    } finally {
      setMfaBusy(false);
    }
  }

  async function confirmMfaSetup() {
    if (!mfaCode.trim()) {
      setMfaError("Enter the 6-digit code from your authenticator app.");
      return;
    }
    setMfaBusy(true);
    setMfaError(null);
    try {
      const codes = await mfaVerifySetup(mfaCode.trim());
      setRecoveryCodes(codes);
      setMfaStage("codes");
      await refreshUser();
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Invalid authenticator code.");
    } finally {
      setMfaBusy(false);
    }
  }

  function dismissMfaCodes() {
    setRecoveryCodes([]);
    setMfaSecret(null);
    setMfaOtpauth(null);
    setMfaCode("");
    setMfaPassword("");
    setMfaStage("idle");
  }

  async function confirmMfaDisable() {
    if (!mfaCode.trim()) {
      setMfaError("Enter a valid authenticator or recovery code to disable MFA.");
      return;
    }
    setMfaBusy(true);
    setMfaError(null);
    try {
      await mfaDisable(mfaCode.trim());
      setMfaCode("");
      setMfaStage("idle");
      setMfaNotice("MFA disabled. You can re-enable it at any time.");
      await refreshUser();
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Could not disable MFA.");
    } finally {
      setMfaBusy(false);
    }
  }

  async function confirmMfaRegenerate() {
    if (!mfaPassword) {
      setMfaError("Enter your account password to regenerate recovery codes.");
      return;
    }
    setMfaBusy(true);
    setMfaError(null);
    try {
      const codes = await mfaRegenerateCodes(mfaPassword);
      setRecoveryCodes(codes);
      setMfaStage("codes");
      setMfaPassword("");
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Could not regenerate codes.");
    } finally {
      setMfaBusy(false);
    }
  }

  function cancelMfaStage() {
    setMfaStage("idle");
    setMfaSecret(null);
    setMfaOtpauth(null);
    setMfaCode("");
    setMfaPassword("");
    setMfaError(null);
  }

  if (isLoading || !user) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <div className="space-y-4">
          <div className="w-48 h-8 rounded bg-surface-muted animate-pulse" />
          <div className="w-80 h-4 rounded bg-surface-muted animate-pulse" />
          <div className="h-64 rounded-xl bg-surface-muted animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Profile</h1>
        <p className="text-secondary">
          Your identity, roles, and account security. Roles are assigned by an
          administrator and cannot be changed here.
        </p>
      </div>

      {/* PERSONAL INFORMATION */}
      <section className="space-y-4">
        <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
          <User className="w-5 h-5 text-muted-foreground" />
          Personal Information
        </h2>
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="profile-display-name" className="text-muted-foreground">
              Display name
            </Label>
            <Input
              id="profile-display-name"
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value);
                setSaved(false);
              }}
              maxLength={255}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-muted-foreground">Email address</Label>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-10 rounded-md border border-input bg-surface-muted px-3 py-2 text-sm text-muted-foreground flex items-center gap-2">
                <Mail className="w-4 h-4" />
                {user.email}
              </div>
              <Badge tone="blue">Verified</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Email ownership changes require a verified flow and are not available here.
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertTitle>Unable to save</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {saved && (
            <Alert variant="success">
              <AlertTitle className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" /> Saved
              </AlertTitle>
              <AlertDescription>Your profile changes have been persisted.</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center gap-3 pt-1">
            <Button onClick={handleSave} disabled={saving || displayName.trim() === ""}>
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              {saving ? "Saving..." : "Save changes"}
            </Button>
            {saved && <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Saved to your account</span>}
          </div>
        </div>
      </section>

      {/* ROLES & ACCESS */}
      <section className="space-y-4">
        <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
          <Shield className="w-5 h-5 text-muted-foreground" />
          Roles &amp; Access
        </h2>
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            {user.roles.length > 0 ? (
              user.roles.map((role) => (
                <Badge key={role} variant="secondary">
                  {role}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">No roles assigned.</span>
            )}
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              {user.permissions.length} permission{user.permissions.length === 1 ? "" : "s"} resolved from your roles:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {user.permissions.map((p) => (
                <span
                  key={p}
                  className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-mono bg-surface-muted border border-border-subtle text-foreground"
                >
                  {p}
                </span>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Permissions are resolved from the database on every request — the frontend only displays them.
            </p>
          </div>
        </div>
      </section>

      {/* SECURITY */}
      <section className="space-y-4">
        <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
          <KeyRound className="w-5 h-5 text-muted-foreground" />
          Security
        </h2>
        <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden text-sm">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border">
            <span className="font-medium text-muted-foreground">Account status</span>
            {user.is_active ? (
              <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                Active
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-red-700 dark:text-red-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                Inactive
              </span>
            )}
          </div>
          <div className="flex justify-between items-center px-5 py-4 border-b border-border">
            <span className="font-medium text-muted-foreground">Session</span>
            <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
              <BadgeCheck className="w-4 h-4" />
              Authenticated
            </span>
          </div>
          <div className="flex justify-between items-center px-5 py-4 border-b border-border">
            <span className="font-medium text-muted-foreground">Token storage</span>
            <span className="text-foreground font-mono text-xs bg-surface-muted px-2 py-1 rounded border border-border-subtle">
              HttpOnly cookie
            </span>
          </div>
          <div className="flex justify-between items-center px-5 py-4">
            <span className="font-medium text-muted-foreground">Password hashing</span>
            <span className="text-foreground font-mono text-xs bg-surface-muted px-2 py-1 rounded border border-border-subtle">
              Argon2id
            </span>
          </div>
          {/* Change Password */}
          <div className="border-t border-border px-5 py-5 space-y-4">
            <div className="mb-2">
              <h3 className="text-sm font-medium text-foreground">
                Change password
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Enter your current password and a new one. After a successful change, all existing sessions will be signed out for security.
              </p>
            </div>
            <PasswordChangeForm mode="self" />
          </div>

          {/* MFA */}
          <div className="border-t border-border px-5 py-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-muted-foreground" />
                <span className="font-medium text-muted-foreground">
                  Two-factor authentication
                </span>
              </div>
              {user.mfa_enabled ? (
                <Badge tone="emerald">Enabled</Badge>
              ) : (
                <Badge variant="secondary">Disabled</Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground max-w-xl">
              {user.mfa_enabled
                ? "Sign-in requires a 6-digit code from your authenticator app or a one-time recovery code."
                : "Add an extra verification step at sign-in using a standard authenticator app."}
            </p>

            {mfaError && (
              <Alert variant="destructive">
                <AlertTitle>MFA error</AlertTitle>
                <AlertDescription>{mfaError}</AlertDescription>
              </Alert>
            )}
            {mfaNotice && (
              <Alert variant="success">
                <AlertDescription>{mfaNotice}</AlertDescription>
              </Alert>
            )}

            {/* Enrollment — secret + verification */}
            {mfaStage === "setup" && mfaSecret && (
              <div className="rounded-lg border border-border bg-surface-muted p-4 space-y-3">
                <div className="space-y-1">
                  <Label className="text-muted-foreground">Manual setup key</Label>
                  <code className="block text-xs font-mono bg-card border border-border-subtle rounded-md px-3 py-2 select-all break-all">
                    {mfaSecret}
                  </code>
                  {mfaOtpauth && (
                    <code className="block text-[10px] font-mono text-muted-foreground break-all">
                      {mfaOtpauth}
                    </code>
                  )}
                </div>
                <div className="space-y-1">
                  <Label htmlFor="mfa-setup-code" className="text-muted-foreground">
                    Enter the 6-digit code from your authenticator app
                  </Label>
                  <div className="flex gap-2 items-center">
                    <Input
                      id="mfa-setup-code"
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                      placeholder="000000"
                      inputMode="numeric"
                      className="w-44 font-mono"
                    />
                    <Button onClick={confirmMfaSetup} disabled={mfaBusy}>
                      {mfaBusy ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : null}
                      Verify &amp; enable
                    </Button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={cancelMfaStage}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel enrollment
                </button>
              </div>
            )}

            {/* Recovery codes — shown exactly once after enrollment/regeneration */}
            {mfaStage === "codes" && recoveryCodes.length > 0 && (
              <div className="rounded-lg border border-amber-600/40 bg-amber-50 dark:bg-amber-500/10 p-4 space-y-3">
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200 flex items-center gap-2">
                  <KeyRound className="w-4 h-4" />
                  Save these one-time recovery codes
                </p>
                <p className="text-xs text-amber-800 dark:text-amber-300">
                  Each code works exactly once and can only be used to sign in when
                  you do not have your authenticator. Store them somewhere safe —
                  they will not be shown again.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {recoveryCodes.map((c) => (
                    <code
                      key={c}
                      className="text-xs font-mono bg-white/70 dark:bg-card border border-amber-600/30 rounded-md px-2 py-1.5 text-center select-all"
                    >
                      {c}
                    </code>
                  ))}
                </div>
                <Button onClick={dismissMfaCodes} variant="outline">
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  I have saved my recovery codes
                </Button>
              </div>
            )}

            {/* Disable */}
            {mfaStage === "disable" && (
              <div className="rounded-lg border border-border bg-surface-muted p-4 space-y-2">
                <Label htmlFor="mfa-disable-code" className="text-muted-foreground">
                  Confirm with an authenticator or recovery code to disable MFA
                </Label>
                <div className="flex gap-2 items-center">
                  <Input
                    id="mfa-disable-code"
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    placeholder="000000"
                    inputMode="numeric"
                    className="w-44 font-mono"
                  />
                  <Button onClick={confirmMfaDisable} disabled={mfaBusy} variant="destructive">
                    {mfaBusy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Disable MFA
                  </Button>
                </div>
                <button
                  type="button"
                  onClick={cancelMfaStage}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Regenerate recovery codes */}
            {mfaStage === "regenerate" && (
              <div className="rounded-lg border border-border bg-surface-muted p-4 space-y-2">
                <Label htmlFor="mfa-regen-password" className="text-muted-foreground">
                  Enter your password to regenerate recovery codes
                </Label>
                <div className="flex gap-2 items-center">
                  <Input
                    id="mfa-regen-password"
                    type="password"
                    autoComplete="current-password"
                    value={mfaPassword}
                    onChange={(e) => setMfaPassword(e.target.value)}
                    className="w-56"
                  />
                  <Button onClick={confirmMfaRegenerate} disabled={mfaBusy}>
                    {mfaBusy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Regenerate
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Regenerating invalidates all previously issued recovery codes.
                </p>
                <button
                  type="button"
                  onClick={cancelMfaStage}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Actions */}
            {mfaStage === "idle" && !user.mfa_enabled && (
              <Button onClick={startMfaSetup} disabled={mfaBusy} variant="outline">
                <RefreshCw className="w-4 h-4 mr-2" />
                Enable MFA
              </Button>
            )}
            {mfaStage === "idle" && user.mfa_enabled && (
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => setMfaStage("disable")} variant="outline">
                  <XCircle className="w-4 h-4 mr-2" />
                  Disable MFA
                </Button>
                <Button onClick={() => setMfaStage("regenerate")} variant="outline">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate recovery codes
                </Button>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}