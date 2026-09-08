import { act, cleanup, render, screen, waitFor } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryRouter } from "react-router-dom";

import {
  PasswordResetThrottleError,
  requestPasswordReset,
} from "../api/authApi";

import { ForgotPasswordPage } from "./ForgotPasswordPage";

/*
 * =========================================================
 * AUTH API MOCK
 * =========================================================
 *
 * Preserve the real PasswordResetThrottleError class.
 *
 * That matters because ForgotPasswordPage uses:
 *
 *   error instanceof PasswordResetThrottleError
 *
 * Replacing the class with a fake implementation could make
 * the component test something different from production.
 *
 * Only requestPasswordReset() itself is mocked.
 */

vi.mock("../api/authApi", async () => {
  const actual =
    await vi.importActual<typeof import("../api/authApi")>("../api/authApi");

  return {
    ...actual,

    requestPasswordReset: vi.fn(),
  };
});

const requestPasswordResetMock = vi.mocked(requestPasswordReset);

/*
 * =========================================================
 * TEST HELPERS
 * =========================================================
 */

function renderForgotPasswordPage() {
  return render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

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
  requestPasswordResetMock.mockReset();
});

afterEach(() => {
  cleanup();
});

/*
 * =========================================================
 * INITIAL RENDERING
 * =========================================================
 */

