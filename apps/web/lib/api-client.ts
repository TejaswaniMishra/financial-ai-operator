export class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public data?: any
  ) {
    super(message);
    this.name = "APIError";
  }
}

const DIRECT_API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Base URL for API calls.
 * Browser: relative path (same-origin) so the request flows through the
 * Next.js BFF proxy, which reads the HttpOnly session cookie and injects the
 * Authorization header. Direct browser → :8000 fetches are blocked by CORS
 * outside the configured origins and never carry the session cookie.
 * Server: absolute URL to the backend (no CORS, cookies handled in code).
 */
function bffBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return DIRECT_API_BASE;
}

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function fetchClient<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, headers, ...customConfig } = options;

  // Build the URL without `new URL` on a possibly-relative path: the URL
  // constructor rejects relative browser paths (bffBase() === "" in the
  // browser), which previously made every request throw client-side.
  const query = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      query.append(key, value);
    });
  }
  const qs = query.toString();
  const url = `${bffBase()}${endpoint}${qs ? `?${qs}` : ""}`;

  const config: RequestInit = {
    ...customConfig,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
  };

  try {
    const response = await fetch(url, config);

    // Attempt to parse JSON response
    let data;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      throw new APIError(
        response.status,
        data?.detail || "An unexpected error occurred while communicating with the API.",
        data
      );
    }

    return data as T;
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    // Handle network errors (e.g. server down)
    throw new APIError(0, "Network error. Please check your connection or server status.");
  }
}