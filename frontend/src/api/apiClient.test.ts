import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  addCsrfHeader,
  apiFetch,
  clearAccessToken,
  getAccessToken,
  getCsrfToken,
  refreshAccessToken,
  setAccessToken,
} from "./apiClient";

import { AUTH_ERROR_CODE_HEADER, AuthErrorCode } from "./authErrors";

/*
 * =========================================================
 * TEST CONSTANTS
 * =========================================================
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const CSRF_COOKIE_NAME =
  import.meta.env.VITE_CSRF_COOKIE_NAME ?? "opsflow_csrf";

const CSRF_HEADER_NAME = "X-CSRF-Token";

/*
 * =========================================================
 * FETCH MOCK
 * =========================================================
 *
 * apiClient.ts uses the browser fetch API directly.
 *
 * No test in this file should communicate with the actual
 * FastAPI application.
 */

const fetchMock = vi.fn<typeof fetch>();

/*
 * =========================================================
 * RESPONSE HELPERS
 * =========================================================
 */

function jsonResponse(
  body: unknown,
  status = 200,
  headers?: HeadersInit,
): Response {
  const responseHeaders = new Headers(headers);

  if (!responseHeaders.has("Content-Type")) {
    responseHeaders.set("Content-Type", "application/json");
  }

  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders,
  });
}

function emptyResponse(status: number, headers?: HeadersInit): Response {
  return new Response(null, {
    status,
    headers,
  });
}

/*
 * =========================================================
 * TYPED ACCESS-CREDENTIAL FAILURE
 * =========================================================
 *
 * apiFetch must refresh only when FastAPI explicitly
 * identifies the rejected credential as the bearer access
 * credential.
 *
 * A bare 401 is deliberately ambiguous and must not trigger
 * persistent refresh-cookie use.
 */

function accessCredentialFailureResponse(): Response {
  return emptyResponse(401, {
    [AUTH_ERROR_CODE_HEADER]: AuthErrorCode.ACCESS_CREDENTIALS_INVALID,
  });
}

/*
 * =========================================================
 * COOKIE HELPERS
 * =========================================================
 */

function setTestCookie(name: string, value: string): void {
  document.cookie = `${name}=` + `${encodeURIComponent(value)}; ` + "Path=/";
}

function clearTestCookie(name: string): void {
  document.cookie = `${name}=; ` + "Max-Age=0; " + "Path=/";
}

/*
 * =========================================================
 * FETCH INSPECTION HELPERS
 * =========================================================
 */

function getCallHeaders(callIndex: number): Headers {
  const [, options] = fetchMock.mock.calls[callIndex];

  return new Headers(options?.headers);
}

function countRefreshCalls(): number {
  return fetchMock.mock.calls.filter(
    ([input]) => String(input) === `${API_BASE_URL}/auth/refresh`,
  ).length;
}

/*
 * =========================================================
 * TEST LIFECYCLE
 * =========================================================
 */

beforeEach(() => {
  /*
   * The production access token is module-scoped state.
   *
   * Explicitly clear it before every test so one test can
   * never authenticate another test accidentally.
   */

  clearAccessToken();

  clearTestCookie(CSRF_COOKIE_NAME);

  fetchMock.mockReset();

  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  clearAccessToken();

  clearTestCookie(CSRF_COOKIE_NAME);

  vi.unstubAllGlobals();
});

/*
 * =========================================================
 * IN-MEMORY ACCESS TOKEN
 * =========================================================
 */

describe("access-token state", () => {
  it("starts without an access token after being cleared", () => {
    clearAccessToken();

    expect(getAccessToken()).toBeNull();
  });

  it("stores an access token in module memory", () => {
    setAccessToken("access-token-value");

    expect(getAccessToken()).toBe("access-token-value");
  });

  it("clears the in-memory access token", () => {
    setAccessToken("access-token-value");

    clearAccessToken();

    expect(getAccessToken()).toBeNull();
  });

  it("does not write an access token to localStorage or sessionStorage", () => {
    const localStorageSpy = vi.spyOn(Storage.prototype, "setItem");

    setAccessToken("access-token-value");

    expect(getAccessToken()).toBe("access-token-value");

    expect(localStorageSpy).not.toHaveBeenCalled();
  });
});

/*
 * =========================================================
 * CSRF COOKIE READING
 * =========================================================
 */

