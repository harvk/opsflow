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
 * Several protected requests may receive 401 at nearly the
 * same time when the current access token expires.
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

    try {
      return decodeURIComponent(cookieValue);
    } catch {
      /*
       * A malformed cookie must never crash the entire
       * authentication client.
       */
      return null;
    }
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
 * The CSRF cookie is intentionally readable. For unsafe
 * cookie-authenticated requests, the frontend copies the
 * cookie value into:
 *
 *   X-CSRF-Token
 */

export function getCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME);
}

/*
 * =========================================================
 * PRIVATE CSRF HEADER APPLICATION
 * =========================================================
 *
 * apiFetch() uses this helper automatically.
 *
 * It mutates the supplied Headers instance.
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
     * A cookie-authenticated backend endpoint requiring
     * CSRF validation should reject the request rather than
     * receive a made-up value.
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
 *
 * Some authentication calls intentionally bypass apiFetch()
 * because they have special lifecycle behavior.
 *
 * Examples:
 *
 *   POST /auth/refresh
 *   POST /auth/logout
 *
 * These calls still require the double-submit CSRF header.
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
 *     401
 *      ↓
 * refresh
 *      ↓
 *     401
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
   * Bearer authentication
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
   *
   * Add the CSRF header to unsafe HTTP methods whenever the
   * signed readable CSRF cookie exists.
   *
   * Bearer-only API routes may simply ignore this extra
   * header.
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
   * No authentication retry is necessary when:
   *
   *   - the response is not 401
   *   - or there was no access token in the first place
   */

  if (response.status !== 401 || !currentToken) {
    return response;
  }

  /*
   * FastAPI rejected an access token.
   *
   * The normal legitimate explanation is that the
   * short-lived token expired.
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
   * Retry the original request exactly once using the new
   * bearer credential.
   */

  const retryResponse = await executeRequest(path, options, replacementToken);

  /*
   * A second 401 means ordinary token expiration was not
   * the problem.
   *
   * Do not enter another refresh cycle.
   */

  if (retryResponse.status === 401) {
    clearAccessToken();

    dispatchUnauthorized();
  }

  return retryResponse;
}
