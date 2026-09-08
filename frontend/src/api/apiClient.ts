import { AuthErrorCode, readAuthErrorCode } from "./authErrors";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const CSRF_COOKIE_NAME =
  import.meta.env.VITE_CSRF_COOKIE_NAME ?? "opsflow_csrf";

const CSRF_HEADER_NAME = "X-CSRF-Token";

const CSRF_PROTECTED_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/*
 * =========================================================
 * IN-MEMORY ACCESS TOKEN
 * =========================================================
 *
 * The access token intentionally lives only inside this
 * JavaScript module.
 *
 * It is NOT written to:
 *
 *   localStorage
 *   sessionStorage
 *   IndexedDB
 *   cookies
 *
 * A page reload destroys this value.
 *
 * Authentication is restored through:
 *
 *   POST /auth/refresh
 *
 * using:
 *
 *   HttpOnly refresh cookie
 *   +
 *   readable CSRF cookie
 *   +
 *   X-CSRF-Token header
 */

let accessToken: string | null = null;

/*
 * =========================================================
 * REFRESH COORDINATION
 * =========================================================
 *
 * Several protected requests may receive an access-token
 * rejection at nearly the same time.
 *
 * refreshPromise ensures they share one refresh request:
 *
 * Request A ─┐
 * Request B ─┼──► one refresh request
 * Request C ─┘
 */

let refreshPromise: Promise<string | null> | null = null;

/*
 * =========================================================
 * ACCESS TOKEN STATE
 * =========================================================
 */

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}

/*
 * =========================================================
 * COOKIE READING
 * =========================================================
 *
 * The refresh JWT cannot be read here because FastAPI sets
 * that cookie as HttpOnly.
 *
 * The CSRF cookie is intentionally different:
 *
 *   HttpOnly = false
 *
 * React may read the CSRF token because the CSRF token is
 * not itself an authentication credential.
 */

function getCookie(name: string): string | null {
  const cookies = document.cookie.split(";");

  for (const rawCookie of cookies) {
    const cookie = rawCookie.trim();

    const separatorIndex = cookie.indexOf("=");

    if (separatorIndex === -1) {
      continue;
    }

    const cookieName = cookie.slice(0, separatorIndex);

    if (cookieName !== name) {
      continue;
    }

    const cookieValue = cookie.slice(separatorIndex + 1);

    if (cookieValue.length === 0) {
      return null;
    }

    return decodeURIComponent(cookieValue);
  }

  return null;
}

/*
 * =========================================================
 * CSRF TOKEN
 * =========================================================
 *
 * The refresh JWT is HttpOnly and cannot be read by
 * JavaScript.
 *
 * The CSRF cookie is intentionally readable.
 */

export function getCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME);
}

/*
 * =========================================================
 * PRIVATE CSRF HEADER APPLICATION
 * =========================================================
 */

function applyCsrfHeader(headers: Headers, method: string | undefined): void {
  const normalizedMethod = (method ?? "GET").toUpperCase();

  if (!CSRF_PROTECTED_METHODS.has(normalizedMethod)) {
    return;
  }

  const csrfToken = getCsrfToken();

  if (!csrfToken) {
    /*
     * Never fabricate a CSRF value.
     *
     * A backend endpoint requiring cookie-authenticated
     * CSRF proof should reject the request itself.
     */

    headers.delete(CSRF_HEADER_NAME);

    return;
  }

  headers.set(CSRF_HEADER_NAME, csrfToken);
}

/*
 * =========================================================
 * PUBLIC CSRF HEADER HELPER
 * =========================================================
 */

export function addCsrfHeader(headers: Headers, method = "POST"): Headers {
  applyCsrfHeader(headers, method);

  return headers;
}

/*
 * =========================================================
 * AUTHENTICATION STATE EVENT
 * =========================================================
 */

function dispatchUnauthorized(): void {
  window.dispatchEvent(new Event("opsflow:unauthorized"));
}

