import { type FormEvent, useEffect, useState } from "react";

import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

import "../styles/login.css";

interface LoginLocationState {
  from?: {
    pathname?: string;
  };
}

export function LoginPage() {
  /*
   * --------------------------------------------------
   * HOOKS
   * --------------------------------------------------
   *
   * Every hook stays at the top of the component.
   *
   * There must be NO:
   *
   *   if (...)
   *   return ...
   *
   * before these hooks finish executing.
   */

  const navigate = useNavigate();
  const location = useLocation();

  const { login, isAuthenticated, isInitializing } = useAuth();

  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Sign In | OpsFlow";

    return () => {
      document.title = "OpsFlow";
    };
  }, []);

  /*
   * --------------------------------------------------
   * DERIVED VALUES
   * --------------------------------------------------
   *
   * These are NOT hooks.
   *
   * They are safe to calculate after our hooks.
   */

  const locationState = location.state as LoginLocationState | null;

  const destination = locationState?.from?.pathname ?? "/services";

  /*
   * --------------------------------------------------
   * EVENT HANDLERS
   * --------------------------------------------------
   */

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError(null);
    setIsSubmitting(true);

    try {
      await login(email.trim(), password);

      navigate(destination, {
        replace: true,
      });
    } catch (caughtError) {
      if (caughtError instanceof Error) {
        setError(caughtError.message);
      } else {
        setError("Unable to sign in. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  /*
   * --------------------------------------------------
   * CONDITIONAL RETURNS
   * --------------------------------------------------
   *
   * These deliberately come AFTER every hook.
   */

  if (isInitializing) {
    return (
      <main className="login-loading">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading authentication</span>
        </div>
      </main>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/services" replace />;
  }

  /*
   * --------------------------------------------------
   * NORMAL LOGIN UI
   * --------------------------------------------------
   */

  return (
    <main className="login-page">
      {/* Ambient background lighting */}

      <div
        className="
          login-ambient-glow
          login-ambient-glow-one
        "
        aria-hidden="true"
      />

      <div
        className="
          login-ambient-glow
          login-ambient-glow-two
        "
        aria-hidden="true"
      />

      {/* Technical grid */}

      <div className="login-grid" aria-hidden="true" />

      {/* Floating shapes */}

      <div
        className="
          floating-shape
          shape-one
        "
        aria-hidden="true"
      />

      <div
        className="
          floating-shape
          shape-two
        "
        aria-hidden="true"
      />

      <div
        className="
          floating-shape
          shape-three
        "
        aria-hidden="true"
      />

      <div
        className="
          floating-shape
          shape-four
        "
        aria-hidden="true"
      />

      <section className="login-shell">
        {/* ==============================
            LEFT BRAND PANEL
            ============================== */}

        <div className="login-brand-panel">
          <div className="login-brand-content">
            <div className="brand-mark">
              <span className="brand-mark-inner">O</span>
            </div>

            <p className="brand-eyebrow">OPERATIONS INTELLIGENCE</p>

            <h1 className="login-brand-title">
              Keep operations
              <span> moving forward.</span>
            </h1>

            <p className="login-brand-description">
              Monitor services, coordinate incidents, and maintain operational
              visibility through one secure workspace.
            </p>

            <div className="system-status-card">
              <span
                className="
                  system-status-indicator
                "
                aria-hidden="true"
              />

              <div>
                <span className="system-status-label">PLATFORM STATUS</span>

                <strong>Operational</strong>
              </div>
            </div>
          </div>

          <div
            className="
              brand-orbit
              brand-orbit-one
            "
            aria-hidden="true"
          />

          <div
            className="
              brand-orbit
              brand-orbit-two
            "
            aria-hidden="true"
          />
        </div>

        {/* ==============================
            RIGHT LOGIN PANEL
            ============================== */}

        <div className="login-form-panel">
          <div className="login-form-container">
            <header className="login-header">
              <div className="mobile-brand">
                <span>O</span>
                OpsFlow
              </div>

              <p className="login-kicker">SECURE ACCESS</p>

              <h2>Welcome back</h2>

              <p>Sign in to continue to your operations workspace.</p>
            </header>

            {/* Authentication error */}

            {error && (
              <div className="login-alert" role="alert">
                <span
                  className="
                    login-alert-icon
                  "
                  aria-hidden="true"
                >
                  !
                </span>

                <span>{error}</span>
              </div>
            )}

            {/* Login form */}

            <form className="login-form" onSubmit={handleSubmit}>
              {/* Email */}

              <div className="login-field">
                <label htmlFor="email">Email address</label>

                <div className="login-input-wrapper">
                  <span
                    className="
                      login-input-icon
                    "
                    aria-hidden="true"
                  >
                    @
                  </span>

                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="
                      name@company.com
                    "
                    autoComplete="email"
                    autoFocus
                    required
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              {/* Password */}

              <div className="login-field">
                <div className="login-label-row">
                  <label htmlFor="password">Password</label>
                </div>

                <div className="login-input-wrapper">
                  <span
                    className="
                      login-input-icon
                    "
                    aria-hidden="true"
                  >
                    ●
                  </span>

                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="
                      Enter your password
                    "
                    autoComplete="
                      current-password
                    "
                    required
                    disabled={isSubmitting}
                  />

                  <button
                    type="button"
                    className="
                      password-toggle
                    "
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {/* Submit */}

              <button
                className="
                  login-submit-button
                "
                type="submit"
                disabled={isSubmitting}
              >
                <span>
                  {isSubmitting ? "Authenticating..." : "Sign in to OpsFlow"}
                </span>

                {!isSubmitting && (
                  <span
                    className="
                      login-button-arrow
                    "
                    aria-hidden="true"
                  >
                    →
                  </span>
                )}

                {isSubmitting && (
                  <span
                    className="
                      login-button-spinner
                    "
                    aria-hidden="true"
                  />
                )}
              </button>
            </form>

            {/* Security footer */}

            <div className="login-security-message">
              <span className="security-icon" aria-hidden="true">
                ◆
              </span>

              <span>Protected by secure token-based authentication</span>
            </div>

            <footer className="login-footer">
              OpsFlow Operations Platform
            </footer>
          </div>
        </div>
      </section>
    </main>
  );
}
