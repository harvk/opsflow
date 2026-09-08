import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmPasswordReset,
  PasswordResetThrottleError,
  requestPasswordReset,
} from "./authApi";

import {
  AUTH_ERROR_CODE_HEADER,
  AuthApiError,
  AuthErrorCode,
} from "./authErrors";

/*
 * =========================================================
 * TEST CONFIGURATION
 * =========================================================
 *
 * Keep this synchronized with the production fallback in
 * authApi.ts.
 *
 * If VITE_API_BASE_URL is configured for the test
 * environment, use that value instead.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/*
 * =========================================================
 * FETCH MOCK
 * =========================================================
 *
 * authApi.ts intentionally uses the browser fetch API.
 *
 * Unit tests must never send real HTTP traffic to FastAPI,
 * so every test replaces fetch() with this controlled mock.
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

function authErrorResponse(
  body: unknown,
  status: number,
  code: AuthErrorCode,
  headers?: HeadersInit,
): Response {
  const responseHeaders = new Headers(headers);

  responseHeaders.set(AUTH_ERROR_CODE_HEADER, code);

  return jsonResponse(body, status, responseHeaders);
}

/*
 * =========================================================
 * TEST LIFECYCLE
 * =========================================================
 */

beforeEach(() => {
  fetchMock.mockReset();

  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/*
 * =========================================================
 * PASSWORD RESET REQUEST
 * =========================================================
 */

describe("requestPasswordReset", () => {
  it("posts the supplied email to the password-reset request endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          message:
            "If an account exists for that email, " +
            "password reset instructions have been sent.",
        },
        202,
      ),
    );

    await requestPasswordReset("user@example.com");

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/auth/password-reset/request`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",

          Accept: "application/json",
        },

        body: JSON.stringify({
          email: "user@example.com",
        }),
      },
    );
  });

  it("returns the generic message from a successful response", async () => {
    const expectedMessage =
      "If an account exists for that email, " +
      "password reset instructions have been sent.";

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          message: expectedMessage,
        },
        202,
      ),
    );

    const result = await requestPasswordReset("user@example.com");

    expect(result).toEqual({
      message: expectedMessage,
    });
  });

  it("does not require a 200 response specifically when the backend returns successful 202", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          message: "Password reset request accepted.",
        },
        202,
      ),
    );

    await expect(requestPasswordReset("user@example.com")).resolves.toEqual({
      message: "Password reset request accepted.",
    });
  });

  it("throws PasswordResetThrottleError for typed HTTP 429", async () => {
    fetchMock.mockResolvedValueOnce(
      authErrorResponse(
        {
          detail: "BACKEND THROTTLE TEXT",
        },
        429,
        AuthErrorCode.PASSWORD_RESET_THROTTLED,
        {
          "Retry-After": "120",
        },
      ),
    );

    try {
      await requestPasswordReset("user@example.com");

      throw new Error("Expected requestPasswordReset to throw.");
    } catch (error) {
      expect(error).toBeInstanceOf(PasswordResetThrottleError);

      if (error instanceof PasswordResetThrottleError) {
        expect(error.name).toBe("PasswordResetThrottleError");

        /*
         * Frontend-controlled message.
         *
         * Backend detail must not control browser text.
         */

        expect(error.message).toBe(
          "Too many password reset requests. " + "Please try again later.",
        );

        expect(error.message).not.toContain("BACKEND THROTTLE TEXT");

        expect(error.retryAfterSeconds).toBe(120);

        expect(error.code).toBe(AuthErrorCode.PASSWORD_RESET_THROTTLED);

        expect(error.status).toBe(429);
      }
    }
  });

  it("uses null retryAfterSeconds when Retry-After is missing", async () => {
    fetchMock.mockResolvedValueOnce(
      authErrorResponse(
        {
          detail: "Too many requests.",
        },
        429,
        AuthErrorCode.PASSWORD_RESET_THROTTLED,
      ),
    );

    try {
      await requestPasswordReset("user@example.com");

      throw new Error("Expected requestPasswordReset to throw.");
    } catch (error) {
      expect(error).toBeInstanceOf(PasswordResetThrottleError);

      if (error instanceof PasswordResetThrottleError) {
        expect(error.retryAfterSeconds).toBeNull();

        expect(error.code).toBe(AuthErrorCode.PASSWORD_RESET_THROTTLED);
      }
    }
  });

  it.each(["not-a-number", "0", "-1", ""])(
    "uses null retryAfterSeconds for invalid Retry-After value %j",
    async (retryAfterValue) => {
      fetchMock.mockResolvedValueOnce(
        authErrorResponse(
          {
            detail: "Too many requests.",
          },
          429,
          AuthErrorCode.PASSWORD_RESET_THROTTLED,
          {
            "Retry-After": retryAfterValue,
          },
        ),
      );

      try {
        await requestPasswordReset("user@example.com");

        throw new Error("Expected requestPasswordReset to throw.");
      } catch (error) {
        expect(error).toBeInstanceOf(PasswordResetThrottleError);

        if (error instanceof PasswordResetThrottleError) {
          expect(error.retryAfterSeconds).toBeNull();
        }
      }
    },
  );

  it("does not infer password-reset throttling from an untyped HTTP 429", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: "Too many requests.",
        },
        429,
        {
          "Retry-After": "120",
        },
      ),
    );

    try {
      await requestPasswordReset("user@example.com");

      throw new Error("Expected requestPasswordReset to throw.");
    } catch (error) {
      expect(error).toBeInstanceOf(AuthApiError);

      expect(error).not.toBeInstanceOf(PasswordResetThrottleError);

      if (error instanceof AuthApiError) {
        expect(error.code).toBeNull();

        expect(error.status).toBe(429);

        expect(error.message).toBe(
          "Unable to request a password reset. " + "Please try again.",
        );
      }
    }
  });

  it("throws a generic reset-request error for unexpected non-success responses", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: "Internal server error.",
        },
        500,
      ),
    );

    await expect(requestPasswordReset("user@example.com")).rejects.toThrow(
      "Unable to request a password reset. " + "Please try again.",
    );
  });

  it("rejects a successful response that does not contain a message", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 202));

    await expect(requestPasswordReset("user@example.com")).rejects.toThrow(
      "The password reset service returned " + "an invalid response.",
    );
  });

  it("rejects a successful response whose message is not a string", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          message: 12345,
        },
        202,
      ),
    );

    await expect(requestPasswordReset("user@example.com")).rejects.toThrow(
      "The password reset service returned " + "an invalid response.",
    );
  });

  it("rejects a successful response containing an empty message", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          message: "",
        },
        202,
      ),
    );

    await expect(requestPasswordReset("user@example.com")).rejects.toThrow(
      "The password reset service returned " + "an invalid response.",
    );
  });
});

/*
 * =========================================================
 * PASSWORD RESET CONFIRMATION
 * =========================================================
 */

describe("confirmPasswordReset", () => {
  it("posts the token and new password to the confirmation endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(null, {
        status: 204,
      }),
    );

    await confirmPasswordReset("reset-token-value", "NewSecurePassword123!");

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/auth/password-reset/confirm`,
      {
        method: "POST",

        credentials: "include",

        headers: {
          "Content-Type": "application/json",

          Accept: "application/json",
        },

        body: JSON.stringify({
          token: "reset-token-value",

          new_password: "NewSecurePassword123!",
        }),
      },
    );
  });

  it("includes browser credentials during password-reset confirmation", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(null, {
        status: 204,
      }),
    );

    await confirmPasswordReset("reset-token-value", "NewSecurePassword123!");

    const [, options] = fetchMock.mock.calls[0];

    expect(options?.credentials).toBe("include");
  });

  it("resolves successfully when the backend returns HTTP 204", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(null, {
        status: 204,
      }),
    );

    await expect(
      confirmPasswordReset("reset-token-value", "NewSecurePassword123!"),
    ).resolves.toBeUndefined();
  });

  it("does not surface backend detail for an invalid or expired reset credential", async () => {
    const backendSentinel = "INTERNAL_RESET_STATE_SENTINEL";

    fetchMock.mockResolvedValueOnce(
      authErrorResponse(
        {
          detail: backendSentinel,
        },
        400,
        AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,
      ),
    );

    try {
      await confirmPasswordReset("expired-token", "NewSecurePassword123!");

      throw new Error("Expected confirmPasswordReset to throw.");
    } catch (error) {
      expect(error).toBeInstanceOf(AuthApiError);

      if (error instanceof AuthApiError) {
        expect(error.code).toBe(
          AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,
        );

        expect(error.status).toBe(400);

        expect(error.message).toBe(
          "The password reset link is invalid or expired.",
        );

        expect(error.message).not.toContain(backendSentinel);
      }
    }
  });

  it("uses the generic invalid-or-expired message when the typed HTTP 400 body has no string detail", async () => {
    fetchMock.mockResolvedValueOnce(
      authErrorResponse(
        {
          detail: 12345,
        },
        400,
        AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,
      ),
    );

    await expect(
      confirmPasswordReset("invalid-token", "NewSecurePassword123!"),
    ).rejects.toThrow("The password reset link is invalid or expired.");
  });

  it("uses the generic invalid-or-expired message when a typed HTTP 400 body is malformed JSON", async () => {
    const headers = new Headers({
      "Content-Type": "application/json",
    });

    headers.set(
      AUTH_ERROR_CODE_HEADER,
      AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID,
    );

    fetchMock.mockResolvedValueOnce(
      new Response("this-is-not-json", {
        status: 400,

        headers,
      }),
    );

    await expect(
      confirmPasswordReset("invalid-token", "NewSecurePassword123!"),
    ).rejects.toThrow("The password reset link is invalid or expired.");
  });

  it("maps a typed replacement-password rejection to frontend-controlled text", async () => {
    const backendSentinel = "INTERNAL_PASSWORD_RULE_SENTINEL";

    fetchMock.mockResolvedValueOnce(
      authErrorResponse(
        {
          detail: backendSentinel,
        },
        400,
        AuthErrorCode.PASSWORD_RESET_PASSWORD_REJECTED,
      ),
    );

    try {
      await confirmPasswordReset("reset-token-value", "NewSecurePassword123!");

      throw new Error("Expected confirmPasswordReset to throw.");
    } catch (error) {
      expect(error).toBeInstanceOf(AuthApiError);

      if (error instanceof AuthApiError) {
        expect(error.code).toBe(AuthErrorCode.PASSWORD_RESET_PASSWORD_REJECTED);

        expect(error.status).toBe(400);

        expect(error.message).toBe("The new password could not be accepted.");

        expect(error.message).not.toContain(backendSentinel);
      }
    }
  });

  it("does not infer invalid reset credentials from an untyped HTTP 400", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: "The password reset token has expired.",
        },
        400,
      ),
    );

    await expect(
      confirmPasswordReset("invalid-token", "NewSecurePassword123!"),
    ).rejects.toThrow("Unable to reset the password. " + "Please try again.");
  });

  it("maps HTTP 422 to the password-policy error", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: "Password validation failed.",
        },
        422,
      ),
    );

    await expect(
      confirmPasswordReset("reset-token-value", "short"),
    ).rejects.toThrow(
      "The new password does not meet the " + "required password policy.",
    );
  });

  it.each([401, 403, 404, 409, 500, 502, 503])(
    "maps unexpected HTTP %i responses to the generic reset error",
    async (status) => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(
          {
            detail: "Unexpected response.",
          },
          status,
        ),
      );

      await expect(
        confirmPasswordReset("reset-token-value", "NewSecurePassword123!"),
      ).rejects.toThrow("Unable to reset the password. " + "Please try again.");
    },
  );
});
