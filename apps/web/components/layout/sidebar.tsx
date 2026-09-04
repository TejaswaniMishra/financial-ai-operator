"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Layers,
  ShieldCheck,
  Search,
  Database,
  BarChart3,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  CheckSquare,
  Calendar
} from "lucide-react";
import { cn, userInitials } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";

const navigation = [
  { name: "Dashboard", href: "/", icon: Activity },
  { name: "Reconciliation", href: "/reconciliation", icon: Layers },
  { name: "Discrepancies", href: "/discrepancies", icon: Search },
  { name: "Investigations", href: "/investigations", icon: ShieldCheck },
  { name: "Action Requests", href: "/action-requests", icon: CheckSquare },
  { name: "Transactions", href: "/transactions", icon: Database },
  { name: "Exceptions", href: "/exceptions", icon: FileText },
  { name: "Periods", href: "/periods", icon: Calendar },
  { name: "Reports", href: "/reports", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, isLoading } = useAuth();
  // Administration navigation appears only for users whose backend-resolved
  // permissions include user/role management — never for a hardcoded role.
  const canAdmin =
    hasPermission(user, PERMISSIONS.MANAGE_USERS) ||
    hasPermission(user, PERMISSIONS.MANAGE_ROLES);

  const toggleCollapse = () => setCollapsed(!collapsed);
  const toggleMobile = () => setMobileOpen(!mobileOpen);

  return (
    <>
      {/* Mobile Menu Button - Fixed outside the sidebar */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <button
          onClick={toggleMobile}
          className="p-2 rounded-md bg-sidebar border border-sidebar-border text-sidebar-foreground shadow-sm focus-ring transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 lg:hidden"
          onClick={toggleMobile}
        />
      )}

      {/* Sidebar Container */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-all duration-300 ease-in-out lg:translate-x-0 lg:static",
          collapsed ? "w-20" : "w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header / Logo */}
        <div className="flex items-center h-16 px-4 shrink-0">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0">
            <Activity className="w-5 h-5" />
          </div>
          {!collapsed && (
            <div className="ml-3 font-semibold text-[15px] tracking-tight whitespace-nowrap overflow-hidden">
              Financial AI Operator
            </div>
          )}
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.name}
                href={item.isComingSoon ? "#" : item.href}
                className={cn(
                  "flex items-center px-3 py-2.5 rounded-md transition-colors group relative",
                  isActive
                    ? "bg-sidebar-active text-sidebar-activeForeground font-medium"
                    : "text-sidebar-muted hover:bg-sidebar-muted/10 hover:text-sidebar-foreground",
                  item.isComingSoon && "opacity-75 cursor-default hover:bg-transparent"
                )}
                title={collapsed ? item.name : undefined}
                onClick={(e) => {
                  if (item.isComingSoon) {
                    e.preventDefault();
                  } else {
                    setMobileOpen(false);
                  }
                }}
              >
                <item.icon className={cn("w-4 h-4 shrink-0", isActive ? "text-sidebar-activeForeground" : "text-sidebar-muted group-hover:text-sidebar-foreground")} />
                {!collapsed && (
                  <span className="ml-3 text-sm flex-1">{item.name}</span>
                )}
                {!collapsed && item.isComingSoon && (
                  <span className="bg-primary/20 text-primary-foreground text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider font-semibold">
                    Soon
                  </span>
                )}
              </Link>
            );
          })}

          {canAdmin && (
            <div className="pt-6 pb-2">
              {!collapsed && (
                <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted/50 mb-2">Administration</div>
              )}
              <Link
                href="/admin"
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center px-3 py-2.5 rounded-md transition-colors group",
                  pathname === "/admin" || pathname?.startsWith("/admin/users")
                    ? "bg-sidebar-active text-sidebar-activeForeground font-medium"
                    : "text-sidebar-muted hover:bg-sidebar-muted/10 hover:text-sidebar-foreground"
                )}
                title={collapsed ? "User Management" : undefined}
              >
                <ShieldCheck className={cn("w-4 h-4 shrink-0", pathname === "/admin" || pathname?.startsWith("/admin/users") ? "text-sidebar-activeForeground" : "text-sidebar-muted group-hover:text-sidebar-foreground")} />
                {!collapsed && (
                  <span className="ml-3 text-sm flex-1">User Management</span>
                )}
              </Link>
              <Link
                href="/admin/security-events"
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center px-3 py-2.5 rounded-md transition-colors group mt-1.5",
                  pathname?.startsWith("/admin/security-events")
                    ? "bg-sidebar-active text-sidebar-activeForeground font-medium"
                    : "text-sidebar-muted hover:bg-sidebar-muted/10 hover:text-sidebar-foreground"
                )}
                title={collapsed ? "Security Events" : undefined}
              >
                <ShieldCheck className={cn("w-4 h-4 shrink-0", pathname?.startsWith("/admin/security-events") ? "text-sidebar-activeForeground" : "text-sidebar-muted group-hover:text-sidebar-foreground")} />
                {!collapsed && (
                  <span className="ml-3 text-sm flex-1">Security Events</span>
                )}
              </Link>
            </div>
          )}

          <div className="pt-6 pb-2">
            {!collapsed && <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted/50 mb-2">System</div>}
            <Link
              href="/settings"
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center px-3 py-2.5 rounded-md transition-colors group",
                pathname?.startsWith("/settings")
                  ? "bg-sidebar-active text-sidebar-activeForeground font-medium"
                  : "text-sidebar-muted hover:bg-sidebar-muted/10 hover:text-sidebar-foreground"
              )}
              title={collapsed ? "Settings" : undefined}
            >
              <Settings className={cn("w-4 h-4 shrink-0", pathname?.startsWith("/settings") ? "text-sidebar-activeForeground" : "text-sidebar-muted group-hover:text-sidebar-foreground")} />
              {!collapsed && (
                <span className="ml-3 text-sm flex-1">Settings</span>
              )}
            </Link>
          </div>
        </nav>

        {/* Bottom User Profile — identity comes from AuthProvider (backend /me), never hardcoded */}
        <div className="p-4 mt-auto shrink-0 border-t border-sidebar-border/50">
          <div className={cn("flex items-center", collapsed ? "justify-center" : "space-x-3")}>
            {isLoading || !user ? (
              <>
                <div className="w-9 h-9 rounded-full bg-sidebar-muted/20 animate-pulse shrink-0" />
                {!collapsed && (
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 w-24 rounded bg-sidebar-muted/20 animate-pulse" />
                    <div className="h-3 w-32 rounded bg-sidebar-muted/20 animate-pulse" />
                  </div>
                )}
              </>
            ) : (
              <>
                <div
                  className="w-9 h-9 rounded-full bg-sidebar-active/20 flex items-center justify-center shrink-0 border border-sidebar-active/30 text-sidebar-foreground font-semibold text-sm"
                  title={user.email}
                >
                  {userInitials(user.display_name, user.email)}
                </div>
                {!collapsed && (
                  <div className="flex-1 overflow-hidden">
                    <div className="text-sm font-medium text-sidebar-foreground truncate">
                      {user.display_name || user.email}
                    </div>
                    {/* Authoritative roles come from the backend /me contract.
                        Never hardcode or infer a role on the client. */}
                    {user.roles.length > 0 ? (
                      <div className="text-xs text-sidebar-muted truncate" title={user.roles.join(" · ")}>
                        {user.roles.join(" · ")}
                      </div>
                    ) : user.display_name ? (
                      <div className="text-xs text-sidebar-muted truncate">{user.email}</div>
                    ) : null}
                  </div>
                )}
              </>
            )}
          </div>
          
          {/* Collapse Toggle (Desktop Only) - Subtle bottom action */}
          <button
            onClick={toggleCollapse}
            className="hidden lg:flex w-full items-center justify-center p-2 mt-4 rounded-md text-sidebar-muted hover:bg-sidebar-muted/10 hover:text-sidebar-foreground transition-colors"
            title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </>
  );
}
