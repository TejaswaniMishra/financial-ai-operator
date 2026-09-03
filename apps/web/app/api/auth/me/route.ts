import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE_NAME } from "@/lib/server/api-proxy";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

export async function GET(_req: NextRequest): Promise<NextResponse> {
  const cookieStore = cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }

  if (!backendRes.ok) {
    // Token expired/revoked — tell the client session is gone
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  // Return ONLY the safe CurrentUser fields — never forward raw backend payloads
  let data: Record<string, unknown>;
  try {
    data = await backendRes.json();
  } catch {
    return NextResponse.json({ detail: "Invalid backend response" }, { status: 502 });
  }

  const safeUser = {
    id: data.id,
    email: data.email,
    display_name: data.display_name ?? null,
    is_active: data.is_active,
  };

  return NextResponse.json(safeUser, { status: 200 });
}
