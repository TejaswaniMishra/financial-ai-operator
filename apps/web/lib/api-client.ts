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

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function fetchClient<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, headers, ...customConfig } = options;
  
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, value);
    });
  }

  const config: RequestInit = {
    ...customConfig,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
  };

  try {
    const response = await fetch(url.toString(), config);
    
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
