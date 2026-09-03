"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ChevronRight,
  Mail,
  Calendar,
  Clock,
  ShieldCheck,
  UserCheck,
  UserX,
  AlertTriangle,
  Users,
} from "lucide-react";
import { cn, userInitials } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";
import {
  fetchAdminUser,
  activateAdminUser,
  deactivateAdminUser,
  type AdminUserDetail,
} from "@/lib/api";
import { ManageRolesModal } from "@/components/admin/manage-roles-modal";
import { ConfirmDialog } from "@/components/admin/confirm-dialog";

const ROLE_STYLES: Record<string, string> = {
  OPERATOR:
    "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20",
  FINANCE_MANAGER:
    "bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20",
  ADMIN:
    "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
};

export default function AdminUserDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const id = params.id;
  const { user: currentUser, isLoading: authLoading } = useAuth();
  const canManageUsers = hasPermission(currentUser, PERMISSIONS.MANAGE_USERS);
  const canManageRoles = hasPermission(currentUser, PERMISSIONS.MANAGE_ROLES);
  const canAccessAdmin =
    !authLoading && (canManageUsers || canManageRoles);

  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [rolesModalOpen, setRolesModalOpen] = useState(false);
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await fetchAdminUser(id);
      setUser(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load user.";
      setError(message);
      setNotFound(/not found/i.test(message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (canAccessAdmin) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, canAccessAdmin]);

  const refreshUser = async () => {
    const data = await fetchAdminUser(id);
    setUser(data);
    setError(null);
  };

  const handleDeactivate = async () => {
    setBusy(true);
    setMutationError(null);
    try {
      const updated = await deactivateAdminUser(id);
      setUser(updated);
      setDeactivateOpen(false);
    } catch (err) {
      setMutationError(
        err instanceof Error ? err.message : "Failed to deactivate user."
      );
      setDeactivateOpen(false);
    } finally {
      setBusy(false);
    }
  };

  const handleActivate = async () => {
    setBusy(true);
    setMutationError(null);
    try {
      const updated = await activateAdminUser(id);
      setUser(updated);
      setActivateOpen(false);
    } catch (err) {
      setMutationError(
        err instanceof Error ? err.message : "Failed to activate user."
      );
      setActivateOpen(false);
    } finally {
      setBusy(false);
    }
  };

  const handleRolesSaved = async () => {
    setRolesModalOpen(false);
    try {
      await refreshUser();
    } catch (err) {
      setMutationError(
        err instanceof Error ? err.message : "Failed to refresh user."
      );
    }
  };

  if (authLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-1/4 bg-surface-muted rounded"></div>
        <div className="h-64 w-full max-w-3xl bg-surface-muted rounded-xl"></div>
      </div>
    );
  }

  if (!canAccessAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center border border-dashed border-border rounded-xl bg-surface/50 shadow-subtle">
        <ShieldCheck className="w-10 h-10 text-amber-500 mb-4" />
        <h1 className="text-xl font-semibold text-foreground mb-2">
          You don&apos;t have permission to view this page
        </h1>
        <p className="text-muted-foreground text-sm max-w-sm">
          User management requires the MANAGE_USERS or MANAGE_ROLES
          permission. Contact a platform administrator if you believe this is
          incorrect.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-1/4 bg-surface-muted rounded"></div>
        <div className="h-64 w-full max-w-3xl bg-surface-muted rounded-xl"></div>
      </div>
    );
  }

  if (error && !user) {
    return (
      <div className="space-y-6 pb-12">
        <nav className="flex items-center text-sm text-muted-foreground font-medium">
          <Link href="/admin" className="hover:text-foreground transition-colors">
            User Management
          </Link>
          <ChevronRight className="w-4 h-4 mx-2 text-border" />
          <span className="text-foreground">User</span>
        </nav>
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between shadow-subtle max-w-3xl">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">
              {notFound
                ? "User not found. It may have been removed or the ID is incorrect."
                : error}
            </span>
          </div>
          <Link
            href="/admin"
            className="px-4 py-1.5 bg-destructive/20 hover:bg-destructive/30 rounded text-sm font-medium transition-colors focus-ring"
          >
            Back to User Management
          </Link>
        </div>
      </div>
    );
  }

  if (!user) return null;

  const isSelf = currentUser?.id === user.id;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-muted-foreground font-medium">
        <Link href="/" className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <Link href="/admin" className="hover:text-foreground transition-colors">
          User Management
        </Link>
        <ChevronRight className="w-4 h-4 mx-2 text-border" />
        <span className="text-foreground">User Detail</span>
      </nav>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 max-w-5xl">
        <div className="flex items-center gap-4">
          <Link
            href="/admin"
            className="p-1 -ml-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-surface-muted"
            aria-label="Back to User Management"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="w-12 h-12 rounded-full bg-surface-muted border border-border flex items-center justify-center text-base font-semibold text-foreground shrink-0">
            {userInitials(user.display_name, user.email)}
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {user.display_name}
            </h1>
            <div className="flex items-center text-sm text-muted-foreground">
              <Mail className="w-3.5 h-3.5 mr-1.5" />
              {user.email}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {canManageUsers && (
            <>
              {user.is_active ? (
                <button
                  onClick={() => setDeactivateOpen(true)}
                  disabled={busy || isSelf}
                  className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-rose-600 bg-rose-500/10 hover:bg-rose-500/20 rounded-md transition-colors border border-rose-500/20 disabled:opacity-50"
                  title={
                    isSelf
                      ? "You cannot deactivate your own account."
                      : undefined
                  }
                >
                  <UserX className="w-4 h-4 mr-2" />
                  Deactivate
                </button>
              ) : (
                <button
                  onClick={() => setActivateOpen(true)}
                  disabled={busy}
                  className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors shadow-sm disabled:opacity-50"
                >
                  <UserCheck className="w-4 h-4 mr-2" />
                  Activate
                </button>
              )}
            </>
          )}
          {canManageRoles && (
            <button
              onClick={() => setRolesModalOpen(true)}
              disabled={busy}
              className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-foreground bg-surface-muted hover:bg-surface-muted/80 rounded-md transition-colors border border-border"
            >
              <ShieldCheck className="w-4 h-4 mr-2 text-primary" />
              Manage Roles
            </button>
          )}
        </div>
      </div>

      {mutationError && (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between shadow-subtle max-w-5xl">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">{mutationError}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl">
        {/* Left: identity card */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card border border-border rounded-lg shadow-subtle overflow-hidden">
            <div className="px-5 py-4 border-b border-border bg-surface-muted/30 flex items-center gap-2">
              <Users className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-card-title text-base">Account Details</h2>
            </div>
            <div className="p-0 divide-y divide-border">
              <div className="grid grid-cols-1 sm:grid-cols-2 p-5 gap-6">
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Display Name
                  </div>
                  <div className="font-medium text-sm text-foreground">
                    {user.display_name}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Email
                  </div>
                  <div className="font-medium text-sm text-foreground">
                    {user.email}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 p-5 gap-6 bg-surface-muted/10">
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Account Status
                  </div>
                  {user.is_active ? (
                    <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-slate-500 dark:text-slate-400 text-xs font-medium">
                      <span className="w-2 h-2 rounded-full bg-slate-400" />
                      Inactive
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Roles
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {user.roles.length > 0 ? (
                      user.roles.map((r) => (
                        <span
                          key={r}
                          className={cn(
                            "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium",
                            ROLE_STYLES[r] ||
                              "bg-surface-muted text-secondary border border-border"
                          )}
                        >
                          {r}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 p-5 gap-6">
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Created
                  </div>
                  <div className="font-medium text-sm text-foreground flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
                    {user.created_at
                      ? new Date(user.created_at).toLocaleString()
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">
                    Last Updated
                  </div>
                  <div className="font-medium text-sm text-foreground flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    {user.updated_at
                      ? new Date(user.updated_at).toLocaleString()
                      : "—"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: notes */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-card border border-border rounded-lg shadow-subtle p-5">
            <h2 className="text-card-title text-base mb-4 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-primary" />
              Access Notes
            </h2>
            <div className="space-y-3 text-xs text-muted-foreground">
              {isSelf && (
                <p className="text-amber-600 dark:text-amber-400 font-medium">
                  This is your own account. You cannot deactivate yourself.
                </p>
              )}
              <p>
                Deactivation is reversible and preserves the account&apos;s
                history. Deactivated users cannot authenticate.
              </p>
              <p>
                Role changes take effect on the user&apos;s next authenticated
                request — no new token is required.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <ConfirmDialog
        open={deactivateOpen}
        title="Deactivate this user?"
        message="Deactivate this user? They will no longer be able to access protected application features."
        confirmLabel="Deactivate"
        tone="danger"
        busy={busy}
        busyLabel="Deactivating..."
        onConfirm={handleDeactivate}
        onClose={() => setDeactivateOpen(false)}
      />
      <ConfirmDialog
        open={activateOpen}
        title="Activate this user?"
        message={`${user.display_name || user.email} will regain access to protected application features.`}
        confirmLabel="Activate"
        tone="primary"
        busy={busy}
        busyLabel="Activating..."
        onConfirm={handleActivate}
        onClose={() => setActivateOpen(false)}
      />
      {rolesModalOpen && (
        <ManageRolesModal
          user={user}
          open
          onClose={() => setRolesModalOpen(false)}
          onSaved={handleRolesSaved}
        />
      )}
    </div>
  );
}