import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { confirmPasswordReset } from "../api/authApi";

import { ResetPasswordPage } from "./ResetPasswordPage";

/*
 * =========================================================
 * AUTH API MOCK
 * =========================================================
 *
 * ResetPasswordPage should be tested independently from the
 * real HTTP implementation.
 *
 * authApi.test.ts already verifies the actual transport
 * contract for confirmPasswordReset().
 *
 * Here we test how the React component reacts to success,
 * failure, validation, pending state, and navigation.
 */

vi.mock("../api/authApi", async () => {
  const actual =
    await vi.importActual<typeof import("../api/authApi")>("../api/authApi");

  return {
    ...actual,

    confirmPasswordReset: vi.fn(),
  };
});

const confirmPasswordResetMock = vi.mocked(confirmPasswordReset);

/*
 * =========================================================
 * TEST CONSTANTS
 * =========================================================
 */

const VALID_PASSWORD = "CorrectHorseBatteryStaple!";

const DIFFERENT_VALID_PASSWORD = "DifferentSecurePassword123!";

/*
 * =========================================================
 * LOCATION PROBE
 * =========================================================
 *
 * This gives the tests visibility into React Router's
 * current location.
 *
 * It is especially important here because ResetPasswordPage
 * deliberately removes the reset token from the visible URL
 * immediately after capturing it.
 */

function LocationProbe() {
  const location = useLocation();

  return (
    <output data-testid="current-location">
      {location.pathname}
      {location.search}
    </output>
  );
}

/*
 * =========================================================
 * RENDER HELPER
 * =========================================================
 */

function renderResetPasswordPage(
  initialEntry = "/reset-password?token=test-reset-token",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LocationProbe />

      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/*
         * Lightweight route destinations let us verify
         * navigation without rendering the entire real
         * application.
         */}

        <Route path="/login" element={<div>Login destination</div>} />

        <Route
          path="/forgot-password"
          element={<div>Forgot password destination</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/*
 * =========================================================
 * FORM HELPER
 * =========================================================
 */

function getResetForm(): HTMLFormElement {
  const submitButton = screen.getByRole("button", {
    name: "Reset password",
  });

  const form = submitButton.closest("form");

  if (!(form instanceof HTMLFormElement)) {
    throw new Error("Reset password form was not found.");
  }

  return form;
}

/*
 * =========================================================
 * DEFERRED PROMISE HELPER
 * =========================================================
 *
 * This lets a test deliberately hold the API request open
 * while examining the pending UI.
 */

function createDeferred<T>() {
  let resolve!: (value: T) => void;

  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;

    reject = promiseReject;
  });

  return {
    promise,
    resolve,
    reject,
  };
}

/*
 * =========================================================
 * TEST LIFECYCLE
 * =========================================================
 */

beforeEach(() => {
  confirmPasswordResetMock.mockReset();
});

afterEach(() => {
  cleanup();
});

/*
 * =========================================================
 * VALID RESET FORM RENDERING
 * =========================================================
 */

describe("ResetPasswordPage rendering", () => {
  it("renders the password reset form when a reset token is supplied", () => {
    renderResetPasswordPage();

    expect(
      screen.getByRole("heading", {
        name: "Choose a new password",
      }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("New password")).toBeInTheDocument();

    expect(screen.getByLabelText("Confirm new password")).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeInTheDocument();
  });

  it("configures both fields for new-password entry", () => {
    renderResetPasswordPage();

    const newPassword = screen.getByLabelText("New password");

    const confirmPassword = screen.getByLabelText("Confirm new password");

    expect(newPassword).toHaveAttribute("type", "password");

    expect(newPassword).toHaveAttribute("autocomplete", "new-password");

    expect(newPassword).toHaveAttribute("minlength", "15");

    expect(newPassword).toHaveAttribute("maxlength", "128");

    expect(confirmPassword).toHaveAttribute("type", "password");

    expect(confirmPassword).toHaveAttribute("autocomplete", "new-password");

    expect(confirmPassword).toHaveAttribute("minlength", "15");

    expect(confirmPassword).toHaveAttribute("maxlength", "128");
  });

  it("starts with the reset button disabled", () => {
    renderResetPasswordPage();

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeDisabled();
  });

  it("links back to the login route", () => {
    renderResetPasswordPage();

    expect(
      screen.getByRole("link", {
        name: /return to sign in/i,
      }),
    ).toHaveAttribute("href", "/login");
  });
});

/*
 * =========================================================
 * RESET TOKEN PROTECTION
 * =========================================================
 */

describe("ResetPasswordPage reset-token handling", () => {
  it("removes the reset token from the visible URL after capturing it", async () => {
    renderResetPasswordPage(
      "/reset-password?token=highly-sensitive-reset-token",
    );

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/reset-password",
      );

      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "token=",
      );

      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "highly-sensitive-reset-token",
      );
    });
  });

  it("retains the captured reset credential in component memory after removing it from the URL", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockResolvedValueOnce(undefined);

    renderResetPasswordPage("/reset-password?token=original-reset-token");

    /*
     * First prove that the credential disappeared from
     * the browser-visible location.
     */

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/reset-password",
      );

      expect(screen.getByTestId("current-location")).not.toHaveTextContent(
        "token=",
      );
    });

    /*
     * Then complete recovery.
     *
     * The API should still receive the original token
     * that was captured before URL sanitization.
     */

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    await waitFor(() => {
      expect(confirmPasswordResetMock).toHaveBeenCalledWith(
        "original-reset-token",
        VALID_PASSWORD,
      );
    });
  });
});

