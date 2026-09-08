import { cleanup, render, screen } from "@testing-library/react";

import { MemoryRouter } from "react-router-dom";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

import { useAuth } from "./auth/useAuth";

/*
 * =========================================================
 * AUTHENTICATION MOCK
 * =========================================================
 *
 * ProtectedRoute remains real.
 *
 * Only useAuth is mocked so these tests exercise:
 *
 *   App.tsx
 *       +
 *   ProtectedRoute.tsx
 *
 * without making real authentication requests.
 */

vi.mock("./auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

/*
 * =========================================================
 * PAGE MOCKS
 * =========================================================
 *
 * Individual pages already have their own component tests.
 *
 * This suite is concerned only with determining WHICH page
 * React Router renders for a given route/authentication
 * state.
 */

vi.mock("./pages/LoginPage", () => ({
  LoginPage: () => <h1>Login route</h1>,
}));

vi.mock("./pages/ForgotPasswordPage", () => ({
  ForgotPasswordPage: () => <h1>Forgot password route</h1>,
}));

vi.mock("./pages/ResetPasswordPage", () => ({
  ResetPasswordPage: () => <h1>Reset password route</h1>,
}));

vi.mock("./pages/OverviewPage", () => ({
  default: () => <h1>Overview route</h1>,
}));

vi.mock("./pages/ServicesPage", () => ({
  default: () => <h1>Services route</h1>,
}));

vi.mock("./pages/ServiceDetailsPage", () => ({
  default: () => <h1>Service details route</h1>,
}));

vi.mock("./pages/ReportIncidentPage", () => ({
  default: () => <h1>Report incident route</h1>,
}));

vi.mock("./pages/NotFoundPage", () => ({
  default: () => <h1>Not found route</h1>,
}));

/*
 * =========================================================
 * APP LAYOUT CHILD MOCKS
 * =========================================================
 *
 * AppLayout remains real.
 *
 * That is useful because the test still exercises its
 * nested <Outlet /> behavior.
 *
 * Header and sidebar rendering are unrelated to this route
 * regression suite, so they are replaced with lightweight
 * components.
 */

vi.mock("./components/AppHeader", () => ({
  default: () => <div>Application header</div>,
}));

vi.mock("./components/AppSidebar", () => ({
  default: () => <nav>Application sidebar</nav>,
}));

/*
 * =========================================================
 * MOCK HANDLE
 * =========================================================
 */

const mockedUseAuth = vi.mocked(useAuth);

/*
 * =========================================================
 * AUTHENTICATION CONFIGURATION
 * =========================================================
 */

interface AuthenticationConfiguration {
  isAuthenticated?: boolean;

  isInitializing?: boolean;
}

function configureAuthentication({
  isAuthenticated = false,
  isInitializing = false,
}: AuthenticationConfiguration = {}) {
  mockedUseAuth.mockReturnValue({
    user: null,

    isAuthenticated,

    isInitializing,

    login: vi.fn(async () => undefined),

    logout: vi.fn(async () => undefined),
  });
}

/*
 * =========================================================
 * RENDER HELPER
 * =========================================================
 */

function renderApplicationAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

/*
 * =========================================================
 * GLOBAL TEST CLEANUP
 * =========================================================
 *
 * This is important.
 *
 * Without explicit cleanup, a page rendered during one test
 * can remain in document.body during the next test.
 *
 * Example:
 *
 * authenticated /services test
 *     ↓
 * <h1>Services route</h1>
 *
 * initialization test starts
 *     ↓
 * loading status is rendered
 *
 * BUT stale Services route remains in the DOM
 *     ↓
 * false test failure
 *
 * We therefore unmount every Testing Library render and
 * completely reset useAuth after EVERY test.
 */

afterEach(() => {
  cleanup();

  mockedUseAuth.mockReset();
});

/*
 * =========================================================
 * PUBLIC AUTHENTICATION ROUTES
 * =========================================================
 */

describe("App public authentication routes", () => {
  beforeEach(() => {
    mockedUseAuth.mockReset();

    configureAuthentication({
      isAuthenticated: false,
      isInitializing: false,
    });
  });

  it("renders the login route without authentication", () => {
    renderApplicationAt("/login");

    expect(
      screen.getByRole("heading", {
        name: "Login route",
      }),
    ).toBeInTheDocument();
  });

  it("renders forgot-password without authentication", () => {
    renderApplicationAt("/forgot-password");

    expect(
      screen.getByRole("heading", {
        name: "Forgot password route",
      }),
    ).toBeInTheDocument();
  });

  it("renders reset-password without authentication", () => {
    renderApplicationAt("/reset-password?token=test-reset-token");

    expect(
      screen.getByRole("heading", {
        name: "Reset password route",
      }),
    ).toBeInTheDocument();
  });

  it("does not force forgot-password through ProtectedRoute", () => {
    renderApplicationAt("/forgot-password");

    expect(
      screen.queryByRole("heading", {
        name: "Login route",
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Forgot password route",
      }),
    ).toBeInTheDocument();
  });

  it("does not force reset-password through ProtectedRoute", () => {
    renderApplicationAt("/reset-password?token=recovery-credential");

    expect(
      screen.queryByRole("heading", {
        name: "Login route",
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Reset password route",
      }),
    ).toBeInTheDocument();
  });
});

/*
 * =========================================================
 * PROTECTED APPLICATION ROUTES
 * =========================================================
 */

describe("App protected route boundary", () => {
  beforeEach(() => {
    mockedUseAuth.mockReset();
  });

  it("redirects an unauthenticated user from a protected route to login", async () => {
    configureAuthentication({
      isAuthenticated: false,
      isInitializing: false,
    });

    renderApplicationAt("/services");

    expect(
      await screen.findByRole("heading", {
        name: "Login route",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Services route",
      }),
    ).not.toBeInTheDocument();
  });

  it("renders a protected route for an authenticated user", () => {
    configureAuthentication({
      isAuthenticated: true,
      isInitializing: false,
    });

    renderApplicationAt("/services");

    expect(
      screen.getByRole("heading", {
        name: "Services route",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Login route",
      }),
    ).not.toBeInTheDocument();
  });

  it("shows the authentication initialization state before resolving a protected route", () => {
    configureAuthentication({
      isAuthenticated: false,
      isInitializing: true,
    });

    renderApplicationAt("/services");

    expect(screen.getByRole("status")).toHaveTextContent("Loading OpsFlow...");

    expect(
      screen.queryByRole("heading", {
        name: "Services route",
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Login route",
      }),
    ).not.toBeInTheDocument();
  });
});
