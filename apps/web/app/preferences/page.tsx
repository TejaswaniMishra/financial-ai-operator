"use client";

import React, { useEffect, useState } from "react";
import { Monitor, Moon, Sun, Check, Loader2, Bell } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";
import { fetchPreferences, updatePreferences } from "@/lib/api";

type ThemeChoice = "system" | "light" | "dark";

export default function PreferencesPage() {
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [serverTheme, setServerTheme] = useState<ThemeChoice>("system");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Load the server-authoritative preference (new browser sessions may not
  // have a local theme yet), then apply it so the UI matches the account.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const prefs = await fetchPreferences();
        if (cancelled) return;
        setServerTheme(prefs.theme);
        if (mounted && ["system", "light", "dark"].includes(prefs.theme)) {
          setTheme(prefs.theme);
        }
      } catch {
        // Backend unreachable — keep current local theme; user can still save.
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If the account preference changed elsewhere (e.g. another session),
  // reflect it when /me is refreshed.
  useEffect(() => {
    if (!mounted || !user?.preferences?.theme) return;
    const t = user.preferences.theme as ThemeChoice;
    if (["system", "light", "dark"].includes(t) && t !== serverTheme) {
      setServerTheme(t);
      setTheme(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleSelect(choice: ThemeChoice) {
    setServerTheme(choice);
    setTheme(choice);
    setSaveError(null);
    setSaving(true);
    try {
      await updatePreferences({ theme: choice });
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to persist preferences."
      );
    } finally {
      setSaving(false);
    }
  }

  const options: Array<{ value: ThemeChoice; label: string; icon: typeof Sun }> = [
    { value: "system", label: "System", icon: Monitor },
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
  ];

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-page-title">Preferences</h1>
        <p className="text-secondary">
          Account-level settings. Preferences are saved to your account and
          apply on every device after you sign in.
        </p>
      </div>

      {/* APPEARANCE */}
      <section className="space-y-4">
        <h2 className="text-section-heading flex items-center gap-2 border-b border-border pb-2">
          <Monitor className="w-5 h-5 text-muted-foreground" />
          Appearance
        </h2>
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-foreground">Theme</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Choose how the interface looks. Saved to your account and applied
              after sign-in on any device.
            </p>
          </div>

          {mounted ? (
            <div className="flex flex-wrap gap-4">
              {options.map((option) => {
                const selected = serverTheme === option.value;
                return (
                  <button
                    key={option.value}
                    onClick={() => handleSelect(option.value)}
                    disabled={saving}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-lg border transition-all focus-ring text-sm font-medium disabled:opacity-60",
                      selected
                        ? "border-primary bg-primary/5 text-primary shadow-sm"
                        : "border-border bg-card text-muted-foreground hover:bg-surface-muted hover:text-foreground hover:border-border-subtle"
                    )}
                    aria-pressed={selected}
                  >
                    <option.icon
                      className={cn(
                        "w-4 h-4",
                        selected ? "text-primary" : "text-muted-foreground"
                      )}
                    />
                    {option.label}
                    {selected && <Check className="w-4 h-4 ml-2" />}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="h-12 flex items-center space-x-4">
              <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
              <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
              <div className="w-24 h-12 rounded-lg bg-surface-muted animate-pulse"></div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Saving to your account…
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                Persisted to your account
              </>
            )}
          </div>
          {saveError && (
            <p className="mt-3 text-xs text-red-700 dark:text-red-400">
              {saveError}
            </p>
          )}
        </div>
      </section>

    </div>
  );
}