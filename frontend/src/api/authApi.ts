import { addCsrfHeader, apiFetch } from "./apiClient";

import type { AuthToken, AuthUser, LoginCredentials } from "../types/auth";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/*
 * =========================================================
 * PASSWORD RESET TYPES
 * =========================================================
 */

export interface PasswordResetRequestResponse {
  message: string;
}

export class PasswordResetThrottleError extends Error {
  readonly retryAfterSeconds: number | null;

  constructor(message: string, retryAfterSeconds: number | null) {
    super(message);

    this.name = "PasswordResetThrottleError";

    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/*
 * =========================================================
 * LOGIN
 * =========================================================
 */

export async function loginRequest(
  credentials: LoginCredentials,
): Promise<AuthToken> {
  const formData = new URLSearchParams();

  formData.set("username", credentials.email);

  formData.set("password", credentials.password);

  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST",

    /*
     * Required so the browser accepts:
     *
     *   HttpOnly refresh cookie
     *   readable CSRF cookie
     *
     * returned by FastAPI.
     */

    credentials: "include",

    headers: {
      "Content-Type": "application/x-www-form-urlencoded",

      Accept: "application/json",
    },

    body: formData,
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Invalid email or password.");
    }

    if (response.status === 429) {
      throw new Error("Too many sign-in attempts. Please try again later.");
    }

    throw new Error("Unable to sign in. Please try again.");
  }

  return response.json() as Promise<AuthToken>;
}

/*
 * =========================================================
 * CURRENT USER
 * =========================================================
 */

export async function getCurrentUserRequest(): Promise<AuthUser> {
  const response = await apiFetch("/auth/me");

  if (!response.ok) {
    throw new Error("Unable to retrieve the authenticated user.");
  }

  return response.json() as Promise<AuthUser>;
}

/*
 * =========================================================
 * LOGOUT
 * =========================================================
 *
 * Logout deliberately uses direct fetch() instead of
 * apiFetch().
 *
 * Why?
 *
 * Logout is a cookie-session mutation:
 *
 *   HttpOnly refresh cookie
 *       +
 *   readable CSRF cookie
 *       +
 *   X-CSRF-Token header
 *
 * We do not want an unsuccessful logout to initiate the
 * ordinary protected-request refresh/retry cycle.
 */

export async function logoutRequest(): Promise<void> {
  /*
   * This is the missing piece from the previous version.
   *
   * addCsrfHeader() reads:
   *
   *     opsflow_csrf
   *
   * from document.cookie and places the exact value into:
   *
   *     X-CSRF-Token
   */

  const headers = addCsrfHeader(
    new Headers({
      Accept: "application/json",
    }),
    "POST",
  );

  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",

    /*
     * Sends the browser-managed HttpOnly refresh
     * credential and the readable CSRF cookie.
     */

    credentials: "include",

    /*
     * Explicitly sends the CSRF header generated above.
     */

    headers,
  });

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error(
        "Logout was rejected because the browser session " +
          "could not provide valid CSRF proof.",
      );
    }

    throw new Error("Unable to complete server logout.");
  }
}

/*
 * =========================================================
 * PASSWORD RESET REQUEST
 * =========================================================
 */

export async function requestPasswordReset(
  email: string,
): Promise<PasswordResetRequestResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/password-reset/request`, {
    method: "POST",

    /*
     * This endpoint is intentionally anonymous.
     *
     * It does not depend on the browser refresh cookie
     * and therefore does not require the session CSRF
     * proof used by refresh/logout.
     */

    headers: {
      "Content-Type": "application/json",

      Accept: "application/json",
    },

    body: JSON.stringify({
      email,
    }),
  });

  if (response.status === 429) {
    const retryAfterHeader = response.headers.get("Retry-After");

    const parsedRetryAfter =
      retryAfterHeader === null ? null : Number.parseInt(retryAfterHeader, 10);

    const retryAfterSeconds =
      parsedRetryAfter !== null &&
      Number.isFinite(parsedRetryAfter) &&
      parsedRetryAfter > 0
        ? parsedRetryAfter
        : null;

    throw new PasswordResetThrottleError(
      "Too many password reset requests. " + "Please try again later.",
      retryAfterSeconds,
    );
  }

  if (!response.ok) {
    throw new Error(
      "Unable to request a password reset. " + "Please try again.",
    );
  }

  const body = (await response.json()) as {
    message?: unknown;
  };

  if (typeof body.message !== "string" || body.message.length === 0) {
    throw new Error(
      "The password reset service " + "returned an invalid response.",
    );
  }

  return {
    message: body.message,
  };
}

/*
 * =========================================================
 * PASSWORD RESET CONFIRMATION
 * =========================================================
 */

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/password-reset/confirm`, {
    method: "POST",

    /*
     * Confirmation revokes persistent authentication
     * sessions and FastAPI clears authentication
     * cookies held by this browser.
     *
     * credentials: "include" allows those Set-Cookie
     * deletion headers to update the browser.
     */

    credentials: "include",

    headers: {
      "Content-Type": "application/json",

      Accept: "application/json",
    },

    body: JSON.stringify({
      token,

      new_password: newPassword,
    }),
  });

  if (response.status === 204) {
    return;
  }

  if (response.status === 400) {
    let detail: string | undefined;

    try {
      const body = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      /*
       * Fall through to the generic reset error.
       */
    }

    throw new Error(detail ?? "The password reset link is invalid or expired.");
  }

  if (response.status === 422) {
    throw new Error(
      "The new password does not meet " + "the required password policy.",
    );
  }

  throw new Error("Unable to reset the password. " + "Please try again.");
}
