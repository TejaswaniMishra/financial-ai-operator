"use client";

import React, { useState, useEffect } from "react";
import { Search, Bell, Sun, Moon, Laptop, User } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

export function TopNav() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="h-16 border-b border-border bg-card sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Search / Command Palette Trigger */}
      <div className="flex-1 max-w-md hidden sm:block ml-12 lg:ml-0">
        <button
          className="w-full flex items-center px-4 py-2 text-[13px] text-muted-foreground bg-surface-muted/50 border border-border-subtle rounded-lg hover:bg-surface-muted hover:text-foreground transition-colors focus-ring"
          onClick={() => {
            // Trigger command palette event
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }));
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
                theme === "light" ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-surface-muted"
              )}
              title="Light Mode"
            >
              <Sun className="w-[18px] h-[18px]" />
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={cn(
                "p-2 rounded-full transition-colors focus-ring",
                theme === "dark" ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-surface-muted"
              )}
              title="Dark Mode"
            >
              <Moon className="w-[18px] h-[18px]" />
            </button>
          </div>
        )}

        <div className="h-6 w-px bg-border hidden sm:block mx-1"></div>

        {/* Profile Placeholder */}
        <div className="flex items-center space-x-3 pl-1 sm:pl-2">
          <div className="hidden md:block text-right">
            <p className="text-sm font-medium text-foreground leading-none">Operator</p>
            <p className="text-[11px] text-muted-foreground mt-1.5">Admin</p>
          </div>
          <button className="flex items-center justify-center w-9 h-9 rounded-full bg-surface-muted border border-border text-foreground hover:bg-border-subtle transition-colors focus-ring">
            <User className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>
    </header>
  );
}
