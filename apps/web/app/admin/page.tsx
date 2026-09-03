"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  UserCheck,
  ShieldCheck,
  AlertTriangle,
  Search,
  RefreshCw,
  ArrowRight,
  UserX,
  Eye,
} from "lucide-react";
import { cn, userInitials } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";
import {
  fetchAdminUsers,
  activateAdminUser,
  deactivateAdminUser,
  type AdminUser,
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

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium",
        ROLE_STYLES[role] || "bg-surface-muted text-secondary border border-border"
      )}
    >
      {role}
    </span>
  );
}

export default function AdminPage() {
  const { user, isLoading: authLoading } = useAuth();
  const canManageUsers = hasPermission(user, PERMISSIONS.MANAGE_USERS);
  const canManageRoles = hasPermission(user, PERMISSIONS.MANAGE_ROLES);
  const canAccessAdmin =
    !authLoading && (canManageUsers || canManageRoles);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Mutation targets
  const [deactivateTarget, setDeactivateTarget] = useState<AdminUser | null>(null);
  const [activateTarget, setActivateTarget] = useState<AdminUser | null>(null);
  const [rolesTarget, setRolesTarget] = useState<AdminUser | null>(null);
  const [mutatingId, setMutatingId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminUsers();
      setUsers(data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canAccessAdmin) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAccessAdmin]);

  if (authLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-1/3 bg-surface-muted rounded"></div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 bg-surface-muted rounded-xl"></div>
          ))}
        </div>
        <div className="h-96 w-full bg-surface-muted rounded-xl"></div>
      </div>
    );
  }

  if (!canAccessAdmin) {
    // Authenticated but lacking MANAGE_USERS/MANAGE_ROLES — stay on the page
    // with a clean permission-denied state (backend still enforces 403).
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

  const activeCount = users.filter((u) => u.is_active).length;
  const adminCount = users.filter((u) => u.roles.includes("ADMIN")).length;

  const filteredUsers = users.filter((u) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      u.email.toLowerCase().includes(q) ||
      u.display_name.toLowerCase().includes(q)
    );
  });

  const handleActivate = async (target: AdminUser) => {
    setMutatingId(target.id);
    setMutationError(null);
    try {
      await activateAdminUser(target.id);
      await loadData();
    } catch (err) {
      setMutationError(
        err instanceof Error ? err.message : "Failed to activate user."
      );
    } finally {
      setMutatingId(null);
      setActivateTarget(null);
    }
  };

  const handleDeactivate = async (target: AdminUser) => {
    setMutatingId(target.id);
    setMutationError(null);
    try {
      await deactivateAdminUser(target.id);
      await loadData();
    } catch (err) {
      setMutationError(
        err instanceof Error ? err.message : "Failed to deactivate user."
      );
    } finally {
      setMutatingId(null);
      setDeactivateTarget(null);
    }
  };

  const handleRolesSaved = async () => {
    setMutationError(null);
    await loadData();
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">User Management</h1>
        <p className="text-secondary max-w-2xl">
          Manage platform users, account status, and role assignments.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Total Users</h3>
            <Users className="w-4 h-4 text-primary" />
          </div>
          <div className="text-kpi">{loading ? "—" : users.length}</div>
          <p className="text-status text-muted-foreground mt-2">
            Registered accounts
          </p>
        </div>

        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Active Users</h3>
            <UserCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-kpi">{loading ? "—" : activeCount}</div>
          <p className="text-status text-muted-foreground mt-2">
            Can access the platform
          </p>
        </div>

        <div className="bg-card border border-border shadow-subtle rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-card-title text-sm">Admins</h3>
            <ShieldCheck className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-kpi">{loading ? "—" : adminCount}</div>
          <p className="text-status text-muted-foreground mt-2">
            Hold the ADMIN role
          </p>
        </div>
      </div>

      {mutationError && (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between shadow-subtle">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">{mutationError}</span>
          </div>
        </div>
      )}

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
      ) : loading ? (
        <div className="bg-card border border-border shadow-subtle rounded-xl p-6 space-y-3 animate-pulse">
          <div className="h-10 w-1/2 bg-surface-muted rounded" />
          <div className="h-8 w-full bg-surface-muted rounded" />
          <div className="h-8 w-full bg-surface-muted rounded" />
          <div className="h-8 w-full bg-surface-muted rounded" />
        </div>
      ) : users.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center border border-dashed border-border rounded-xl bg-surface/50 shadow-subtle">
          <Users className="w-10 h-10 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">
            No users found
          </h3>
          <p className="text-muted-foreground text-sm max-w-sm">
            There are currently no registered users.
          </p>
        </div>
      ) : (
        <div className="bg-card border border-border shadow-subtle rounded-xl overflow-hidden">
          {/* Toolbar */}
          <div className="p-4 sm:p-5 border-b border-border flex flex-col sm:flex-row gap-4 justify-between bg-surface-muted/30">
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm bg-surface border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground transition-all"
              />
            </div>
            <button
              onClick={loadData}
              className="inline-flex items-center justify-center px-3 py-2 text-sm font-medium text-secondary hover:text-foreground bg-surface border border-border rounded-md hover:border-border-subtle transition-colors"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-muted border-b border-border">
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">User</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Email</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Roles</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Status</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap">Created</th>
                  <th className="px-5 py-3 text-xs font-medium text-secondary uppercase tracking-wider whitespace-nowrap text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-sm text-muted-foreground">
                      No users match the current search.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((u) => {
                    const mutating = mutatingId === u.id;
                    const canEdit = canManageUsers || canManageRoles;
                    return (
                      <tr key={u.id} className="hover:bg-surface-muted/50 transition-colors">
                        <td className="px-5 py-3">
                          <div className="flex items-center space-x-3">
                            <div className="w-8 h-8 rounded-full bg-surface-muted border border-border flex items-center justify-center text-xs font-semibold text-foreground shrink-0">
                              {userInitials(u.display_name, u.email)}
                            </div>
                            <span className="font-medium text-sm text-foreground">
                              {u.display_name}
                            </span>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-sm text-muted-foreground">
                          {u.email}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {u.roles.length > 0 ? (
                              u.roles.map((r) => <RoleBadge key={r} role={r} />)
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-3 whitespace-nowrap">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-slate-500 dark:text-slate-400 text-xs font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                              Inactive
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-xs text-secondary whitespace-nowrap">
                          {u.created_at
                            ? new Date(u.created_at).toLocaleDateString()
                            : "—"}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center justify-end gap-2">
                            {canEdit && (
                              <>
                                {!u.is_active ? (
                                  <button
                                    onClick={() => setActivateTarget(u)}
                                    disabled={mutating}
                                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 rounded transition-colors disabled:opacity-50"
                                  >
                                    <UserCheck className="w-3.5 h-3.5 mr-1.5" />
                                    Activate
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => setDeactivateTarget(u)}
                                    disabled={mutating}
                                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-rose-600 dark:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 rounded transition-colors disabled:opacity-50"
                                  >
                                    <UserX className="w-3.5 h-3.5 mr-1.5" />
                                    Deactivate
                                  </button>
                                )}
                                {canManageRoles && (
                                  <button
                                    onClick={() => setRolesTarget(u)}
                                    disabled={mutating}
                                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-foreground bg-surface-muted hover:bg-surface-muted/80 border border-border rounded transition-colors disabled:opacity-50"
                                  >
                                    <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                                    Roles
                                  </button>
                                )}
                              </>
                            )}
                            <Link
                              href={`/admin/users/${u.id}`}
                              className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-primary bg-primary/5 hover:bg-primary/10 border border-primary/20 rounded transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5 mr-1.5" />
                              View
                              <ArrowRight className="w-3 h-3 ml-1.5" />
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Activation confirm (no warning required, but keep it explicit) */}
      <ConfirmDialog
        open={activateTarget !== null}
        title="Activate this user?"
        message={`${activateTarget?.display_name || activateTarget?.email || ""} will regain access to protected application features.`}
        confirmLabel="Activate"
        tone="primary"
        busy={mutatingId === activateTarget?.id}
        busyLabel="Activating..."
        onConfirm={() => activateTarget && handleActivate(activateTarget)}
        onClose={() => setActivateTarget(null)}
      />

      {/* Deactivation confirm */}
      <ConfirmDialog
        open={deactivateTarget !== null}
        title="Deactivate this user?"
        message="Deactivate this user? They will no longer be able to access protected application features."
        confirmLabel="Deactivate"
        tone="danger"
        busy={mutatingId === deactivateTarget?.id}
        busyLabel="Deactivating..."
        onConfirm={() => deactivateTarget && handleDeactivate(deactivateTarget)}
        onClose={() => setDeactivateTarget(null)}
      />

      {/* Role management */}
      {rolesTarget && (
        <ManageRolesModal
          user={rolesTarget}
          open
          onClose={() => setRolesTarget(null)}
          onSaved={handleRolesSaved}
        />
      )}
    </div>
  );
}