"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Lock, Mail, User, Shield, AlertCircle, CheckCircle } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { cn } from "@/lib/utils";

export default function SignupPage() {
  const { signup, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  // If already authenticated, redirect away
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password || !confirmPassword) {
      setError("All fields are required.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      await signup({
        display_name: displayName.trim() || email.trim(),
        email: email.trim(),
        password,
        // NOTE: no role field — backend assigns roles
      });
      setSuccess(true);
      // Redirect to login after a short confirmation pause
      setTimeout(() => router.replace("/login"), 1500);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Registration failed. Please try again.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
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
            Join the platform
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            Create an account to access enterprise financial AI tooling.
            Your role will be assigned by your administrator.
          </p>
        </div>
        <p className="text-slate-600 text-xs">
          Financial AI Operator &copy; {new Date().getFullYear()}
        </p>
      </div>

      {/* Right Panel */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-2">
            <div className="flex lg:hidden items-center gap-2 mb-6">
              <Shield className="w-6 h-6 text-primary" />
              <span className="font-semibold text-foreground">Financial AI Operator</span>
            </div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              Create account
            </h1>
            <p className="text-sm text-muted-foreground">
              Fill in your details to register for access.
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Account created. Redirecting to sign in...</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <label htmlFor="display-name" className="text-sm font-medium text-foreground">
                Display name <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="display-name"
                  type="text"
                  autoComplete="name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  className={cn(
                    "w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
                  )}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="signup-email" className="text-sm font-medium text-foreground">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="signup-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className={cn(
                    "w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
                  )}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="signup-password" className="text-sm font-medium text-foreground">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="signup-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className={cn(
                    "w-full pl-10 pr-10 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="confirm-password" className="text-sm font-medium text-foreground">
                Confirm password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  id="confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat password"
                  className={cn(
                    "w-full pl-10 pr-10 py-2.5 text-sm rounded-lg border bg-background text-foreground",
                    "placeholder:text-muted-foreground/60",
                    "border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors",
                    confirmPassword && password !== confirmPassword
                      ? "border-destructive focus:ring-destructive/50"
                      : ""
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {confirmPassword && password !== confirmPassword && (
                <p className="text-xs text-destructive mt-1">Passwords do not match.</p>
              )}
            </div>

            <button
              id="signup-submit"
              type="submit"
              disabled={isSubmitting || success}
              className={cn(
                "w-full py-2.5 px-4 rounded-lg text-sm font-semibold text-white transition-all mt-2",
                "bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : (
                "Create account"
              )}
            </button>
          </form>

          <p className="text-sm text-center text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-primary font-medium hover:underline underline-offset-2"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}