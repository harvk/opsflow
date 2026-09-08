import { type FormEvent, useEffect, useState } from "react";

import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { useAuth } from "../auth/useAuth";

import "../styles/login.css";

interface LoginLocationState {
  from?: {
    pathname?: string;
  };
}

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();

  const navigate = useNavigate();

  const location = useLocation();

  const [searchParams, setSearchParams] = useSearchParams();

  /*
   * =======================================================
   * FORM STATE
   * =======================================================
   */

  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /*
   * =======================================================
   * PASSWORD RESET SUCCESS
   * =======================================================
   *
   * ResetPasswordPage redirects to:
   *
   *   /login?passwordReset=success
   *
   * Capture the value once, then remove the query
   * parameter from browser history.
   */

  const [passwordResetSucceeded] = useState(
    () => searchParams.get("passwordReset") === "success",
  );

  /*
   * =======================================================
   * ORIGINAL PROTECTED DESTINATION
   * =======================================================
   */

  const locationState = location.state as LoginLocationState | null;

  const destination = locationState?.from?.pathname ?? "/";

  /*
   * =======================================================
   * CLEAN PASSWORD RESET QUERY PARAMETER
   * =======================================================
   */

  useEffect(() => {
    if (!searchParams.has("passwordReset")) {
      return;
    }

    setSearchParams(
      {},
      {
        replace: true,
      },
    );
  }, [searchParams, setSearchParams]);

  /*
   * =======================================================
   * AUTHENTICATED USER REDIRECT
   * =======================================================
   */

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    navigate(destination, {
      replace: true,
    });
  }, [destination, isAuthenticated, navigate]);

  /*
   * =======================================================
   * LOGIN
   * =======================================================
   */

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setErrorMessage(null);

    const normalizedEmail = email.trim().toLowerCase();

    if (normalizedEmail.length === 0) {
      setErrorMessage("Enter your email address.");

      return;
    }

    if (password.length === 0) {
      setErrorMessage("Enter your password.");

      return;
    }

    setIsSubmitting(true);

    try {
      await login(normalizedEmail, password);

      navigate(destination, {
        replace: true,
      });
    } catch (error) {
      if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to sign in. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  /*
   * =======================================================
   * PAGE
   * =======================================================
   */

  return (
    <main className="login-page">
      {/*
       * ===================================================
       * BACKGROUND DECORATION
       * ===================================================
       */}

      <div className="login-grid" aria-hidden="true" />

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
        {/*
         * =================================================
         * BRAND PANEL
         * =================================================
         */}

        <aside className="login-brand-panel" aria-hidden="true">
          <div className="login-brand-content">
            <div className="brand-mark">
              <span className="brand-mark-inner">OF</span>
            </div>

            <p className="brand-eyebrow">OPERATIONS INTELLIGENCE</p>

            <h1 className="login-brand-title">
              Command your
              <span>operational flow.</span>
            </h1>

            <p className="login-brand-description">
              Monitor services, coordinate incidents, and maintain visibility
              across your operational environment from one secure workspace.
            </p>

            <div className="system-status-card">
              <span className="system-status-indicator" aria-hidden="true" />

              <div>
                <span className="system-status-label">SYSTEM STATUS</span>

                <strong>Secure authentication gateway</strong>
              </div>
            </div>
          </div>

          {/*
           * Decorative orbit rings are siblings of the
           * actual content. They must not wrap the content.
           */}

          <div
            className="
              brand-orbit
              brand-orbit-one
            "
          />

          <div
            className="
              brand-orbit
              brand-orbit-two
            "
          />
        </aside>

        {/*
         * =================================================
         * FORM PANEL
         * =================================================
         */}

        <section className="login-form-panel">
          <div className="login-form-container">
            {/*
             * Mobile identity.
             *
             * Only the OF mark belongs in the span because
             * the responsive CSS styles .mobile-brand span
             * as the gradient badge.
             */}

            <div className="mobile-brand">
              <span>OF</span>
              OpsFlow
            </div>

            <header className="login-header">
              <p className="login-kicker">SECURE ACCESS</p>

              <h2>Welcome back</h2>

              <p>Sign in to continue to your OpsFlow workspace.</p>
            </header>

            {/*
             * =================================================
             * RESET SUCCESS
             * =================================================
             */}

            {passwordResetSucceeded && (
              <div
                className="
                  login-alert
                  login-alert-success
                "
                role="status"
                aria-live="polite"
              >
                <span
                  className="
                    login-alert-icon
                    login-alert-success-icon
                  "
                  aria-hidden="true"
                >
                  ✓
                </span>

                <div className="login-alert-copy">
                  <strong>Password reset complete</strong>

                  <span>Sign in again using your new password.</span>
                </div>
              </div>
            )}

            {/*
             * =================================================
             * LOGIN ERROR
             * =================================================
             */}

            {errorMessage !== null && (
              <div
                className="
                  login-alert
                  login-alert-error
                "
                role="alert"
                aria-live="assertive"
              >
                <span className="login-alert-icon" aria-hidden="true">
                  !
                </span>

                <span>{errorMessage}</span>
              </div>
            )}

            {/*
             * =================================================
             * LOGIN FORM
             * =================================================
             */}

            <form className="login-form" onSubmit={handleSubmit} noValidate>
              {/*
               * -------------------------------------------------
               * EMAIL
               * -------------------------------------------------
               */}

              <div className="login-field">
                <label htmlFor="email">Email address</label>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    @
                  </span>

                  <input
                    id="email"
                    name="email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    placeholder="name@example.com"
                    required
                    maxLength={320}
                    value={email}
                    disabled={isSubmitting}
                    onChange={(event) => {
                      setEmail(event.target.value);

                      setErrorMessage(null);
                    }}
                  />
                </div>
              </div>

              {/*
               * -------------------------------------------------
               * PASSWORD
               * -------------------------------------------------
               */}

              <div className="login-field">
                <div className="login-label-row">
                  <label htmlFor="password">Password</label>

                  <Link to="/forgot-password" className="login-forgot-link">
                    Forgot password?
                  </Link>
                </div>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    ◆
                  </span>

                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    required
                    value={password}
                    disabled={isSubmitting}
                    onChange={(event) => {
                      setPassword(event.target.value);

                      setErrorMessage(null);
                    }}
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    disabled={isSubmitting}
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    aria-pressed={showPassword}
                    onClick={() => {
                      setShowPassword((current) => !current);
                    }}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {/*
               * -------------------------------------------------
               * SUBMIT
               * -------------------------------------------------
               */}

              <button
                type="submit"
                className="login-submit-button"
                disabled={isSubmitting}
              >
                <span>{isSubmitting ? "Signing in..." : "Sign in"}</span>

                {isSubmitting ? (
                  <span className="login-button-spinner" aria-hidden="true" />
                ) : (
                  <span className="login-button-arrow" aria-hidden="true">
                    →
                  </span>
                )}
              </button>
            </form>

            {/*
             * =================================================
             * SECURITY MESSAGE
             * =================================================
             */}

            <div className="login-security-message">
              <span className="security-icon" aria-hidden="true">
                ●
              </span>
              Protected by secure session management and short-lived access
              credentials.
            </div>

            <footer className="login-footer">
              OpsFlow secure operations platform
            </footer>
          </div>
        </section>
      </section>
    </main>
  );
}
