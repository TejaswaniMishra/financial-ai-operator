"use client";

import React, { useEffect, useState } from "react";
import { User, Shield, KeyRound, Mail, BadgeCheck, Save, Loader2, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { updateProfile } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

export default function ProfilePage() {
  const { user, isLoading, refreshUser } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        </div>
      </section>
    </div>
  );
}