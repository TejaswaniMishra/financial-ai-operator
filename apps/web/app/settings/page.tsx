"use client";

import React, { useState, useEffect } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun, User, Shield, Info, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    setMounted(true);
  }, []);

  const displayName = user?.display_name || user?.email || "—";
  const subLabel = user?.display_name ? user.email : null;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Settings</h1>
        <p className="text-secondary">
          Manage your application preferences and configuration.
        </p>
      </div>

      <div className="grid gap-8 max-w-4xl">
        {/* Section 1: Appearance */}
        <section className="space-y-4">
          <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
            <Monitor className="w-5 h-5 text-muted-foreground" />
            Appearance
          </h2>
          <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
            <div className="mb-4">
              <h3 className="text-sm font-medium text-foreground">
                Theme Preference
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Select your preferred color theme for the interface.
              </p>
            </div>

            {mounted ? (
              <div className="flex flex-wrap gap-4">
                {[
                  { value: "light", label: "Light", icon: Sun },
                  { value: "dark", label: "Dark", icon: Moon },
                  { value: "system", label: "System", icon: Monitor },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setTheme(option.value)}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-lg border transition-all focus-ring text-sm font-medium",
                      theme === option.value
                        ? "border-primary bg-primary/5 text-primary shadow-sm"
                        : "border-border bg-card text-muted-foreground hover:bg-surface-muted hover:text-foreground hover:border-border-subtle",
                    )}
                  >
                    <option.icon
                      className={cn(
                        "w-4 h-4",
                        theme === option.value
                          ? "text-primary"
                          : "text-muted-foreground",
                      )}
                    />
                    {option.label}
                    {theme === option.value && (
                      <Check className="w-4 h-4 ml-2" />
                    )}
                  </button>
                ))}
              </div>
            ) : (
              <div className="h-12 flex items-center space-x-4">
                <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
                <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
                <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
              </div>
            )}
          </div>
        </section>

        {/* Section 2: Operator Profile */}
        <section className="space-y-4">
          <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
            <User className="w-5 h-5 text-muted-foreground" />
            Operator Profile
          </h2>
          <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-surface-muted border border-border flex items-center justify-center shrink-0">
                <User className="w-6 h-6 text-muted-foreground" />
              </div>
              <div className="flex-1 space-y-1">
                {authLoading ? (
                  <>
                    <div className="w-32 h-4 rounded bg-surface-muted animate-pulse" />
                    <div className="w-48 h-3 rounded bg-surface-muted animate-pulse mt-2" />
                  </>
                ) : (
                  <>
                    <h3 className="text-base font-semibold text-foreground">
                      {displayName}
                    </h3>
                    {subLabel && (
                      <p className="text-sm text-muted-foreground">{subLabel}</p>
                    )}
                  </>
                )}
                <div className="mt-4 p-3 bg-surface-muted rounded-md text-xs text-muted-foreground border border-border-subtle inline-block">
                  Profile editing is not yet available.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Application */}
        <section className="space-y-4">
          <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
            <Info className="w-5 h-5 text-muted-foreground" />
            Application
          </h2>
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden text-sm">
            <div className="flex justify-between items-center px-5 py-4 border-b border-border">
              <span className="font-medium text-muted-foreground">Name</span>
              <span className="text-foreground font-semibold">
                Financial AI Operator
              </span>
            </div>
            <div className="flex justify-between items-center px-5 py-4">
              <span className="font-medium text-muted-foreground">
                Client Version
              </span>
              <span className="text-foreground font-mono text-xs bg-surface-muted px-2 py-1 rounded border border-border-subtle">
                v1.0.0
              </span>
            </div>
          </div>
        </section>

        {/* Section 4: Security / Authentication */}
        <section className="space-y-4">
          <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
            <Shield className="w-5 h-5 text-muted-foreground" />
            Security &amp; Authentication
          </h2>
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden text-sm">
            <div className="flex justify-between items-center px-5 py-4 border-b border-border">
              <span className="font-medium text-muted-foreground">Session</span>
              <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                Active
              </span>
            </div>
            <div className="flex justify-between items-center px-5 py-4 border-b border-border">
              <span className="font-medium text-muted-foreground">Token storage</span>
              <span className="text-foreground font-mono text-xs bg-surface-muted px-2 py-1 rounded border border-border-subtle">
                HttpOnly cookie
              </span>
            </div>
            <div className="flex justify-between items-center px-5 py-4 border-b border-border">
              <span className="font-medium text-muted-foreground">Password hashing</span>
              <span className="text-foreground font-mono text-xs bg-surface-muted px-2 py-1 rounded border border-border-subtle">
                Argon2id
              </span>
            </div>
            <div className="flex justify-between items-center px-5 py-4">
              <span className="font-medium text-muted-foreground">Multi-factor auth</span>
              <span className="text-[10px] uppercase tracking-wider font-semibold bg-primary/20 text-primary-foreground px-1.5 py-0.5 rounded">
                Not yet implemented
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
