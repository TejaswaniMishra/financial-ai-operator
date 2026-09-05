import { NextRequest, NextResponse } from "next/server";
import { checkCSRF, SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

// The cookie max-age is matched to the backend access-token lifetime by
// reading the token's `exp` claim, so a deployer can change
// ACCESS_TOKEN_EXPIRE_MINUTES without a stale hardcoded value here.
// (Fallback of 15 minutes applies only if the claim cannot be read.)
const FALLBACK_TOKEN_MAX_AGE_SECONDS = 15 * 60;

function tokenMaxAgeSeconds(accessToken: string): number {
  try {
    const payload = JSON.parse(
      Buffer.from(accessToken.split(".")[1] ?? "", "base64url").toString("utf8")
    );
    if (typeof payload?.exp === "number" && payload.exp > 0) {
      return Math.max(30, payload.exp - Math.floor(Date.now() / 1000));
    }
  } catch {
    // Unreadable payload — fall through to the safe fallback below.
  }
  return FALLBACK_TOKEN_MAX_AGE_SECONDS;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  console.log("[auth/login] backend config:", {
    configured: Boolean(BACKEND_URL),
    isLocalhost: BACKEND_URL.includes("localhost"),
    isRender: BACKEND_URL.includes("onrender.com"),
  });

  if (!checkCSRF(req)) {
    return NextResponse.json({ detail: "Cross-origin request blocked" }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  // Forward credentials to the FastAPI backend
  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }

  // On failure, forward the backend error safely (never expose internals)
  if (!backendRes.ok) {
    let detail = "Invalid email or password";
    try {
      const data = await backendRes.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch { }
    return NextResponse.json({ detail }, { status: backendRes.status });
  }

  let data: { access_token?: string; mfa_required?: boolean; mfa_token?: string };
  try {
    data = await backendRes.json();
  } catch {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
  }

  // MFA challenge: no session is established yet. The short-lived mfa_token
  // is passed to the browser only so the second login stage can exchange it;
  // it grants access to nothing else.
  if (data?.mfa_required) {
    if (!data.mfa_token || typeof data.mfa_token !== "string") {
      return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
    }
    return NextResponse.json(
      { mfa_required: true, mfa_token: data.mfa_token },
      { status: 200 }
    );
  }

  if (!data?.access_token || typeof data.access_token !== "string") {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
  }

  // Set the JWT in an HttpOnly cookie — it never reaches browser JavaScript
  const response = NextResponse.json({ ok: true }, { status: 200 });
  response.cookies.set(SESSION_COOKIE_NAME, data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: tokenMaxAgeSeconds(data.access_token),
  });

  return response;
}
