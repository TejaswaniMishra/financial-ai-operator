import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

/**
 * Edge middleware: fast cookie-presence check before protected pages load.
 *
 * This is a FIRST LINE OF DEFENCE only — it checks the session cookie EXISTS.
 * It does NOT validate the token; the FastAPI backend is authoritative.
 *
 * Expired/revoked/invalid tokens are caught when the BFF proxy forwards the
 * request and receives a 401 from FastAPI, which triggers the
 * UNAUTHORIZED_EVENT in the browser client and clears the session.
 */

const PROTECTED_PATHS = [
  "/",
  "/reconciliation",
  "/discrepancies",
  "/investigations",
  "/settings",
  "/action-requests",
];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );
}

function isPublicPath(pathname: string): boolean {
  return (
    pathname.startsWith("/login") ||
    pathname.startsWith("/signup") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/favicon")
  );
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Never run auth checks on public or API paths
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Check protected routes
  if (isProtectedPath(pathname)) {
    const session = req.cookies.get(SESSION_COOKIE_NAME);
    if (!session?.value) {
      const loginUrl = req.nextUrl.clone();
      loginUrl.pathname = "/login";
      // Preserve the intended destination for post-login redirect
      if (pathname !== "/") {
        loginUrl.searchParams.set("next", pathname);
      }
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
