import { NextRequest } from "next/server";
import { proxyAuthenticatedRequest } from "@/lib/server/api-proxy";

async function handler(
  req: NextRequest,
  context: { params: { path: string[] } }
): Promise<Response> {
  const backendPath = "/api/v1/" + context.params.path.join("/");
  return proxyAuthenticatedRequest(req, backendPath);
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;