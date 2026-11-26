export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000/api/v1`
    : "http://localhost:8000/api/v1");

export class ApiError extends Error {
  errorCode?: string;
  requestId?: string;
  statusCode: number;

  constructor(message: string, statusCode: number, errorCode?: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.requestId = requestId;
  }
}

let refreshInProgress: Promise<boolean> | null = null;
let lastRefreshFailureAt = 0;

function clearLegacyTokenStorage(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("dealerdesk_access");
  window.localStorage.removeItem("dealerdesk_refresh");
}

export async function refreshSession(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (Date.now() - lastRefreshFailureAt < 3000) return false;
  if (refreshInProgress) return refreshInProgress;

  refreshInProgress = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error("Session refresh failed");
      lastRefreshFailureAt = 0;
      clearLegacyTokenStorage();
      return true;
    } catch {
      lastRefreshFailureAt = Date.now();
      clearLegacyTokenStorage();
      window.dispatchEvent(new Event("dealerdesk:auth-expired"));
      return false;
    } finally {
      refreshInProgress = null;
    }
  })();
  return refreshInProgress;
}

export async function refreshStoredAccessToken(): Promise<string | null> {
  const ok = await refreshSession();
  return ok ? "cookie" : null;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (!headers.has("X-Request-ID")) {
    headers.set(
      "X-Request-ID",
      `fe-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
    );
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const usesCookieSession = accessToken === undefined;
  const sendRequest = async (explicitToken: string | null | undefined): Promise<Response> => {
    const requestHeaders = new Headers(headers);
    if (explicitToken && explicitToken !== "cookie") {
      requestHeaders.set("Authorization", `Bearer ${explicitToken}`);
    } else {
      requestHeaders.delete("Authorization");
    }
    try {
      return await fetch(`${API_URL}${path}`, {
        ...options,
        credentials: options.credentials ?? "include",
        headers: requestHeaders,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Network request failed";
      throw new ApiError(`Could not connect to DealerDesk: ${message}`, 0);
    }
  };
  let response = await sendRequest(accessToken);
  if (
    response.status === 401
    && usesCookieSession
    && !path.startsWith("/auth/")
  ) {
    const refreshed = await refreshSession();
    if (refreshed) {
      response = await sendRequest(null);
    }
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    let errorCode: string | undefined;
    let requestId = response.headers.get("X-Request-ID") || undefined;

    try {
      const body = (await response.json()) as {
        detail?: string | string[];
        error_code?: string;
        request_id?: string;
      };
      if (Array.isArray(body.detail)) {
        detail = body.detail.join(", ");
      } else if (typeof body.detail === "string") {
        detail = body.detail;
      }
      errorCode = body.error_code;
      requestId = body.request_id || requestId;
    } catch {
      detail = response.statusText || detail;
    }

    throw new ApiError(detail, response.status, errorCode, requestId);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
