"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Search, Sun, Moon, User, LogOut } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { NotificationCenter } from "@/components/layout/notification-center";

export function TopNav() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const { user, isLoading, logout } = useAuth();

  useEffect(() => {
    setMounted(true);
  }, []);

  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (
        profileRef.current &&
        !profileRef.current.contains(event.target as Node)
      ) {
        setIsProfileOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsProfileOpen(false);
      }
    };

    if (isProfileOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
      document.addEventListener("keydown", handleEscape);
    }
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isProfileOpen]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setIsProfileOpen(false);
    try {
      await logout();
    } finally {
      setIsLoggingOut(false);
    }
  };

  // Display name: prefer display_name, fall back to email, then generic fallback
  const displayName = user?.display_name || user?.email || "Operator";
  // Sub-label: email if we have a display_name, otherwise just empty
  const subLabel = user?.display_name ? user.email : null;

  // Apply the server-authoritative theme preference once identity loads
  // (covers fresh sessions on new devices where localStorage has no value).
  useEffect(() => {
    if (!mounted || !user?.preferences?.theme) return;
    const t = user.preferences.theme;
    if (t === "system" || t === "light" || t === "dark") {
      if (resolvedTheme !== t) setTheme(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, user]);

  return (
    <header className="h-16 border-b border-border bg-card sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Search / Command Palette Trigger */}
      <div className="flex-1 max-w-md hidden sm:block ml-12 lg:ml-0">
        <button
          className="w-full flex items-center px-4 py-2 text-[13px] text-muted-foreground bg-surface-muted/50 border border-border-subtle rounded-lg hover:bg-surface-muted hover:text-foreground transition-colors focus-ring"
          onClick={() => {
            document.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", metaKey: true }),
            );
          }}
        >
          <Search className="w-4 h-4 mr-2.5 text-muted-foreground/70" />
          <span>Search...</span>
          <div className="ml-auto flex items-center space-x-1 font-mono text-[10px] bg-background px-1.5 py-0.5 rounded text-muted-foreground border border-border-subtle shadow-sm">
            <span>⌘</span>
            <span>K</span>
          </div>
        </button>
      </div>

      <div className="flex items-center ml-auto space-x-2 sm:space-x-4">
        {/* Notifications */}
        <NotificationCenter />

        {/* Theme Toggle */}
        {mounted && (
          <div className="flex items-center space-x-1 hidden sm:flex">
            <button
              onClick={() => setTheme("light")}
              className={cn(
                "p-2 rounded-full transition-colors focus-ring",
                resolvedTheme === "light"
                  ? "text-primary bg-primary/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-muted",
              )}
              title="Light Mode"
            >
              <Sun className="w-[18px] h-[18px]" />
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={cn(
                "p-2 rounded-full transition-colors focus-ring",
                resolvedTheme === "dark"
                  ? "text-primary bg-primary/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-muted",
              )}
              title="Dark Mode"
            >
              <Moon className="w-[18px] h-[18px]" />
            </button>
          </div>
        )}

        <div className="h-6 w-px bg-border hidden sm:block mx-1"></div>

        {/* Profile Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center space-x-3 pl-1 sm:pl-2 rounded-md hover:bg-surface-muted p-1 -m-1 transition-colors focus-ring outline-none"
            aria-haspopup="true"
            aria-expanded={isProfileOpen}
            aria-label="User menu"
          >
            <div className="hidden md:block text-right">
              {isLoading ? (
                <>
                  <div className="w-20 h-3 rounded bg-surface-muted animate-pulse mb-1.5" />
                  <div className="w-14 h-2.5 rounded bg-surface-muted animate-pulse" />
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-foreground leading-none">
                    {displayName}
                  </p>
                  {subLabel && (
                    <p className="text-[11px] text-muted-foreground mt-1.5 truncate max-w-[140px]">
                      {subLabel}
                    </p>
                  )}
                </>
              )}
            </div>
            <div
              className={cn(
                "flex items-center justify-center w-9 h-9 rounded-full border text-foreground transition-colors",
                isProfileOpen
                  ? "bg-border-subtle border-border"
                  : "bg-surface-muted border-border",
              )}
            >
              <User className="w-4 h-4 text-muted-foreground" />
            </div>
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-card border border-border overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="px-4 py-3 border-b border-border bg-surface-muted/30">
                {user ? (
                  <>
                    <p className="text-sm font-medium text-foreground truncate">
                      {displayName}
                    </p>
                    {subLabel && (
                      <p className="text-xs text-muted-foreground mt-0.5 truncate">
                        {subLabel}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                )}
              </div>
              <div className="py-1">
                <Link
                  href="/profile"
                  onClick={() => setIsProfileOpen(false)}
                  className="w-full text-left px-4 py-2 text-sm text-foreground hover:bg-surface-muted transition-colors flex items-center justify-between group focus-visible:bg-surface-muted"
                >
                  <span>Profile</span>
                </Link>
                <Link
                  href="/preferences"
                  onClick={() => setIsProfileOpen(false)}
                  className="w-full text-left px-4 py-2 text-sm text-foreground hover:bg-surface-muted transition-colors flex items-center justify-between group focus-visible:bg-surface-muted"
                >
                  <span>Preferences</span>
                </Link>
              </div>
              <div className="border-t border-border py-1">
                <button
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="w-full text-left px-4 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors flex items-center gap-2 outline-none focus-visible:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  {isLoggingOut ? "Signing out..." : "Sign out"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}