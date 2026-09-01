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
  Menu
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/", icon: Activity },
  { name: "Reconciliation", href: "/reconciliation", icon: Layers },
  { name: "Discrepancies", href: "/discrepancies", icon: Search },
  { name: "Investigations", href: "/investigations", icon: ShieldCheck },
  { name: "Transactions", href: "/transactions", icon: Database },
  { name: "Reports", href: "/reports", icon: BarChart3 },
  { name: "Exceptions", href: "/exceptions", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapse = () => setCollapsed(!collapsed);
  const toggleMobile = () => setMobileOpen(!mobileOpen);

  return (
    <>
      {/* Mobile Menu Button - Fixed outside the sidebar */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <button
          onClick={toggleMobile}
          className="p-2 rounded-md bg-surface border border-border text-foreground shadow-sm hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary/20 transition-colors"
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
          "fixed inset-y-0 left-0 z-40 flex flex-col bg-surface border-r border-border transition-all duration-300 ease-in-out lg:translate-x-0 lg:static",
          collapsed ? "w-20" : "w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header / Logo */}
        <div className="flex items-center h-16 px-4 border-b border-border shrink-0">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0">
            <Activity className="w-5 h-5" />
          </div>
          {!collapsed && (
            <div className="ml-3 font-semibold text-sm tracking-tight text-foreground whitespace-nowrap overflow-hidden">
              FinOps Operator
            </div>
          )}
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center px-3 py-2.5 rounded-md transition-colors group relative",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
                title={collapsed ? item.name : undefined}
                onClick={() => setMobileOpen(false)}
              >
                <item.icon className={cn("w-5 h-5 shrink-0", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
                {!collapsed && <span className="ml-3 text-sm">{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Bottom Actions */}
        <div className="p-3 border-t border-border shrink-0 space-y-1">
          <Link
            href="/settings"
            className={cn(
              "flex items-center px-3 py-2.5 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors group",
              pathname?.startsWith("/settings") && "bg-primary/10 text-primary font-medium"
            )}
            title={collapsed ? "Settings" : undefined}
          >
            <Settings className="w-5 h-5 shrink-0" />
            {!collapsed && <span className="ml-3 text-sm">Settings</span>}
          </Link>
          
          {/* Collapse Toggle (Desktop Only) */}
          <button
            onClick={toggleCollapse}
            className="hidden lg:flex w-full items-center px-3 py-2.5 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            {collapsed ? (
              <ChevronRight className="w-5 h-5 mx-auto" />
            ) : (
              <>
                <ChevronLeft className="w-5 h-5 shrink-0" />
                <span className="ml-3 text-sm">Collapse</span>
              </>
            )}
          </button>
        </div>
      </div>
    </>
  );
}
