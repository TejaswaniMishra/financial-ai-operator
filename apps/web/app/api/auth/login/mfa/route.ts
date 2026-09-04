import { NextRequest, NextResponse } from "next/server";
import { checkCSRF, SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

// JWT lifetime from the backend is 15 minutes (900 seconds).
// We match the cookie max-age to the access token lifetime.
const TOKEN_MAX_AGE_SECONDS = 15 * 60;

// POST /api/auth/login/mfa — second login stage for MFA-enabled accounts.
// Exchanges the short-lived challenge token + TOTP/recovery code for a real
// session cookie. The challenge token is single-use server-side.
export async function POST(req: NextRequest): Promise<NextResponse> {
  if (!checkCSRF(req)) {
    return NextResponse.json({ detail: "Cross-origin request blocked" }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/mfa/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }

  if (!backendRes.ok) {
    let detail = "Invalid authenticator or recovery code";
    try {
      const data = await backendRes.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {}
    return NextResponse.json({ detail }, { status: backendRes.status });
  }

  let data: { access_token?: string };
  try {
    data = await backendRes.json();
  } catch {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
  }

  if (!data?.access_token || typeof data.access_token !== "string") {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
  }

  const response = NextResponse.json({ ok: true }, { status: 200 });
  response.cookies.set(SESSION_COOKIE_NAME, data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: TOKEN_MAX_AGE_SECONDS,
  });

  return response;
}
