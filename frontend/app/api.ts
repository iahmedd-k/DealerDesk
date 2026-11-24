export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

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

function storedAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("dealerdesk_access");
}

let refreshInProgress: Promise<string | null> | null = null;

export async function refreshStoredAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const refreshToken = window.localStorage.getItem("dealerdesk_refresh");
  if (refreshInProgress) return refreshInProgress;

  refreshInProgress = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(refreshToken ? { refresh_token: refreshToken } : {}),
      });
      if (!response.ok) throw new Error("Session refresh failed");
      const tokens = (await response.json()) as {
        access_token: string;
        refresh_token: string;
      };
      if (tokens.access_token) {
        window.localStorage.setItem("dealerdesk_access", tokens.access_token);
        window.localStorage.setItem("dealerdesk_refresh", tokens.refresh_token);
      }
      return tokens.access_token;
    } catch (error) {
      window.localStorage.removeItem("dealerdesk_access");
      window.localStorage.removeItem("dealerdesk_refresh");
      window.dispatchEvent(new Event("dealerdesk:auth-expired"));
      return null;
    } finally {
      refreshInProgress = null;
    }
  })();
  return refreshInProgress;
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

  const usesStoredToken = accessToken === undefined;
  let token = usesStoredToken ? storedAccessToken() : accessToken;
  const sendRequest = async (requestToken: string | null): Promise<Response> => {
    const requestHeaders = new Headers(headers);
    if (requestToken) requestHeaders.set("Authorization", `Bearer ${requestToken}`);
    else requestHeaders.delete("Authorization");
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
  let response = await sendRequest(token);
  if (
    response.status === 401
    && usesStoredToken
    && token
    && !path.startsWith("/auth/")
  ) {
    const refreshedToken = await refreshStoredAccessToken();
    if (refreshedToken) {
      token = refreshedToken;
      response = await sendRequest(token);
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