/*
 * =========================================================
 * LOW-LEVEL REFRESH REQUEST
 * =========================================================
 *
 * This deliberately does NOT use apiFetch().
 *
 * Otherwise:
 *
 * protected request
 *      ↓
 * typed access rejection
 *      ↓
 * refresh
 *      ↓
 * refresh rejection
 *      ↓
 * refresh again
 *
 * could create a recursive refresh loop.
 */

async function performAccessTokenRefresh(): Promise<string | null> {
  try {
    const headers = addCsrfHeader(
      new Headers({
        Accept: "application/json",
      }),
      "POST",
    );

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",

      /*
       * Sends the HttpOnly refresh cookie.
       */

      credentials: "include",

      /*
       * Sends the matching readable CSRF value through
       * X-CSRF-Token.
       */

      headers,
    });

    if (!response.ok) {
      clearAccessToken();

      return null;
    }

    const body = (await response.json()) as {
      access_token?: unknown;

      token_type?: unknown;
    };

    if (
      typeof body.access_token !== "string" ||
      body.access_token.length === 0
    ) {
      clearAccessToken();

      return null;
    }

    setAccessToken(body.access_token);

    return body.access_token;
  } catch {
    clearAccessToken();

    return null;
  }
}

/*
 * =========================================================
 * PUBLIC REFRESH FUNCTION
 * =========================================================
 */

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = performAccessTokenRefresh();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

/*
 * =========================================================
 * AUTHENTICATED REQUEST EXECUTION
 * =========================================================
 */

async function executeRequest(
  path: string,
  options: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(options.headers);

  /*
   * -------------------------------------------------------
   * BEARER AUTHENTICATION
   * -------------------------------------------------------
   */

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.delete("Authorization");
  }

  /*
   * -------------------------------------------------------
   * CSRF
   * -------------------------------------------------------
   */

  applyCsrfHeader(headers, options.method);

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,

    headers,

    /*
     * Browser credentials remain enabled consistently.
     *
     * JavaScript never obtains the HttpOnly refresh JWT.
     */

    credentials: "include",
  });
}

/*
 * =========================================================
 * PUBLIC API CLIENT
 * =========================================================
 */

export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  /*
   * Snapshot the token used by this particular request.
   */

  const currentToken = getAccessToken();

  const response = await executeRequest(path, options, currentToken);

  /*
   * No local access credential was presented.
   *
   * There is therefore nothing to refresh.
   */

  if (!currentToken) {
    return response;
  }

  /*
   * Anything other than HTTP 401 is not an access-token
   * authentication failure.
   */

  if (response.status !== 401) {
    return response;
  }

  const authErrorCode = readAuthErrorCode(response);

  /*
   * =======================================================
   * UNKNOWN 401 — FAIL CLOSED
   * =======================================================
   *
   * A 401 with an unexpected or absent authentication code
   * is not assumed to mean ordinary token expiration.
   *
   * Do not automatically send persistent refresh
   * credentials in response to an ambiguous failure.
   *
   * Clear local identity and require a fresh login instead.
   */

  if (authErrorCode !== AuthErrorCode.ACCESS_CREDENTIALS_INVALID) {
    clearAccessToken();

    dispatchUnauthorized();

    return response;
  }

  /*
   * =======================================================
   * TYPED ACCESS-CREDENTIAL FAILURE
   * =======================================================
   *
   * FastAPI explicitly identified the rejected credential
   * as the bearer access credential.
   *
   * Attempt exactly one coordinated refresh.
   */

  const replacementToken = await refreshAccessToken();

  if (!replacementToken) {
    clearAccessToken();

    dispatchUnauthorized();

    return response;
  }

  /*
   * Retry the original request exactly once using the
   * replacement bearer credential.
   */

  const retryResponse = await executeRequest(path, options, replacementToken);

  /*
   * A second 401 after successful refresh means the local
   * authenticated identity can no longer be trusted.
   *
   * Do not enter another refresh cycle.
   */

  if (retryResponse.status === 401) {
    clearAccessToken();

    dispatchUnauthorized();
  }

  return retryResponse;
}
