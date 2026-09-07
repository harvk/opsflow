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
  const cookies = document.cookie.split("; ");

  for (const cookie of cookies) {
    const separatorIndex = cookie.indexOf("=");

    if (separatorIndex === -1) {
      continue;
    }

    const cookieName = cookie.slice(0, separatorIndex);

    const cookieValue = cookie.slice(separatorIndex + 1);

    if (cookieName === name) {
      return decodeURIComponent(cookieValue);
    }
  }

  return null;
}

/*
 * =========================================================
 * CSRF TOKEN ACCESS
 * =========================================================
 */

export function getCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME);
}

/*
 * =========================================================
 * CSRF HEADER APPLICATION
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
     * A cookie-authenticated backend endpoint that requires
     * CSRF validation will correctly reject the request
     * with HTTP 403.
     */
    headers.delete(CSRF_HEADER_NAME);

    return;
  }

  headers.set(CSRF_HEADER_NAME, csrfToken);
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
    const headers = new Headers({
      Accept: "application/json",
    });

    /*
     * /auth/refresh is cookie-authenticated.
     *
     * Copy the readable CSRF cookie into the required custom
     * request header.
     */
    applyCsrfHeader(headers, "POST");

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",

      /*
       * The refresh JWT is an HttpOnly browser cookie.
       *
       * Because React and FastAPI use different origins
       * during development, credentials must explicitly
       * be included.
       */
      credentials: "include",

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
   * Bearer authentication.
   */
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.delete("Authorization");
  }

  /*
   * Add the CSRF header to unsafe HTTP methods whenever the
   * signed CSRF cookie exists.
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
