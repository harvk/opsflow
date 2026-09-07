import { apiFetch } from "./apiClient";

import type { AuthToken, AuthUser, LoginCredentials } from "../types/auth";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/*
 * =========================================================
 * LOGIN
 * =========================================================
 *
 * Login remains a direct fetch.
 *
 * Before authentication there is not yet a CSRF cookie
 * belonging to the new authenticated session.
 *
 * A successful response establishes:
 *
 *   JSON:
 *     access_token
 *
 *   Browser cookies:
 *     HttpOnly refresh token
 *     readable signed CSRF token
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
     * Required so the browser accepts authentication
     * cookies returned by FastAPI.
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
      throw new Error("Too many sign-in attempts. Please wait and try again.");
    }

    throw new Error("Unable to sign in. Please try again.");
  }

  return response.json() as Promise<AuthToken>;
}

/*
 * =========================================================
 * CURRENT USER
 * =========================================================
 *
 * /auth/me is bearer-authenticated.
 *
 * apiFetch() supplies the access JWT through:
 *
 *   Authorization: Bearer <token>
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
 * Logout now uses apiFetch().
 *
 * apiFetch automatically supplies:
 *
 *   credentials: "include"
 *   +
 *   X-CSRF-Token
 *
 * The refresh JWT itself remains inaccessible to
 * JavaScript.
 */

export async function logoutRequest(): Promise<void> {
  const response = await apiFetch("/auth/logout", {
    method: "POST",

    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Unable to complete server logout.");
  }
}
