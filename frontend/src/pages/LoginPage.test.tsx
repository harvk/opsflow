import { cleanup, render, screen, waitFor } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { MemoryRouter, useLocation } from "react-router-dom";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

import { useAuth } from "../auth/useAuth";

/*
 * =========================================================
 * AUTHENTICATION MOCK
 * =========================================================
 *
 * LoginPage remains real.
 *
 * Only useAuth is mocked so these tests exercise the actual
 * login/recovery UI without sending authentication requests
 * to the backend.
 */

vi.mock("../auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

/*
 * =========================================================
 * AUTHENTICATION STATE HELPER
 * =========================================================
 */

function configureUnauthenticatedState() {
  mockedUseAuth.mockReturnValue({
    user: null,

    isAuthenticated: false,

    isInitializing: false,

    login: vi.fn(async () => undefined),

    logout: vi.fn(async () => undefined),
  });
}

/*
 * =========================================================
 * LOCATION PROBE
 * =========================================================
 *
 * MemoryRouter does not expose its current URL directly.
 *
 * We render the current pathname and query string into a
 * test-only element so routing transitions can be verified.
 *
 * IMPORTANT:
 *
 * Do NOT use an <output> element here.
 *
 * HTML <output> has an implicit accessibility role of
 * "status". LoginPage also deliberately exposes its
 * password-reset success message with role="status".
 *
 * Using <output> therefore creates two status regions and
 * makes screen.getByRole("status") ambiguous.
 */

function LocationProbe() {
  const location = useLocation();

  return (
    <div data-testid="current-location" aria-hidden="true">
      {location.pathname}
      {location.search}
    </div>
  );
}

/*
 * =========================================================
 * RENDER HELPER
 * =========================================================
 */

function renderLoginAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LoginPage />

      <LocationProbe />
    </MemoryRouter>,
  );
}

/*
 * =========================================================
 * TEST ISOLATION
 * =========================================================
 */

beforeEach(() => {
  mockedUseAuth.mockReset();

  configureUnauthenticatedState();
});

afterEach(() => {
  cleanup();

  mockedUseAuth.mockReset();
});

/*
 * =========================================================
 * FORGOT-PASSWORD NAVIGATION
 * =========================================================
 */

describe("LoginPage forgot-password navigation", () => {
  it("renders the forgot-password recovery link", () => {
    renderLoginAt("/login");

    const recoveryLink = screen.getByRole("link", {
      name: "Forgot password?",
    });

    expect(recoveryLink).toBeInTheDocument();

    expect(recoveryLink).toHaveAttribute("href", "/forgot-password");
  });

  it("navigates to the forgot-password route when the recovery link is selected", async () => {
    const user = userEvent.setup();

    renderLoginAt("/login");

    expect(screen.getByTestId("current-location")).toHaveTextContent("/login");

    await user.click(
      screen.getByRole("link", {
        name: "Forgot password?",
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/forgot-password",
      );
    });
  });
});

/*
 * =========================================================
 * PASSWORD-RESET SUCCESS HANDOFF
 * =========================================================
 */

describe("LoginPage password-reset completion state", () => {
  it("renders the successful password-reset notification", () => {
    renderLoginAt("/login?passwordReset=success");

    const status = screen.getByRole("status");

    expect(status).toHaveTextContent("Password reset complete");

    expect(status).toHaveTextContent("Sign in again using your new password.");
  });

  it("removes the password-reset marker from the visible URL", async () => {
    renderLoginAt("/login?passwordReset=success");

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/login",
      );

      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "passwordReset",
      );
    });
  });

  it("keeps the success notification visible after cleaning the URL", async () => {
    renderLoginAt("/login?passwordReset=success");

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "passwordReset",
      );
    });

    const status = screen.getByRole("status");

    expect(status).toHaveTextContent("Password reset complete");

    expect(status).toHaveTextContent("Sign in again using your new password.");
  });

  it("does not display the password-reset success notification during an ordinary login visit", () => {
    renderLoginAt("/login");

    expect(
      screen.queryByText("Password reset complete"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Sign in again using your new password."),
    ).not.toBeInTheDocument();
  });

  it("does not treat an arbitrary password-reset marker as a successful reset", async () => {
    renderLoginAt("/login?passwordReset=failed");

    expect(
      screen.queryByText("Password reset complete"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Sign in again using your new password."),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "passwordReset",
      );
    });
  });
});
