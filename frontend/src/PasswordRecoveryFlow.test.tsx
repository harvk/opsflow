import { cleanup, render, screen, waitFor } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

import { confirmPasswordReset, requestPasswordReset } from "./api/authApi";

import { useAuth } from "./auth/useAuth";

/*
 * =========================================================
 * AUTHENTICATION MOCK
 * =========================================================
 *
 * Password recovery happens while the user is generally
 * unauthenticated.
 *
 * App and the real recovery pages remain mounted.
 *
 * We mock only useAuth so LoginPage can render without an
 * actual AuthProvider or backend authentication request.
 *
 * IMPORTANT:
 *
 * The import path and vi.mock path MUST refer to the exact
 * same module:
 *
 *   import ... from "./auth/useAuth"
 *   vi.mock("./auth/useAuth")
 *
 * The previous broken file imported "../src/auth/useAuth"
 * but mocked "../auth/useAuth", so Vitest never mocked the
 * imported function.
 */

vi.mock("./auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

/*
 * =========================================================
 * PASSWORD RECOVERY API MOCK
 * =========================================================
 *
 * App, LoginPage, ForgotPasswordPage and ResetPasswordPage
 * all remain real.
 *
 * Only the two actual HTTP operations are replaced.
 *
 * This makes this an application integration test up to the
 * network boundary.
 */

vi.mock("./api/authApi", async () => {
  const actual =
    await vi.importActual<typeof import("./api/authApi")>("./api/authApi");

  return {
    ...actual,

    requestPasswordReset: vi.fn(),

    confirmPasswordReset: vi.fn(),
  };
});

/*
 * =========================================================
 * MOCK HANDLES
 * =========================================================
 */

const mockedUseAuth = vi.mocked(useAuth);

const mockedRequestPasswordReset = vi.mocked(requestPasswordReset);

const mockedConfirmPasswordReset = vi.mocked(confirmPasswordReset);

/*
 * =========================================================
 * TEST DATA
 * =========================================================
 */

const RECOVERY_EMAIL = "operator@example.com";

const RESET_TOKEN = "test-password-reset-token-2026";

const NEW_PASSWORD = "Replacement-Passphrase-2026!";

const GENERIC_RECOVERY_MESSAGE =
  "If an eligible account exists, password reset instructions will be sent.";

/*
 * =========================================================
 * AUTHENTICATION STATE
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
 * MemoryRouter keeps its routing state internally.
 *
 * This test-only element gives us visibility into the
 * current pathname and query string.
 *
 * A neutral <div> is deliberate.
 *
 * Do not use <output>, because <output> has an implicit
 * role="status" and would collide with the real accessible
 * status messages used by LoginPage/ForgotPasswordPage.
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
 * RECOVERY EMAIL SIMULATOR
 * =========================================================
 *
 * There is intentionally no PasswordRecoveryFlowPage.
 *
 * In production:
 *
 *   ForgotPasswordPage
 *       ↓
 *   backend sends email
 *       ↓
 *   user clicks email URL
 *       ↓
 *   /reset-password?token=...
 *
 * The external email system is outside the React app.
 *
 * This test-only button represents the moment the user
 * follows that recovery email back into the application.
 */

function RecoveryEmailLinkSimulator() {
  const navigate = useNavigate();

  function openRecoveryLink() {
    navigate("/reset-password" + `?token=${encodeURIComponent(RESET_TOKEN)}`);
  }

  return (
    <button
      type="button"
      data-testid="open-recovery-link"
      onClick={openRecoveryLink}
    >
      Open simulated recovery link
    </button>
  );
}

/*
 * =========================================================
 * RENDER HELPER
 * =========================================================
 */

function renderRecoveryApplication(initialPath = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />

      <LocationProbe />

      <RecoveryEmailLinkSimulator />
    </MemoryRouter>,
  );
}

/*
 * =========================================================
 * TEST ISOLATION
 * =========================================================
 */

beforeEach(() => {
  /*
   * Completely reset each mock before configuring the next
   * test.
   */

  mockedUseAuth.mockReset();

  mockedRequestPasswordReset.mockReset();

  mockedConfirmPasswordReset.mockReset();

  configureUnauthenticatedState();

  /*
   * Default successful password-reset request.
   */

  mockedRequestPasswordReset.mockResolvedValue({
    message: GENERIC_RECOVERY_MESSAGE,
  });

  /*
   * confirmPasswordReset() returns Promise<void>.
   */

  mockedConfirmPasswordReset.mockResolvedValue(undefined);
});

afterEach(() => {
  /*
   * Remove all mounted React trees so route/page state from
   * one test cannot leak into another.
   */

  cleanup();

  mockedUseAuth.mockReset();

  mockedRequestPasswordReset.mockReset();

  mockedConfirmPasswordReset.mockReset();
});

/*
 * =========================================================
 * COMPLETE PASSWORD RECOVERY FLOW
 * =========================================================
 */

