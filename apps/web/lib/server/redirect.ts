/**
 * Validates that a redirect destination is a safe internal application path.
 *
 * Rules:
 * - Must start with "/"
 * - Must NOT start with "//" (protocol-relative — could be external)
 * - Must NOT contain a protocol (http:, https:, etc.)
 * - Must NOT be an auth path (prevents redirect loops)
 * - Only allows printable ASCII path characters
 */

const AUTH_PATHS = new Set(["/login", "/signup"]);

export function validateNextParam(next: string | null | undefined): string {
  if (!next) return "/";

  try {
    // Reject anything that contains a protocol or is protocol-relative
    if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(next)) return "/";
    if (next.startsWith("//")) return "/";

    // Must start with a single "/"
    if (!next.startsWith("/")) return "/";

    // Reject non-ASCII or control characters
    if (!/^[\x20-\x7E]+$/.test(next)) return "/";

    // Reject auth paths to prevent redirect loops
    const pathname = next.split("?")[0];
    if (AUTH_PATHS.has(pathname)) return "/";

    // Normalise and ensure it's still an internal path after URL parsing
    const parsed = new URL(next, "http://localhost");
    if (parsed.host !== "localhost") return "/";

    return next;
  } catch {
    return "/";
  }
}
