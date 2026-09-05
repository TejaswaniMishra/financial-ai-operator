import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "fao_session";

// These are the only backend paths this proxy is allowed to reach.
const ALLOWED_BACKEND_PREFIX = "/api/v1/";

// Headers we safely forward from the browser request to the backend.
const SAFE_FORWARD_HEADERS = ["content-type", "accept"];

// Headers we explicitly strip from backend responses before returning to browser.
// Never forward internal backend headers like Set-Cookie to the browser.
const STRIP_RESPONSE_HEADERS = new Set(["set-cookie", "server", "x-powered-by"]);

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

/**
 * Validates that the Origin/Referer header matches the expected host for
 * mutating requests (POST, PUT, PATCH, DELETE). Returns false if the
 * request appears cross-origin.
 *
 * Security note: In development (localhost), we compare only the *hostname*
 * (not the port) because the Next.js dev server may bind to a different port
 * than the browser's current address (e.g. fallback from :3000 to :3001).
 * All localhost ports are equally trusted in local dev. In production, the
 * app runs on a single origin and the full host comparison is used.
 */
export function checkCSRF(req: NextRequest): boolean {
  const method = req.method.toUpperCase();
  if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
    return true;
  }

  const host = req.headers.get("host") || req.nextUrl.host;
  const origin = req.headers.get("origin");
  const referer = req.headers.get("referer");

  if (!origin && !referer) {
    // No origin/referer — reject ambiguous mutating request
    return false;
  }

  // Extract just the hostname for comparison.
  // In production host === "yourdomain.com" so this is still an exact match.
  // In development host may be "localhost:3000" or "localhost:3001" depending
  // on port availability, so we compare only the hostname part.
  const serverHostname = host.split(":")[0];
  const isLocalhost = serverHostname === "localhost" || serverHostname === "127.0.0.1";

  try {
    if (origin) {
      const originUrl = new URL(origin);
      if (isLocalhost) {
        // Dev: match hostname only (ignore port)
        return originUrl.hostname === serverHostname;
      }
      // Production: match full host (hostname + port if non-standard)
      return originUrl.host === host;
    }
    if (referer) {
      const refererUrl = new URL(referer);
      if (isLocalhost) {
        return refererUrl.hostname === serverHostname;
      }
      return refererUrl.host === host;
    }
  } catch {
    return false;
  }

  return false;
}

/**
 * The single authoritative helper for proxying authenticated requests from
 * Next.js BFF routes to the FastAPI backend.
 *
 * Security guarantees:
 * - JWT is read from the HttpOnly cookie — never from request headers/body
 * - Any client-supplied Authorization header is OVERWRITTEN
 * - Only safe request headers are forwarded
 * - Sensitive response headers are stripped
 * - Only paths under /api/v1/ are allowed
 */
export async function proxyAuthenticatedRequest(
  req: NextRequest,
  backendPath: string,
  { requireAuth = true }: { requireAuth?: boolean } = {}
): Promise<NextResponse> {
  // Validate the backend path is within the allowed prefix
  if (!backendPath.startsWith(ALLOWED_BACKEND_PREFIX)) {
    return NextResponse.json({ detail: "Forbidden backend path" }, { status: 403 });
  }

  // CSRF protection for mutating methods
  if (!checkCSRF(req)) {
    return NextResponse.json(
      { detail: "Cross-origin request blocked" },
      { status: 403 }
    );
  }

  // Read token from HttpOnly cookie (server-side only)
  const cookieStore = cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (requireAuth && !token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  // Construct the backend URL, preserving query string
  const targetUrl = new URL(`${BACKEND_URL}${backendPath}`);
  // Forward query parameters
  req.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  // Build clean request headers — never blindly forward all client headers
  const forwardHeaders = new Headers();
  for (const header of SAFE_FORWARD_HEADERS) {
    const value = req.headers.get(header);
    if (value) forwardHeaders.set(header, value);
  }

  // Overwrite Authorization — the client NEVER controls this
  if (token) {
    forwardHeaders.set("Authorization", `Bearer ${token}`);
  }

  try {
    const body =
      req.method !== "GET" && req.method !== "HEAD"
        ? await req.arrayBuffer()
        : undefined;

    const backendResponse = await fetch(targetUrl.toString(), {
      method: req.method,
      headers: forwardHeaders,
      body: body ?? undefined,
    });

    // Build clean response headers — strip sensitive/internal headers
    const responseHeaders = new Headers();
    backendResponse.headers.forEach((value, key) => {
      if (!STRIP_RESPONSE_HEADERS.has(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      headers: responseHeaders,
    });
  } catch (err) {
    // Safe diagnostic logging: never log tokens, headers, request bodies, or secrets.
    const error = err as Error;
    console.error("[proxy] Backend fetch failed:", {
      name: error.name,
      message: error.message,
    });

    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

