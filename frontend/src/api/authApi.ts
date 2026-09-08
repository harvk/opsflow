import { apiFetch } from "./apiClient";

import { AuthApiError, AuthErrorCode, readAuthErrorCode } from "./authErrors";

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

/*
 * =========================================================
 * PASSWORD RESET THROTTLE ERROR
 * =========================================================
 *
 * ForgotPasswordPage already distinguishes this error so it
 * can display Retry-After information.
 *
 * Preserve that interface while attaching the stable
 * backend authentication error code.
 */

export class PasswordResetThrottleError extends AuthApiError {
  readonly retryAfterSeconds: number | null;

  constructor(message: string, retryAfterSeconds: number | null) {
    super(message, {
      code: AuthErrorCode.PASSWORD_RESET_THROTTLED,

      status: 429,
    });

    this.name = "PasswordResetThrottleError";

    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/*
 * =========================================================
 * RETRY-AFTER PARSING
 * =========================================================
 */

function readRetryAfterSeconds(response: Response): number | null {
  const retryAfterHeader = response.headers.get("Retry-After");

  if (retryAfterHeader === null) {
    return null;
  }

  const parsedRetryAfter = Number.parseInt(retryAfterHeader, 10);

  if (!Number.isFinite(parsedRetryAfter) || parsedRetryAfter <= 0) {
    return null;
  }

  return parsedRetryAfter;
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
     * Required so the browser accepts the HttpOnly
     * refresh cookie returned by FastAPI.
     */

    credentials: "include",

    headers: {
      "Content-Type": "application/x-www-form-urlencoded",

      Accept: "application/json",
    },

    body: formData,
  });

  if (!response.ok) {
    const code = readAuthErrorCode(response);

    if (code === AuthErrorCode.LOGIN_CREDENTIALS_INVALID) {
      throw new AuthApiError("Invalid email or password.", {
        code,

        status: response.status,
      });
    }

    if (code === AuthErrorCode.LOGIN_THROTTLED) {
      throw new AuthApiError(
        "Too many authentication attempts. " + "Please try again later.",
        {
          code,

          status: response.status,
        },
      );
    }

    throw new AuthApiError("Unable to sign in. Please try again.", {
      code,

      status: response.status,
    });
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
    const code = readAuthErrorCode(response);

    throw new AuthApiError("Unable to retrieve the authenticated user.", {
      code,

      status: response.status,
    });
  }

  return response.json() as Promise<AuthUser>;
}

/*
 * =========================================================
 * LOGOUT
 * =========================================================
 *
 * Use apiFetch rather than a raw fetch.
 *
 * apiFetch already owns:
 *
 *   credentials: include
 *   bearer access token
 *   readable CSRF cookie
 *   X-CSRF-Token
 *
 * This also matches AuthContext's existing architecture.
 */

export async function logoutRequest(): Promise<void> {
  const response = await apiFetch("/auth/logout", {
    method: "POST",

    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 204) {
    return;
  }

  if (!response.ok) {
    throw new AuthApiError("Unable to complete server logout.", {
      code: readAuthErrorCode(response),

      status: response.status,
    });
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

    headers: {
      "Content-Type": "application/json",

      Accept: "application/json",
    },

    body: JSON.stringify({
      email,
    }),
  });

  const code = readAuthErrorCode(response);

  /*
   * Do not infer password-reset throttling from HTTP 429
   * alone.
   *
   * The backend must explicitly identify the condition.
   */

  if (
    response.status === 429 &&
    code === AuthErrorCode.PASSWORD_RESET_THROTTLED
  ) {
    throw new PasswordResetThrottleError(
      "Too many password reset requests. " + "Please try again later.",
      readRetryAfterSeconds(response),
    );
  }

  if (!response.ok) {
    throw new AuthApiError(
      "Unable to request a password reset. " + "Please try again.",
      {
        code,

        status: response.status,
      },
    );
  }

  const body = (await response.json()) as {
    message?: unknown;
  };

  if (typeof body.message !== "string" || body.message.length === 0) {
    throw new Error(
      "The password reset service returned " + "an invalid response.",
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
     * sessions and FastAPI clears any authentication
     * cookies held by this browser.
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

  const code = readAuthErrorCode(response);

  /*
   * =======================================================
   * INVALID RESET CREDENTIAL
   * =======================================================
   *
   * Do not consume backend detail text.
   */

  if (code === AuthErrorCode.PASSWORD_RESET_CREDENTIAL_INVALID) {
    throw new AuthApiError("The password reset link is invalid or expired.", {
      code,

      status: response.status,
    });
  }

  /*
   * =======================================================
   * REPLACEMENT PASSWORD REJECTED
   * =======================================================
   */

  if (code === AuthErrorCode.PASSWORD_RESET_PASSWORD_REJECTED) {
    throw new AuthApiError("The new password could not be accepted.", {
      code,

      status: response.status,
    });
  }

  /*
   * =======================================================
   * PYDANTIC / SCHEMA VALIDATION
   * =======================================================
   *
   * HTTP 422 is framework-level request validation rather
   * than an authentication-domain error code.
   */

  if (response.status === 422) {
    throw new AuthApiError(
      "The new password does not meet the " + "required password policy.",
      {
        code,

        status: response.status,
      },
    );
  }

  throw new AuthApiError("Unable to reset the password. Please try again.", {
    code,

    status: response.status,
  });
}
