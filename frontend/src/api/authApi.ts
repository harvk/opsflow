import { apiFetch } from "./apiClient";
import type { AuthToken, AuthUser, LoginCredentials } from "../types/auth";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function loginRequest(
  credentials: LoginCredentials,
): Promise<AuthToken> {
  const formData = new URLSearchParams();

  formData.set("username", credentials.email);
  formData.set("password", credentials.password);

  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData,
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Invalid email or password.");
    }

    throw new Error("Unable to sign in. Please try again.");
  }

  return response.json() as Promise<AuthToken>;
}

export async function getCurrentUserRequest(): Promise<AuthUser> {
  const response = await apiFetch("/auth/me");

  if (!response.ok) {
    throw new Error("Unable to retrieve the authenticated user.");
  }

  return response.json() as Promise<AuthUser>;
}
