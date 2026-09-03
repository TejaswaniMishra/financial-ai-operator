import { NextRequest, NextResponse } from "next/server";
import { checkCSRF, SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

// JWT lifetime from the backend is 15 minutes (900 seconds).
// We match the cookie max-age to the access token lifetime.
const TOKEN_MAX_AGE_SECONDS = 15 * 60;

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
    } catch {}
    return NextResponse.json({ detail }, { status: backendRes.status });
  }

  let data: { access_token: string; token_type: string };
  try {
    data = await backendRes.json();
  } catch {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
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
    maxAge: TOKEN_MAX_AGE_SECONDS,
  });

  return response;
}
