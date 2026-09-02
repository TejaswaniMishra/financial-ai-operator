"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, Bell, Sun, Moon, Laptop, User } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

export function TopNav() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const [isProfileOpen, setIsProfileOpen] = useState(false);
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

  return (
    <header className="h-16 border-b border-border bg-card sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Search / Command Palette Trigger */}
      <div className="flex-1 max-w-md hidden sm:block ml-12 lg:ml-0">
        <button
          className="w-full flex items-center px-4 py-2 text-[13px] text-muted-foreground bg-surface-muted/50 border border-border-subtle rounded-lg hover:bg-surface-muted hover:text-foreground transition-colors focus-ring"
          onClick={() => {
            // Trigger command palette event
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
        <button className="relative p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-surface-muted transition-colors focus-ring">
          <Bell className="w-[18px] h-[18px]" />
          <span className="absolute top-1.5 right-2 w-1.5 h-1.5 rounded-full bg-error ring-2 ring-card"></span>
        </button>

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
          >
            <div className="hidden md:block text-right">
              <p className="text-sm font-medium text-foreground leading-none">
                Operator
              </p>
              <p className="text-[11px] text-muted-foreground mt-1.5">Admin</p>
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
                <p className="text-sm font-medium text-foreground">Arjun Rao</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Finance Manager
                </p>
              </div>
              <div className="py-1">
                <button
                  disabled
                  className="w-full text-left px-4 py-2 text-sm text-foreground hover:bg-surface-muted transition-colors flex items-center justify-between group opacity-75 cursor-default hover:bg-transparent outline-none focus-visible:bg-surface-muted"
                >
                  <span>Profile</span>
                  <span className="text-[10px] uppercase tracking-wider font-semibold bg-primary/20 text-primary-foreground px-1.5 py-0.5 rounded">
                    Soon
                  </span>
                </button>
                <button
                  disabled
                  className="w-full text-left px-4 py-2 text-sm text-foreground hover:bg-surface-muted transition-colors flex items-center justify-between group opacity-75 cursor-default hover:bg-transparent outline-none focus-visible:bg-surface-muted"
                >
                  <span>Preferences</span>
                  <span className="text-[10px] uppercase tracking-wider font-semibold bg-primary/20 text-primary-foreground px-1.5 py-0.5 rounded">
                    Soon
                  </span>
                </button>
              </div>
              <div className="border-t border-border py-1">
                <button
                  disabled
                  className="w-full text-left px-4 py-2 text-sm text-destructive transition-colors flex items-center justify-between group opacity-75 cursor-default outline-none focus-visible:bg-destructive/10"
                >
                  <span>Sign out</span>
                  <span className="text-[10px] uppercase tracking-wider font-semibold bg-primary/20 text-primary-foreground px-1.5 py-0.5 rounded">
                    Soon
                  </span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
