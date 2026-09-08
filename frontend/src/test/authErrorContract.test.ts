import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmPasswordReset,
  loginRequest,
  PasswordResetThrottleError,
  requestPasswordReset,
} from "../api/authApi";

import {
  apiFetch,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../api/apiClient";

import {
  AUTH_ERROR_CODE_HEADER,
  AuthApiError,
  AuthErrorCode,
  readAuthErrorCode,
} from "../api/authErrors";

/*
 * =========================================================
 * RESPONSE HELPER
 * =========================================================
 */

function createResponse(
  status: number,
  options: {
    code?: string;

    retryAfter?: string;

    body?: unknown;
  } = {},
): Response {
  const headers = new Headers();

  if (options.code) {
    headers.set(AUTH_ERROR_CODE_HEADER, options.code);
  }

  if (options.retryAfter) {
    headers.set("Retry-After", options.retryAfter);
  }

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  return new Response(
    options.body === undefined ? null : JSON.stringify(options.body),
    {
      status,

      headers,
    },
  );
}

/*
 * =========================================================
 * TEST ISOLATION
 * =========================================================
 */

beforeEach(() => {
  clearAccessToken();
});

afterEach(() => {
  clearAccessToken();

  vi.unstubAllGlobals();

  vi.restoreAllMocks();
});

/*
 * =========================================================
 * ERROR CODE PARSING
 * =========================================================
 */

describe("authentication error code parsing", () => {
  it("accepts a known authentication error code", () => {
    const response = createResponse(401, {
      code: AuthErrorCode.LOGIN_CREDENTIALS_INVALID,
    });

    expect(readAuthErrorCode(response)).toBe(
      AuthErrorCode.LOGIN_CREDENTIALS_INVALID,
    );
  });

  it("rejects an unknown authentication error code", () => {
    const response = createResponse(401, {
      code: "INTERNAL_UNTRUSTED_CODE",
    });

    expect(readAuthErrorCode(response)).toBeNull();
  });
});

/*
 * =========================================================
 * LOGIN
 * =========================================================
 */

describe("login typed error contract", () => {
  it("maps the typed invalid-login code to frontend-controlled text", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createResponse(401, {
        code: AuthErrorCode.LOGIN_CREDENTIALS_INVALID,

        body: {
          detail: "BACKEND_TEXT_MUST_NOT_CONTROL_UI",
        },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    try {
      await loginRequest({
        email: "missing@example.com",

        password: "WrongPassword123!",
      });

      throw new Error("Expected loginRequest to reject.");
    } catch (error) {
      expect(error).toBeInstanceOf(AuthApiError);

      expect(error).toMatchObject({
        code: AuthErrorCode.LOGIN_CREDENTIALS_INVALID,

        status: 401,

        message: "Invalid email or password.",
      });

      expect((error as Error).message).not.toContain("BACKEND_TEXT");
    }
  });

  it("does not infer invalid credentials from an untyped 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createResponse(401, {
        body: {
          detail: "Incorrect email or password.",
        },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      loginRequest({
        email: "missing@example.com",

        password: "WrongPassword123!",
      }),
    ).rejects.toMatchObject({
      code: null,

      status: 401,

      message: "Unable to sign in. Please try again.",
    });
  });
});

/*
 * =========================================================
 * PASSWORD RESET THROTTLING
 * =========================================================
 */

describe("password-reset throttle contract", () => {
  it("uses the typed throttle code and Retry-After header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createResponse(429, {
        code: AuthErrorCode.PASSWORD_RESET_THROTTLED,

        retryAfter: "75",

        body: {
          detail: "backend throttle text",
        },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    try {
      await requestPasswordReset("person@example.com");

      throw new Error("Expected requestPasswordReset to reject.");
    } catch (error) {
      expect(error).toBeInstanceOf(PasswordResetThrottleError);

      const throttleError = error as PasswordResetThrottleError;

      expect(throttleError.code).toBe(AuthErrorCode.PASSWORD_RESET_THROTTLED);

      expect(throttleError.status).toBe(429);

      expect(throttleError.retryAfterSeconds).toBe(75);
    }
  });
});

/*
 * =========================================================
 * PASSWORD RESET CONFIRMATION
 * =========================================================
 */

describe("password-reset confirmation typed error contract", () => {
  it("does not expose backend detail for an invalid reset credential", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createResponse(400, {
        code: AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,

        body: {
          detail: "INTERNAL_RESET_STATE_SENTINEL",
        },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      confirmPasswordReset("x".repeat(32), "AnotherSecurePassword456!"),
    ).rejects.toMatchObject({
      code: AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,

      status: 400,

      message: "The password reset link is invalid or expired.",
    });

    try {
      await confirmPasswordReset("x".repeat(32), "AnotherSecurePassword456!");
    } catch (error) {
      expect((error as Error).message).not.toContain(
        "INTERNAL_RESET_STATE_SENTINEL",
      );
    }
  });

  it("uses frontend-controlled text when the replacement password is rejected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createResponse(400, {
        code: AuthErrorCode.PASSWORD_RESET_PASSWORD_REJECTED,

        body: {
          detail: "INTERNAL_PASSWORD_RULE_SENTINEL",
        },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      confirmPasswordReset("x".repeat(32), "AnotherSecurePassword456!"),
    ).rejects.toMatchObject({
      code: AuthErrorCode.PASSWORD_RESET_PASSWORD_REJECTED,

      status: 400,

      message: "The new password could not be accepted.",
    });
  });
});

/*
 * =========================================================
 * AUTHENTICATED API REFRESH CONTRACT
 * =========================================================
 */

describe("apiFetch typed access-token recovery", () => {
  it("refreshes only after the backend identifies the access credential", async () => {
    setAccessToken("old-access-token");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createResponse(401, {
          code: AuthErrorCode.ACCESS_CREDENTIALS_INVALID,
        }),
      )
      .mockResolvedValueOnce(
        createResponse(200, {
          body: {
            access_token: "replacement-access-token",

            token_type: "bearer",
          },
        }),
      )
      .mockResolvedValueOnce(
        createResponse(200, {
          body: {
            result: "success",
          },
        }),
      );

    vi.stubGlobal("fetch", fetchMock);

    const response = await apiFetch("/services");

    expect(response.status).toBe(200);

    expect(fetchMock).toHaveBeenCalledTimes(3);

    expect(String(fetchMock.mock.calls[1][0])).toContain("/auth/refresh");

    expect(getAccessToken()).toBe("replacement-access-token");
  });

  it("does not send refresh credentials for an ambiguous 401", async () => {
    setAccessToken("old-access-token");

    const unauthorizedListener = vi.fn();

    window.addEventListener("opsflow:unauthorized", unauthorizedListener);

    const fetchMock = vi.fn().mockResolvedValue(createResponse(401));

    vi.stubGlobal("fetch", fetchMock);

    try {
      const response = await apiFetch("/services");

      expect(response.status).toBe(401);

      expect(fetchMock).toHaveBeenCalledTimes(1);

      expect(getAccessToken()).toBeNull();

      expect(unauthorizedListener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("opsflow:unauthorized", unauthorizedListener);
    }
  });
});
