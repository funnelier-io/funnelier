import { API_BASE } from "./constants";

/**
 * API client with JWT token injection and auto-refresh.
 */

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem("token", access);
  localStorage.setItem("refresh_token", refresh);
}

function clearTokens() {
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      clearTokens();
      return null;
    }

    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  ok: boolean;
}

export interface ApiError {
  detail: string;
  status: number;
}

/**
 * Main fetch wrapper with JWT auth and auto-refresh.
 */
export async function api<T = unknown>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  options?: { noAuth?: boolean }
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!options?.noAuth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const fetchOptions: RequestInit = { method, headers };
  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  let res = await fetch(`${API_BASE}${path}`, fetchOptions);

  // Auto-refresh on 401
  if (res.status === 401 && !options?.noAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      fetchOptions.headers = headers;
      res = await fetch(`${API_BASE}${path}`, fetchOptions);
    }
  }

  const data = await res.json().catch(() => ({}) as T);

  return {
    data: data as T,
    status: res.status,
    ok: res.ok,
  };
}

/**
 * Upload file via multipart form data.
 */
export async function uploadFile<T = unknown>(
  path: string,
  file: File,
  fieldName = "file"
): Promise<ApiResponse<T>> {
  const token = getToken();
  const formData = new FormData();
  formData.append(fieldName, file);

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  const data = await res.json().catch(() => ({}) as T);

  return {
    data: data as T,
    status: res.status,
    ok: res.ok,
  };
}

// Convenience methods
export const apiGet = <T>(path: string) => api<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown) =>
  api<T>("POST", path, body);
export const apiPut = <T>(path: string, body?: unknown) =>
  api<T>("PUT", path, body);
export const apiDelete = <T>(path: string) => api<T>("DELETE", path);

export { setTokens, clearTokens, getToken };