describe("getCsrfToken", () => {
  it("returns null when the CSRF cookie does not exist", () => {
    expect(getCsrfToken()).toBeNull();
  });

  it("reads the configured CSRF cookie", () => {
    setTestCookie(CSRF_COOKIE_NAME, "csrf-token-value");

    expect(getCsrfToken()).toBe("csrf-token-value");
  });

  it("decodes an encoded CSRF cookie value", () => {
    const token = "csrf/token+with=value";

    setTestCookie(CSRF_COOKIE_NAME, token);

    expect(getCsrfToken()).toBe(token);
  });

  it("returns null for an empty CSRF cookie", () => {
    document.cookie = `${CSRF_COOKIE_NAME}=; ` + "Path=/";

    expect(getCsrfToken()).toBeNull();
  });
});

/*
 * =========================================================
 * CSRF HEADER HELPER
 * =========================================================
 */

describe("addCsrfHeader", () => {
  it("adds the CSRF header to POST requests by default", () => {
    setTestCookie(CSRF_COOKIE_NAME, "csrf-token-value");

    const headers = addCsrfHeader(new Headers());

    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf-token-value");
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"])(
    "adds the CSRF header to unsafe %s requests",
    (method) => {
      setTestCookie(CSRF_COOKIE_NAME, "csrf-token-value");

      const headers = addCsrfHeader(new Headers(), method);

      expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf-token-value");
    },
  );

  it.each(["GET", "HEAD", "OPTIONS"])(
    "does not add the CSRF header to safe %s requests",
    (method) => {
      setTestCookie(CSRF_COOKIE_NAME, "csrf-token-value");

      const headers = addCsrfHeader(new Headers(), method);

      expect(headers.has(CSRF_HEADER_NAME)).toBe(false);
    },
  );

  it("does not fabricate a CSRF header when the cookie is absent", () => {
    const headers = addCsrfHeader(new Headers(), "POST");

    expect(headers.has(CSRF_HEADER_NAME)).toBe(false);
  });

  it("removes a stale CSRF header when no CSRF cookie exists", () => {
    const headers = new Headers({
      [CSRF_HEADER_NAME]: "stale-value",
    });

    addCsrfHeader(headers, "POST");

    expect(headers.has(CSRF_HEADER_NAME)).toBe(false);
  });
});

/*
 * =========================================================
 * ACCESS-TOKEN REFRESH
 * =========================================================
 */

describe("refreshAccessToken", () => {
  it("sends a credentialed POST request to the refresh endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        access_token: "new-access-token",

        token_type: "bearer",
      }),
    );

    await refreshAccessToken();

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE_URL}/auth/refresh`);

    const [, options] = fetchMock.mock.calls[0];

    expect(options?.method).toBe("POST");

    expect(options?.credentials).toBe("include");

    const headers = new Headers(options?.headers);

    expect(headers.get("Accept")).toBe("application/json");
  });

  it("copies the readable CSRF cookie into the refresh request header", async () => {
    setTestCookie(CSRF_COOKIE_NAME, "csrf-refresh-value");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        access_token: "new-access-token",
      }),
    );

    await refreshAccessToken();

    const headers = getCallHeaders(0);

    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf-refresh-value");
  });

  it("stores and returns a valid replacement access token", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        access_token: "replacement-token",
      }),
    );

    const result = await refreshAccessToken();

    expect(result).toBe("replacement-token");

    expect(getAccessToken()).toBe("replacement-token");
  });

  it("clears the access token when refresh returns a non-success response", async () => {
    setAccessToken("expired-access-token");

    fetchMock.mockResolvedValueOnce(emptyResponse(401));

    const result = await refreshAccessToken();

    expect(result).toBeNull();

    expect(getAccessToken()).toBeNull();
  });

  it("clears the access token when the refresh response has no access token", async () => {
    setAccessToken("expired-access-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        token_type: "bearer",
      }),
    );

    const result = await refreshAccessToken();

    expect(result).toBeNull();

    expect(getAccessToken()).toBeNull();
  });

  it("clears the access token when the returned access token is empty", async () => {
    setAccessToken("expired-access-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        access_token: "",
      }),
    );

    const result = await refreshAccessToken();

    expect(result).toBeNull();

    expect(getAccessToken()).toBeNull();
  });

  it("fails closed when the refresh request throws a network error", async () => {
    setAccessToken("expired-access-token");

    fetchMock.mockRejectedValueOnce(new TypeError("Network error"));

    const result = await refreshAccessToken();

    expect(result).toBeNull();

    expect(getAccessToken()).toBeNull();
  });
});

/*
 * =========================================================
 * AUTHENTICATED API REQUESTS
 * =========================================================
 */

describe("apiFetch", () => {
  it("sends the in-memory access token as a Bearer credential", async () => {
    setAccessToken("current-access-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services");

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE_URL}/services`);

    const headers = getCallHeaders(0);

    expect(headers.get("Authorization")).toBe("Bearer current-access-token");
  });

  it("always enables browser credentials for API requests", async () => {
    setAccessToken("current-access-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services");

    const [, options] = fetchMock.mock.calls[0];

    expect(options?.credentials).toBe("include");
  });

  it("preserves caller-provided request headers", async () => {
    setAccessToken("current-access-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services", {
      headers: {
        Accept: "application/json",

        "X-Test-Header": "test-value",
      },
    });

    const headers = getCallHeaders(0);

    expect(headers.get("X-Test-Header")).toBe("test-value");

    expect(headers.get("Accept")).toBe("application/json");

    expect(headers.get("Authorization")).toBe("Bearer current-access-token");
  });

  it("removes a caller-provided stale Authorization header when no token exists", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services", {
      headers: {
        Authorization: "Bearer stale-token",
      },
    });

    const headers = getCallHeaders(0);

    expect(headers.has("Authorization")).toBe(false);
  });

  it("adds CSRF protection to unsafe API requests", async () => {
    setAccessToken("current-access-token");

    setTestCookie(CSRF_COOKIE_NAME, "resource-csrf-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        name: "Service A",
      }),
    });

    const headers = getCallHeaders(0);

    expect(headers.get(CSRF_HEADER_NAME)).toBe("resource-csrf-token");
  });

  it("does not attach CSRF protection to GET requests", async () => {
    setAccessToken("current-access-token");

    setTestCookie(CSRF_COOKIE_NAME, "resource-csrf-token");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ok: true,
      }),
    );

    await apiFetch("/services", {
      method: "GET",
    });

    const headers = getCallHeaders(0);

    expect(headers.has(CSRF_HEADER_NAME)).toBe(false);
  });

  it("returns non-401 responses without attempting refresh", async () => {
    setAccessToken("current-access-token");

    fetchMock.mockResolvedValueOnce(emptyResponse(403));

    const response = await apiFetch("/services");

    expect(response.status).toBe(403);

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(countRefreshCalls()).toBe(0);
  });

  it("does not attempt refresh for a 401 when no access token was sent", async () => {
    fetchMock.mockResolvedValueOnce(accessCredentialFailureResponse());

    const response = await apiFetch("/services");

    expect(response.status).toBe(401);

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(countRefreshCalls()).toBe(0);
  });

  it("does not refresh an ambiguous 401 when an access token was sent", async () => {
    setAccessToken("current-access-token");

    const unauthorizedListener = vi.fn();

    window.addEventListener("opsflow:unauthorized", unauthorizedListener);

    fetchMock.mockResolvedValueOnce(emptyResponse(401));

    try {
      const response = await apiFetch("/services");

      expect(response.status).toBe(401);

      /*
       * An untyped 401 is deliberately not assumed to
       * mean that the bearer access token expired.
       *
       * Persistent refresh credentials must therefore
       * not be sent.
       */

      expect(fetchMock).toHaveBeenCalledTimes(1);

      expect(countRefreshCalls()).toBe(0);

      expect(getAccessToken()).toBeNull();

      expect(unauthorizedListener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("opsflow:unauthorized", unauthorizedListener);
    }
  });

  it("refreshes an expired token and retries the original request once", async () => {
    setAccessToken("expired-access-token");

    fetchMock
      /*
       * The backend explicitly identifies the first 401
       * as an access-credential rejection.
       */
      .mockResolvedValueOnce(accessCredentialFailureResponse())

      /*
       * Refresh succeeds.
       */
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: "replacement-access-token",
        }),
      )

      /*
       * Original request succeeds when retried.
       */
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
        }),
      );

    const response = await apiFetch("/services");

    expect(response.status).toBe(200);

    expect(fetchMock).toHaveBeenCalledTimes(3);

    /*
     * Request 1:
     *
     * protected resource using the expired token.
     */

    const firstHeaders = getCallHeaders(0);

    expect(firstHeaders.get("Authorization")).toBe(
      "Bearer expired-access-token",
    );

    /*
     * Request 2:
     *
     * refresh.
     */

    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE_URL}/auth/refresh`);

    /*
     * Request 3:
     *
     * exactly one retry using the new token.
     */

    const retryHeaders = getCallHeaders(2);

    expect(retryHeaders.get("Authorization")).toBe(
      "Bearer replacement-access-token",
    );

    expect(getAccessToken()).toBe("replacement-access-token");
  });

  it("clears authentication and emits unauthorized when refresh fails", async () => {
    setAccessToken("expired-access-token");

    const unauthorizedListener = vi.fn();

    window.addEventListener("opsflow:unauthorized", unauthorizedListener);

    fetchMock
      /*
       * Original protected request is explicitly an
       * access-token rejection.
       */
      .mockResolvedValueOnce(accessCredentialFailureResponse())

      /*
       * Refresh itself fails.
       */
      .mockResolvedValueOnce(emptyResponse(401));

    try {
      const response = await apiFetch("/services");

      expect(response.status).toBe(401);

      expect(fetchMock).toHaveBeenCalledTimes(2);

      expect(countRefreshCalls()).toBe(1);

      /*
       * There must be no third protected-resource
       * request because no replacement credential was
       * obtained.
       */

      expect(getAccessToken()).toBeNull();

      expect(unauthorizedListener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("opsflow:unauthorized", unauthorizedListener);
    }
  });

  it("does not enter a second refresh cycle when the retried request also returns 401", async () => {
    setAccessToken("expired-access-token");

    const unauthorizedListener = vi.fn();

    window.addEventListener("opsflow:unauthorized", unauthorizedListener);

    fetchMock
      /*
       * Original protected request.
       *
       * This must be explicitly identified as an access
       * credential rejection to authorize one refresh.
       */
      .mockResolvedValueOnce(accessCredentialFailureResponse())

      /*
       * Successful refresh.
       */
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: "replacement-access-token",
        }),
      )

      /*
       * Retried protected request still fails.
       *
       * apiFetch must not recurse into another refresh
       * cycle after the one allowed retry.
       */
      .mockResolvedValueOnce(accessCredentialFailureResponse());

    try {
      const response = await apiFetch("/services");

      expect(response.status).toBe(401);

      expect(fetchMock).toHaveBeenCalledTimes(3);

      /*
       * Crucially, there was only ONE refresh request.
       */

      expect(countRefreshCalls()).toBe(1);

      expect(getAccessToken()).toBeNull();

      expect(unauthorizedListener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("opsflow:unauthorized", unauthorizedListener);
    }
  });
});

/*
 * =========================================================
 * CONCURRENT REFRESH COORDINATION
 * =========================================================
 */

describe("concurrent refresh coordination", () => {
  it("shares one refresh request across simultaneous 401 responses", async () => {
    setAccessToken("expired-access-token");

    /*
     * Hold the refresh response open long enough for
     * both protected requests to reach
     * refreshAccessToken().
     *
     * If refreshPromise works correctly, request B will
     * reuse request A's pending refresh Promise rather
     * than issuing a second /auth/refresh call.
     */

    let resolveRefresh: (response: Response) => void = () => {
      throw new Error("Refresh resolver was not initialized.");
    };

    const pendingRefresh = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });

    fetchMock.mockImplementation((input, options) => {
      const url = String(input);

      /*
       * Refresh endpoint.
       */

      if (url === `${API_BASE_URL}/auth/refresh`) {
        return pendingRefresh;
      }

      const headers = new Headers(options?.headers);

      const authorization = headers.get("Authorization");

      /*
       * Both initial requests use the expired token.
       *
       * FastAPI explicitly identifies the bearer
       * access credential as the rejected credential.
       */

      if (authorization === "Bearer expired-access-token") {
        return Promise.resolve(accessCredentialFailureResponse());
      }

      /*
       * Both retried requests should use the same
       * replacement token.
       */

      if (authorization === "Bearer shared-replacement-token") {
        return Promise.resolve(
          jsonResponse({
            ok: true,
          }),
        );
      }

      return Promise.resolve(emptyResponse(500));
    });

    const servicesRequest = apiFetch("/services");

    const incidentsRequest = apiFetch("/incidents");

    /*
     * Wait until one refresh call has actually started.
     */

    await vi.waitFor(() => {
      expect(countRefreshCalls()).toBe(1);
    });

    /*
     * Let the shared refresh complete.
     */

    resolveRefresh(
      jsonResponse({
        access_token: "shared-replacement-token",
      }),
    );

    const [servicesResponse, incidentsResponse] = await Promise.all([
      servicesRequest,
      incidentsRequest,
    ]);

    expect(servicesResponse.status).toBe(200);

    expect(incidentsResponse.status).toBe(200);

    /*
     * This is the critical assertion.
     *
     * Two simultaneous expired requests resulted in
     * ONE refresh operation.
     */

    expect(countRefreshCalls()).toBe(1);

    expect(getAccessToken()).toBe("shared-replacement-token");

    /*
     * Expected calls:
     *
     * 1. GET /services    -> typed 401
     * 2. GET /incidents   -> typed 401
     * 3. POST /refresh    -> 200
     * 4. retry /services  -> 200
     * 5. retry /incidents -> 200
     */

    expect(fetchMock).toHaveBeenCalledTimes(5);
  });
});
