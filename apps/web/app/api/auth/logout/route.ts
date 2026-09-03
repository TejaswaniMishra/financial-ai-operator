import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { checkCSRF, SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  if (!checkCSRF(req)) {
    return NextResponse.json({ detail: "Cross-origin request blocked" }, { status: 403 });
  }

  const cookieStore = cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  // Always clear the session cookie regardless of backend outcome.
  // This ensures the client always ends up unauthenticated.
  const response = NextResponse.json({ ok: true }, { status: 200 });
  response.cookies.set(SESSION_COOKIE_NAME, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0, // Expire immediately
  });

  if (!token) {
    // No session to revoke — still return success so client clears state
    return response;
  }

  // Best-effort: call backend to revoke the token (no client-supplied jti)
  try {
    await fetch(`${BACKEND_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
  } catch {
    // Backend unreachable — still clear local session
    console.error("[logout] Backend logout call failed");
  }

  return response;
}
