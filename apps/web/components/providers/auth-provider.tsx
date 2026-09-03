"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  type CurrentUser,
  type LoginRequest,
  type SignupRequest,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  fetchCurrentUser,
  UNAUTHORIZED_EVENT,
} from "@/lib/api";
import { validateNextParam } from "@/lib/server/redirect";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginRequest, next?: string) => Promise<void>;
  signup: (payload: SignupRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Routes that are fully public and must NOT trigger auth redirect
const PUBLIC_PATHS = new Set(["/login", "/signup"]);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  // Prevent double-fetching in StrictMode
  const fetchedRef = useRef(false);

  const loadCurrentUser = useCallback(async () => {
    try {
      const u = await fetchCurrentUser();
      setUser(u);
    } catch {
      // 401 or network error — user is not authenticated
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial auth check on mount
  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    loadCurrentUser();
  }, [loadCurrentUser]);

  // Listen for UNAUTHORIZED_EVENT dispatched by fetchAuthenticated helper in api.ts.
  // This handles expired/revoked tokens mid-session without polling.
  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setIsLoading(false);
      if (!PUBLIC_PATHS.has(pathname)) {
        const next = validateNextParam(pathname);
        router.replace(`/login${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`);
      }
    };

    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [pathname, router]);

  const login = useCallback(
    async (payload: LoginRequest, next?: string) => {
      await apiLogin(payload);
      const u = await fetchCurrentUser();
      setUser(u);
      const destination = validateNextParam(next ?? null);
      router.replace(destination);
    },
    [router]
  );

  const signup = useCallback(async (payload: SignupRequest) => {
    await apiSignup(payload);
    // Per spec: signup ? redirect to /login (backend did NOT authenticate)
    router.replace("/login");
  }, [router]);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
