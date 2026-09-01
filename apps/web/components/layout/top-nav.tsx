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
    <header className="h-16 border-b border-border bg-surface/50 backdrop-blur-md sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Search / Command Palette Trigger */}
      <div className="flex-1 max-w-lg hidden sm:block ml-12 lg:ml-0">
        <button
          className="w-full flex items-center px-3 py-1.5 text-sm text-muted-foreground bg-background border border-border rounded-md hover:border-primary/50 hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20"
          onClick={() => {
            // Trigger command palette event
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }));
          }}
        >
          <Search className="w-4 h-4 mr-2" />
          <span>Search...</span>
          <div className="ml-auto flex items-center space-x-1 font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
            <span>⌘</span>
            <span>K</span>
          </div>
        </button>
      </div>

      <div className="flex items-center ml-auto space-x-4">
        {/* Notifications */}
        <button className="relative p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-muted transition-colors focus:outline-none">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-error border border-surface"></span>
        </button>

        {/* Theme Toggle */}
        {mounted && (
          <div className="flex items-center border border-border rounded-md bg-background overflow-hidden p-0.5">
            <button
              onClick={() => setTheme("light")}
              className={cn(
                "p-1.5 rounded-sm transition-colors",
                theme === "light" ? "bg-surface text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
              title="Light Mode"
            >
              <Sun className="w-4 h-4" />
            </button>
            <button
              onClick={() => setTheme("system")}
              className={cn(
                "p-1.5 rounded-sm transition-colors",
                theme === "system" ? "bg-surface text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
              title="System Theme"
            >
              <Laptop className="w-4 h-4" />
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={cn(
                "p-1.5 rounded-sm transition-colors",
                theme === "dark" ? "bg-surface text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
              title="Dark Mode"
            >
              <Moon className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Profile Placeholder */}
        <div className="flex items-center space-x-2 pl-4 border-l border-border">
          <button className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors focus:outline-none">
            <User className="w-4 h-4" />
          </button>
          <div className="hidden md:block text-sm">
            <p className="font-medium text-foreground leading-none">Operator</p>
            <p className="text-[11px] text-muted-foreground mt-1">Admin</p>
          </div>
        </div>
      </div>
    </header>
  );
}
