"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { PasswordChangeForm } from "@/components/auth/password-change-form";

/**
 * Forced password-change screen. Reached when the backend reports
 * must_change_password (an administrator reset this user's password). The
 * backend independently denies protected endpoints until the change is made;
 * this page is the frontend's UX surface for completing it.
 */
export default function PasswordChangePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // If the backend does NOT require a change, an authenticated user has no
  // business here — send them to the dashboard.
  useEffect(() => {
    if (!isLoading && user && !user.must_change_password) {
      router.replace("/");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user || !user.must_change_password) {
    return null;
  }

  return (
    <div className="mx-auto w-full max-w-xl py-10">
      <div className="bg-card border border-amber-500/30 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-border bg-amber-500/5 flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
            <ShieldAlert className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              Password change required
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              An administrator reset your password. For security, you must
              choose a new password before accessing the platform. Sign in
              credentials entered here are transmitted securely and never
              stored.
            </p>
          </div>
        </div>
        <div className="px-6 py-6">
          <PasswordChangeForm mode="forced" />
        </div>
      </div>
    </div>
  );
}
