import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/server/api-proxy";

async function handler(
  req: NextRequest,
  context: { params: { path: string[] } }
): Promise<Response> {
  const backendPath = "/api/v1/" + context.params.path.join("/");
  // /api/v1/health is a public unauthenticated probe on the backend — the
  // browser health check must work before any session exists (e.g. the
  // dashboard's connection notice), so it is forwarded without a token.
  const requireAuth = backendPath !== "/api/v1/health";
  return proxyAuthenticatedRequest(req, backendPath, { requireAuth });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;