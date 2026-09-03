import { NextRequest, NextResponse } from "next/server";
import { checkCSRF } from "@/lib/server/api-proxy";
import { signupErrorMessage } from "@/lib/auth-errors";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

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

  // Defensively strip any role/is_active fields the client might have injected.
  // The backend is the sole authority on role assignment.
  if (typeof body === "object" && body !== null) {
    const sanitised = { ...(body as Record<string, unknown>) };
    delete sanitised["role"];
    delete sanitised["roles"];
    delete sanitised["is_active"];
    delete sanitised["is_admin"];
    body = sanitised;
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    // The BFF could not reach FastAPI. Never leak backend internals.
    return NextResponse.json(
      { detail: signupErrorMessage(503) },
      { status: 503 }
    );
  }

  if (!backendRes.ok) {
    // Map the backend failure to safe, useful copy while preserving the
    // backend's HTTP status. FastAPI 422 bodies carry a `detail` array and 500
    // bodies may carry internal text — neither is ever forwarded verbatim.
    const data = await backendRes.json().catch(() => null);
    return NextResponse.json(
      { detail: signupErrorMessage(backendRes.status, data) },
      { status: backendRes.status }
    );
  }

  // Return 201 Created with no token — client must then navigate to /login
  return NextResponse.json({ ok: true }, { status: 201 });
}