/*
 * =========================================================
 * INVALID / MISSING RESET TOKEN
 * =========================================================
 */

describe("ResetPasswordPage invalid reset link", () => {
  it("shows the invalid-link state when no reset token exists", () => {
    renderResetPasswordPage("/reset-password");

    expect(
      screen.getByRole("heading", {
        name: "Invalid reset link",
      }),
    ).toBeInTheDocument();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Request a new password-reset link before trying again.",
    );

    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();

    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("treats an empty token as an invalid reset credential", () => {
    renderResetPasswordPage("/reset-password?token=");

    expect(
      screen.getByRole("heading", {
        name: "Invalid reset link",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", {
        name: "Reset password",
      }),
    ).not.toBeInTheDocument();
  });

  it("provides links to request another reset or return to login", () => {
    renderResetPasswordPage("/reset-password");

    expect(
      screen.getByRole("link", {
        name: "Request another reset",
      }),
    ).toHaveAttribute("href", "/forgot-password");

    expect(
      screen.getByRole("link", {
        name: /return to sign in/i,
      }),
    ).toHaveAttribute("href", "/login");
  });
});

/*
 * =========================================================
 * PASSWORD POLICY UI
 * =========================================================
 */

describe("ResetPasswordPage password policy", () => {
  it("shows the live password-length counter", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    expect(screen.getByText("0/128")).toBeInTheDocument();

    await user.type(screen.getByLabelText("New password"), "123456789012345");

    expect(screen.getByText("15/128")).toBeInTheDocument();
  });

  it("keeps submission disabled when the password is shorter than 15 characters", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), "too-short");

    await user.type(screen.getByLabelText("Confirm new password"), "too-short");

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeDisabled();

    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("defensively rejects a programmatic submission below the minimum length", () => {
    renderResetPasswordPage();

    fireEvent.change(screen.getByLabelText("New password"), {
      target: {
        value: "too-short",
      },
    });

    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: {
        value: "too-short",
      },
    });

    fireEvent.submit(getResetForm());

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your new password must contain at least 15 characters.",
    );

    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("defensively rejects passwords longer than 128 characters", () => {
    const tooLongPassword = "a".repeat(129);

    renderResetPasswordPage();

    /*
     * fireEvent.change intentionally bypasses normal
     * user typing constraints so we can test the
     * component's defensive validation branch.
     */

    fireEvent.change(screen.getByLabelText("New password"), {
      target: {
        value: tooLongPassword,
      },
    });

    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: {
        value: tooLongPassword,
      },
    });

    fireEvent.submit(getResetForm());

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your new password must not exceed 128 characters.",
    );

    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("shows the mismatch state when password confirmation differs", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      DIFFERENT_VALID_PASSWORD,
    );

    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeDisabled();
  });

  it("defensively rejects a programmatic submission when passwords do not match", () => {
    renderResetPasswordPage();

    fireEvent.change(screen.getByLabelText("New password"), {
      target: {
        value: VALID_PASSWORD,
      },
    });

    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: {
        value: DIFFERENT_VALID_PASSWORD,
      },
    });

    fireEvent.submit(getResetForm());

    expect(screen.getByRole("alert")).toHaveTextContent(
      "The password confirmation does not match.",
    );

    expect(confirmPasswordResetMock).not.toHaveBeenCalled();
  });

  it("enables submission when both valid passwords match", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    expect(screen.getByText("✓ Passwords match.")).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeEnabled();
  });
});

/*
 * =========================================================
 * PASSWORD VISIBILITY
 * =========================================================
 */

describe("ResetPasswordPage password visibility", () => {
  it("toggles visibility of the new password independently", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    const input = screen.getByLabelText("New password");

    const toggle = screen.getByRole("button", {
      name: "Show new password",
    });

    expect(input).toHaveAttribute("type", "password");

    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await user.click(toggle);

    expect(input).toHaveAttribute("type", "text");

    expect(
      screen.getByRole("button", {
        name: "Hide new password",
      }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles visibility of the confirmation password independently", async () => {
    const user = userEvent.setup();

    renderResetPasswordPage();

    const input = screen.getByLabelText("Confirm new password");

    expect(input).toHaveAttribute("type", "password");

    await user.click(
      screen.getByRole("button", {
        name: "Show password confirmation",
      }),
    );

    expect(input).toHaveAttribute("type", "text");

    expect(
      screen.getByRole("button", {
        name: "Hide password confirmation",
      }),
    ).toHaveAttribute("aria-pressed", "true");
  });
});

/*
 * =========================================================
 * SUCCESSFUL PASSWORD RESET
 * =========================================================
 */

describe("ResetPasswordPage successful submission", () => {
  it("submits the captured token and new password exactly once", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockResolvedValueOnce(undefined);

    renderResetPasswordPage("/reset-password?token=real-reset-token");

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    await waitFor(() => {
      expect(confirmPasswordResetMock).toHaveBeenCalledTimes(1);
    });

    expect(confirmPasswordResetMock).toHaveBeenCalledWith(
      "real-reset-token",
      VALID_PASSWORD,
    );
  });

  it("redirects to login with the password-reset success marker", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockResolvedValueOnce(undefined);

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(await screen.findByText("Login destination")).toBeInTheDocument();

    expect(screen.getByTestId("current-location")).toHaveTextContent(
      "/login?passwordReset=success",
    );
  });
});

