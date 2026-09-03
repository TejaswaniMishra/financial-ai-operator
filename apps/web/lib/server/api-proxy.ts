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

  try {
    if (origin) {
      const originHost = new URL(origin).host;
      return originHost === host;
    }
    if (referer) {
      const refererHost = new URL(referer).host;
      return refererHost === host;
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
    // Only log the error type, not content that might contain tokens/secrets
    console.error("[proxy] Backend fetch failed:", (err as Error).name);
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}
