"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, KeyRound, Lock, Mail, Shield, AlertCircle } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { cn } from "@/lib/utils";

function LoginForm() {
  const { login, completeMfaLogin, user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextParam = searchParams.get("next");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // MFA second stage — a challenge token, held in React state only. It is
  // short-lived (15 min), single-use, and grants access to nothing by itself.
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);

  // If already authenticated, redirect away — EXCEPT when the backend has
  // flagged a forced password change (admin reset): the AuthProvider routes
  // those users to /password-change, so this effect must not yank them to "/"
  // and race that redirect.
  useEffect(() => {
    if (!isLoading && isAuthenticated && user && !user.must_change_password) {
      router.replace(nextParam ?? "/");
    }
  }, [isLoading, isAuthenticated, user, router, nextParam]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      const outcome = await login(
        { email: email.trim(), password },
        nextParam ?? undefined
      );
      if (outcome.mfa_required && outcome.mfa_token) {
        setMfaToken(outcome.mfa_token);
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Invalid email or password";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!mfaToken || !code.trim()) {
      setError("Enter the code from your authenticator app.");
      return;
    }
    setIsVerifyingCode(true);
    try {
      await completeMfaLogin(mfaToken, code.trim(), nextParam ?? undefined);
    } catch (err: unknown) {
      // The backend challenge token stays valid after a wrong code (it is
      // revoked only on success), so the user can retry without re-entering
      // credentials.
      const msg = err instanceof Error ? err.message : "Invalid code.";
      setError(msg);
    } finally {
      setIsVerifyingCode(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-[hsl(222,47%,11%)] flex-col items-start justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <span className="text-white font-semibold text-lg tracking-tight">
            Financial AI Operator
          </span>
        </div>
        <div className="space-y-4 max-w-sm">
          <h2 className="text-2xl font-semibold text-white leading-snug">
            Autonomous FinOps, powered by AI
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            Reconciliation, discrepancy investigation, and policy-governed action
            execution — governed, auditable, and enterprise-ready.
          </p>
        </div>
        <p className="text-slate-600 text-xs">
          Financial AI Operator &copy; {new Date().getFullYear()}
        </p>
      </div>

      {/* Right Panel */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-8">
          {/* Header */}
          <div className="space-y-2">
            <div className="flex lg:hidden items-center gap-2 mb-6">
              <Shield className="w-6 h-6 text-primary" />
              <span className="font-semibold text-foreground">Financial AI Operator</span>
            </div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              {mfaToken ? "Two-factor authentication" : "Sign in"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {mfaToken
                ? `Enter the 6-digit code from your authenticator app for ${email.trim()}.`
                : "Enter your credentials to access the platform."}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Form — credentials step, or MFA code step after a challenge */}
          {mfaToken ? (
            <form onSubmit={handleCodeSubmit} className="space-y-5" noValidate>
              <div className="space-y-1.5">
                <label
                  htmlFor="mfa-code"
                  className="text-sm font-medium text-foreground"
                >
                  Authenticator code
                </label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                  <input
                    id="mfa-code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="000000"
                    className={cn(
                      "w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                      "placeholder:text-muted-foreground/60",
                      "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary",
                      "transition-colors"
                    )}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Lost your authenticator? Enter one of your one-time recovery
                  codes instead.
                </p>
              </div>

              <button
                id="mfa-submit"
                type="submit"
                disabled={isVerifyingCode}
                className={cn(
                  "w-full py-2.5 px-4 rounded-lg text-sm font-semibold text-white transition-all",
                  "bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                {isVerifyingCode ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Verifying...
                  </span>
                ) : (
                  "Verify & sign in"
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setMfaToken(null);
                  setCode("");
                  setError(null);
                }}
                className="w-full text-center text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Back to sign in
              </button>
            </form>
          ) : (
            <>
            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="text-sm font-medium text-foreground"
              >
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className={cn(
                    "w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary",
                    "transition-colors"
                  )}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="text-sm font-medium text-foreground"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className={cn(
                    "w-full pl-10 pr-10 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary",
                    "transition-colors"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              id="login-submit"
              type="submit"
              disabled={isSubmitting}
              className={cn(
                "w-full py-2.5 px-4 rounded-lg text-sm font-semibold text-white transition-all",
                "bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                "Sign in"
              )}
            </button>
            </form>

            <p className="text-sm text-center text-muted-foreground">
              No account?{" "}
              <Link
                href="/signup"
                className="text-primary font-medium hover:underline underline-offset-2"
              >
                Create account
              </Link>
            </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen bg-background">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}