describe("password recovery application lifecycle", () => {
  it("completes login-to-recovery-to-reset-to-login as one application flow", async () => {
    const user = userEvent.setup();

    /*
     * ===============================================
     * STEP 1
     *
     * Start at LoginPage.
     * ===============================================
     */

    renderRecoveryApplication("/login");

    expect(screen.getByTestId("current-location")).toHaveTextContent("/login");

    /*
     * ===============================================
     * STEP 2
     *
     * Follow the actual Forgot Password link from
     * LoginPage.
     * ===============================================
     */

    const forgotPasswordLink = screen.getByRole("link", {
      name: "Forgot password?",
    });

    expect(forgotPasswordLink).toBeInTheDocument();

    await user.click(forgotPasswordLink);

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/forgot-password",
      );
    });

    expect(
      screen.getByRole("heading", {
        name: "Forgot your password?",
      }),
    ).toBeInTheDocument();

    /*
     * ===============================================
     * STEP 3
     *
     * Submit the email through the real
     * ForgotPasswordPage.
     * ===============================================
     */

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    await user.type(emailInput, RECOVERY_EMAIL);

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    /*
     * ForgotPasswordPage should send exactly the
     * entered email into authApi.
     */

    await waitFor(() => {
      expect(mockedRequestPasswordReset).toHaveBeenCalledTimes(1);
    });

    expect(mockedRequestPasswordReset).toHaveBeenCalledWith(RECOVERY_EMAIL);

    /*
     * ===============================================
     * STEP 4
     *
     * Confirm the privacy-preserving success response.
     * ===============================================
     */

    const recoveryStatus = await screen.findByRole("status");

    expect(recoveryStatus).toHaveTextContent("Check your inbox");

    expect(recoveryStatus).toHaveTextContent(GENERIC_RECOVERY_MESSAGE);

    /*
     * ===============================================
     * STEP 5
     *
     * Simulate the user opening the recovery email.
     *
     * This is the external boundary of the frontend
     * application.
     * ===============================================
     */

    await user.click(screen.getByTestId("open-recovery-link"));

    expect(
      await screen.findByRole("heading", {
        name: "Choose a new password",
      }),
    ).toBeInTheDocument();

    /*
     * ===============================================
     * STEP 6
     *
     * ResetPasswordPage captures the token in memory
     * and removes it from the visible route.
     * ===============================================
     */

    await waitFor(() => {
      const location = screen.getByTestId("current-location");

      expect(location).toHaveTextContent("/reset-password");

      expect(location).not.toHaveTextContent("token=");

      expect(location).not.toHaveTextContent(RESET_TOKEN);
    });

    /*
     * ===============================================
     * STEP 7
     *
     * Enter a policy-compliant replacement password.
     *
     * The current ResetPasswordPage requires at least
     * 15 characters.
     * ===============================================
     */

    const newPasswordInput = screen.getByLabelText("New password");

    const confirmPasswordInput = screen.getByLabelText("Confirm new password");

    await user.type(newPasswordInput, NEW_PASSWORD);

    await user.type(confirmPasswordInput, NEW_PASSWORD);

    const resetButton = screen.getByRole("button", {
      name: "Reset password",
    });

    expect(resetButton).toBeEnabled();

    await user.click(resetButton);

    /*
     * ===============================================
     * STEP 8
     *
     * The URL no longer contains the reset credential,
     * but ResetPasswordPage must still possess its
     * in-memory copy.
     * ===============================================
     */

    await waitFor(() => {
      expect(mockedConfirmPasswordReset).toHaveBeenCalledTimes(1);
    });

    expect(mockedConfirmPasswordReset).toHaveBeenCalledWith(
      RESET_TOKEN,
      NEW_PASSWORD,
    );

    /*
     * ===============================================
     * STEP 9
     *
     * Successful confirmation navigates back to
     * LoginPage using the temporary success marker.
     * ===============================================
     */

    await waitFor(() => {
      expect(screen.getByText("Password reset complete")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Sign in again using your new password."),
    ).toBeInTheDocument();

    /*
     * ===============================================
     * STEP 10
     *
     * LoginPage consumes passwordReset=success and then
     * removes the marker from the route.
     * ===============================================
     */

    await waitFor(() => {
      const location = screen.getByTestId("current-location");

      expect(location).toHaveTextContent("/login");

      expect(location).not.toHaveTextContent("passwordReset");
    });

    /*
     * ===============================================
     * FINAL NETWORK BOUNDARY ASSERTIONS
     * ===============================================
     */

    expect(mockedRequestPasswordReset).toHaveBeenCalledTimes(1);

    expect(mockedConfirmPasswordReset).toHaveBeenCalledTimes(1);
  });

  /*
   * =====================================================
   * MISSING RESET CREDENTIAL
   * =====================================================
   */

  it("routes a tokenless reset attempt back into account recovery", async () => {
    const user = userEvent.setup();

    /*
     * Enter ResetPasswordPage without a token.
     */

    renderRecoveryApplication("/reset-password");

    expect(
      screen.getByRole("heading", {
        name: "Invalid reset link",
      }),
    ).toBeInTheDocument();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Request a new password-reset link before trying again.",
    );

    /*
     * An invalid entry must never attempt confirmation.
     */

    expect(mockedConfirmPasswordReset).not.toHaveBeenCalled();

    /*
     * Use the actual ResetPasswordPage link to return
     * to ForgotPasswordPage.
     */

    await user.click(
      screen.getByRole("link", {
        name: "Request another reset",
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/forgot-password",
      );
    });

    expect(
      screen.getByRole("heading", {
        name: "Forgot your password?",
      }),
    ).toBeInTheDocument();

    expect(mockedConfirmPasswordReset).not.toHaveBeenCalled();
  });
});