/*
 * =========================================================
 * PENDING SUBMISSION STATE
 * =========================================================
 */

describe("ResetPasswordPage pending state", () => {
  it("disables password fields and the submit button while confirmation is pending", async () => {
    const user = userEvent.setup();

    const deferred = createDeferred<void>();

    confirmPasswordResetMock.mockReturnValueOnce(deferred.promise);

    renderResetPasswordPage();

    const newPassword = screen.getByLabelText("New password");

    const confirmPassword = screen.getByLabelText("Confirm new password");

    await user.type(newPassword, VALID_PASSWORD);

    await user.type(confirmPassword, VALID_PASSWORD);

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(newPassword).toBeDisabled();

    expect(confirmPassword).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: /securing account/i,
      }),
    ).toBeDisabled();

    await act(async () => {
      deferred.resolve(undefined);

      await deferred.promise;
    });

    expect(await screen.findByText("Login destination")).toBeInTheDocument();
  });

  it("prevents duplicate submissions while reset confirmation is pending", async () => {
    const user = userEvent.setup();

    const deferred = createDeferred<void>();

    confirmPasswordResetMock.mockReturnValueOnce(deferred.promise);

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    const form = getResetForm();

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(confirmPasswordResetMock).toHaveBeenCalledTimes(1);

    /*
     * Programmatically attempt another form submission.
     *
     * handleSubmit() should reject it because
     * isSubmitting is already true.
     */

    fireEvent.submit(form);

    expect(confirmPasswordResetMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.reject(new Error("Test cleanup failure."));

      try {
        await deferred.promise;
      } catch {
        /*
         * Expected rejection.
         */
      }
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Test cleanup failure.",
    );
  });
});

/*
 * =========================================================
 * API ERROR HANDLING
 * =========================================================
 */

describe("ResetPasswordPage API errors", () => {
  it("renders invalid or expired token errors from the API", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce(
      new Error("The password reset link is invalid or expired."),
    );

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    const alert = await screen.findByRole("alert");

    expect(alert).toHaveTextContent(
      "The password reset link is invalid or expired.",
    );

    expect(alert).toHaveAttribute("aria-live", "assertive");
  });

  it("renders backend password-policy errors", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce(
      new Error("The new password does not meet the required password policy."),
    );

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The new password does not meet the required password policy.",
    );
  });

  it("uses a generic fallback when a non-Error value is thrown", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce("unexpected failure");

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reset the password.",
    );
  });

  it("re-enables the form after an unsuccessful request", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce(
      new Error("Unable to reset the password. Please try again."),
    );

    renderResetPasswordPage();

    const newPassword = screen.getByLabelText("New password");

    const confirmPassword = screen.getByLabelText("Confirm new password");

    await user.type(newPassword, VALID_PASSWORD);

    await user.type(confirmPassword, VALID_PASSWORD);

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    await screen.findByRole("alert");

    expect(newPassword).toBeEnabled();

    expect(confirmPassword).toBeEnabled();

    expect(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    ).toBeEnabled();
  });
});

/*
 * =========================================================
 * ERROR STATE TRANSITIONS
 * =========================================================
 */

describe("ResetPasswordPage error-state transitions", () => {
  it("clears a previous error when the new-password field changes", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce(
      new Error("The password reset link is invalid or expired."),
    );

    renderResetPasswordPage();

    const newPassword = screen.getByLabelText("New password");

    await user.type(newPassword, VALID_PASSWORD);

    await user.type(
      screen.getByLabelText("Confirm new password"),
      VALID_PASSWORD,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.type(newPassword, "X");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("clears a previous error when the confirmation field changes", async () => {
    const user = userEvent.setup();

    confirmPasswordResetMock.mockRejectedValueOnce(
      new Error("Unable to reset the password. Please try again."),
    );

    renderResetPasswordPage();

    await user.type(screen.getByLabelText("New password"), VALID_PASSWORD);

    const confirmPassword = screen.getByLabelText("Confirm new password");

    await user.type(confirmPassword, VALID_PASSWORD);

    await user.click(
      screen.getByRole("button", {
        name: "Reset password",
      }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.type(confirmPassword, "X");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
