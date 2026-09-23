import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import { registerAccount } from "../api/authApi";
import { RegisterPage } from "./RegisterPage";

vi.mock("../api/authApi", () => ({
  registerAccount: vi.fn(),
}));

const mockedRegisterAccount = vi.mocked(registerAccount);

function LocationProbe() {
  const location = useLocation();

  return (
    <div data-testid="current-location" aria-hidden="true">
      {location.pathname}
      {location.search}
    </div>
  );
}

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <RegisterPage />
      <LocationProbe />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockedRegisterAccount.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("RegisterPage", () => {
  it("renders an email-and-password account creation form", () => {
    renderRegisterPage();

    expect(
      screen.getByRole("heading", { name: /set up your workspace access/i }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeInTheDocument();
  });

  it("submits a normalized email with the selected password", async () => {
    const user = userEvent.setup();

    mockedRegisterAccount.mockResolvedValueOnce({
      id: "d8981ce5-26e9-4f4f-b423-8bd4e1d401c9",
      email: "new.user@example.com",
      full_name: "new.user",
      role: "viewer",
      is_active: true,
    });

    renderRegisterPage();

    await user.type(
      screen.getByLabelText(/email address/i),
      "  New.User@Example.com  ",
    );
    await user.type(
      screen.getByLabelText(/^password$/i),
      "VerySecurePassword123!",
    );
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "VerySecurePassword123!",
    );
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockedRegisterAccount).toHaveBeenCalledWith({
        email: "new.user@example.com",
        password: "VerySecurePassword123!",
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("current-location")).toHaveTextContent(
        "/login?accountCreated=success",
      );
    });
  });

  it("rejects mismatched passwords before sending a request", async () => {
    const user = userEvent.setup();

    renderRegisterPage();

    await user.type(
      screen.getByLabelText(/email address/i),
      "user@example.com",
    );
    await user.type(
      screen.getByLabelText(/^password$/i),
      "VerySecurePassword123!",
    );
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "DifferentPassword123!",
    );
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(
      await screen.findByText(/password confirmation does not match/i),
    ).toBeInTheDocument();
    expect(mockedRegisterAccount).not.toHaveBeenCalled();
  });
});