describe("ForgotPasswordPage rendering", () => {
  it("renders the account recovery form", () => {
    renderForgotPasswordPage();

    expect(
      screen.getByRole("heading", {
        name: "Forgot your password?",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: /return to sign in/i,
      }),
    ).toBeInTheDocument();
  });

  it("configures the email field for account recovery", () => {
    renderForgotPasswordPage();

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    expect(emailInput).toHaveAttribute("type", "email");

    expect(emailInput).toHaveAttribute("name", "email");

    expect(emailInput).toHaveAttribute("autocomplete", "email");

    expect(emailInput).toHaveAttribute("required");

    expect(emailInput).toHaveAttribute("maxlength", "320");

    expect(emailInput).toHaveAttribute(
      "aria-describedby",
      "password-reset-email-help",
    );
  });

  it("renders the privacy-preserving account-enumeration guidance", () => {
    renderForgotPasswordPage();

    expect(
      screen.getByText(
        /opsflow will not confirm whether an account exists for this address/i,
      ),
    ).toBeInTheDocument();
  });

  it("links back to the public login route", () => {
    renderForgotPasswordPage();

    const loginLink = screen.getByRole("link", {
      name: /return to sign in/i,
    });

    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("does not render a success or error alert initially", () => {
    renderForgotPasswordPage();

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

/*
 * =========================================================
 * SUCCESSFUL SUBMISSION
 * =========================================================
 */

describe("ForgotPasswordPage successful submission", () => {
  it("submits the entered email address to requestPasswordReset", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockResolvedValueOnce({
      message:
        "If an account exists for that email, password reset instructions have been sent.",
    });

    renderForgotPasswordPage();

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    await user.type(emailInput, "user@example.com");

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    await waitFor(() => {
      expect(requestPasswordResetMock).toHaveBeenCalledTimes(1);
    });

    expect(requestPasswordResetMock).toHaveBeenCalledWith("user@example.com");
  });

  it("displays the generic server response in an accessible status region", async () => {
    const user = userEvent.setup();

    const message =
      "If an account exists for that email, password reset instructions have been sent.";

    requestPasswordResetMock.mockResolvedValueOnce({
      message,
    });

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    const status = await screen.findByRole("status");

    expect(status).toHaveAttribute("aria-live", "polite");

    expect(status).toHaveTextContent("Check your inbox");

    expect(status).toHaveTextContent(message);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

/*
 * =========================================================
 * PENDING REQUEST STATE
 * =========================================================
 */

describe("ForgotPasswordPage pending state", () => {
  it("disables the input and submit button while the request is pending", async () => {
    const user = userEvent.setup();

    const deferred = createDeferred<{
      message: string;
    }>();

    requestPasswordResetMock.mockReturnValueOnce(deferred.promise);

    renderForgotPasswordPage();

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    const submitButton = screen.getByRole("button", {
      name: "Send reset instructions",
    });

    await user.type(emailInput, "user@example.com");

    await user.click(submitButton);

    expect(emailInput).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: /sending instructions/i,
      }),
    ).toBeDisabled();

    await act(async () => {
      deferred.resolve({
        message: "Reset instructions requested.",
      });

      await deferred.promise;
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: "Send reset instructions",
        }),
      ).toBeEnabled();
    });

    expect(emailInput).toBeEnabled();
  });

  it("prevents duplicate submissions while a request is already pending", async () => {
    const user = userEvent.setup();

    const deferred = createDeferred<{
      message: string;
    }>();

    requestPasswordResetMock.mockReturnValueOnce(deferred.promise);

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    const submitButton = screen.getByRole("button", {
      name: "Send reset instructions",
    });

    await user.click(submitButton);

    expect(requestPasswordResetMock).toHaveBeenCalledTimes(1);

    const pendingButton = screen.getByRole("button", {
      name: /sending instructions/i,
    });

    expect(pendingButton).toBeDisabled();

    await user.click(pendingButton);

    expect(requestPasswordResetMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.resolve({
        message: "Reset instructions requested.",
      });

      await deferred.promise;
    });
  });
});

/*
 * =========================================================
 * GENERAL ERROR HANDLING
 * =========================================================
 */

describe("ForgotPasswordPage error handling", () => {
  it("renders ordinary API errors using an accessible alert", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockRejectedValueOnce(
      new Error("Unable to request a password reset. Please try again."),
    );

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    const alert = await screen.findByRole("alert");

    expect(alert).toHaveTextContent(
      "Unable to request a password reset. Please try again.",
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("falls back to a generic error when a non-Error value is thrown", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockRejectedValueOnce("unexpected failure");

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to request a password reset.",
    );
  });

  it("re-enables the form after an unsuccessful request", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockRejectedValueOnce(
      new Error("Request failed."),
    );

    renderForgotPasswordPage();

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    await user.type(emailInput, "user@example.com");

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    await screen.findByRole("alert");

    expect(emailInput).toBeEnabled();

    expect(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    ).toBeEnabled();
  });
});

/*
 * =========================================================
 * RATE-LIMIT HANDLING
 * =========================================================
 */

describe("ForgotPasswordPage throttling", () => {
  it("displays Retry-After seconds when the backend supplies them", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockRejectedValueOnce(
      new PasswordResetThrottleError(
        "Too many password reset requests. Please try again later.",
        90,
      ),
    );

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many reset requests. Please wait approximately 90 seconds before trying again.",
    );
  });

  it("uses the throttle error message when Retry-After is unavailable", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock.mockRejectedValueOnce(
      new PasswordResetThrottleError(
        "Too many password reset requests. Please try again later.",
        null,
      ),
    );

    renderForgotPasswordPage();

    await user.type(
      screen.getByRole("textbox", {
        name: "Email address",
      }),
      "user@example.com",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many password reset requests. Please try again later.",
    );
  });
});

/*
 * =========================================================
 * STATE TRANSITIONS
 * =========================================================
 */

describe("ForgotPasswordPage message state", () => {
  it("replaces an earlier success message when a later submission fails", async () => {
    const user = userEvent.setup();

    requestPasswordResetMock
      .mockResolvedValueOnce({
        message: "Reset instructions requested.",
      })
      .mockRejectedValueOnce(
        new Error("Unable to request a password reset. Please try again."),
      );

    renderForgotPasswordPage();

    const emailInput = screen.getByRole("textbox", {
      name: "Email address",
    });

    await user.type(emailInput, "user@example.com");

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Reset instructions requested.",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Send reset instructions",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to request a password reset. Please try again.",
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
