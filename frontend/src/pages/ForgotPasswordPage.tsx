import { type FormEvent, useState } from "react";

import { Link } from "react-router-dom";

import {
  PasswordResetThrottleError,
  requestPasswordReset,
} from "../api/authApi";

import "../styles/login.css";

export function ForgotPasswordPage() {
  /*
   * =======================================================
   * FORM STATE
   * =======================================================
   */

  const [email, setEmail] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /*
   * =======================================================
   * SUBMIT PASSWORD RESET REQUEST
   * =======================================================
   */

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setErrorMessage(null);

    setSuccessMessage(null);

    setIsSubmitting(true);

    try {
      const result = await requestPasswordReset(email);

      setSuccessMessage(result.message);
    } catch (error) {
      if (error instanceof PasswordResetThrottleError) {
        if (error.retryAfterSeconds !== null) {
          setErrorMessage(
            "Too many reset requests. " +
              "Please wait approximately " +
              `${error.retryAfterSeconds} ` +
              "seconds before trying again.",
          );
        } else {
          setErrorMessage(error.message);
        }

        return;
      }

      setErrorMessage("Unable to request a password reset. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      {/*
       * ===================================================
       * PAGE BACKGROUND
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

      {/*
       * ===================================================
       * RECOVERY SHELL
       * ===================================================
       */}

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

            <p className="brand-eyebrow">SECURE ACCOUNT RECOVERY</p>

            <h1 className="login-brand-title">
              Restore access.
              <span>Return securely.</span>
            </h1>

            <p className="login-brand-description">
              OpsFlow uses temporary, single-use recovery credentials to help
              protect account access throughout the password reset process.
            </p>

            <div className="system-status-card">
              <span className="system-status-indicator" aria-hidden="true" />

              <div>
                <span className="system-status-label">RECOVERY SERVICE</span>

                <strong>Secure reset available</strong>
              </div>
            </div>
          </div>

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
             * =============================================
             * MOBILE BRAND
             * =============================================
             */}

            <div className="mobile-brand">
              <span>OF</span>

              <strong>OpsFlow</strong>
            </div>

            {/*
             * =============================================
             * PAGE HEADING
             * =============================================
             */}

            <header className="login-header">
              <p className="login-kicker">ACCOUNT RECOVERY</p>

              <h2>Forgot your password?</h2>

              <p>
                Enter your account email address. If an eligible account exists,
                we'll send secure reset instructions.
              </p>
            </header>

            {/*
             * =============================================
             * SUCCESS MESSAGE
             * =============================================
             */}

            {successMessage !== null && (
              <div
                className="
                  login-alert
                  login-alert-success
                "
                role="status"
                aria-live="polite"
              >
                <div>
                  <strong>Check your inbox</strong>

                  <div>{successMessage}</div>
                </div>
              </div>
            )}

            {/*
             * =============================================
             * ERROR MESSAGE
             * =============================================
             */}

            {errorMessage !== null && (
              <div className="login-alert" role="alert" aria-live="assertive">
                <span className="login-alert-icon" aria-hidden="true">
                  !
                </span>

                <span>{errorMessage}</span>
              </div>
            )}

            {/*
             * =============================================
             * RECOVERY FORM
             * =============================================
             */}

            <form className="login-form" onSubmit={handleSubmit}>
              <div className="login-field">
                <label htmlFor="password-reset-email">Email address</label>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    @
                  </span>

                  <input
                    id="password-reset-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder="name@example.com"
                    required
                    maxLength={320}
                    value={email}
                    disabled={isSubmitting}
                    aria-describedby={"password-reset-email-help"}
                    onChange={(event) => {
                      setEmail(event.target.value);
                    }}
                  />
                </div>

                <p id="password-reset-email-help" className="login-field-hint">
                  For privacy, OpsFlow will not confirm whether an account
                  exists for this address.
                </p>
              </div>

              <button
                type="submit"
                className="login-submit-button"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? "Sending instructions..."
                  : "Send reset instructions"}

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
             * =============================================
             * RETURN TO LOGIN
             * =============================================
             */}

            <div className="login-recovery-navigation">
              <Link to="/login" className="login-secondary-link">
                ← Return to sign in
              </Link>
            </div>

            <div className="login-security-message">
              <span className="security-icon" aria-hidden="true">
                ●
              </span>
              Reset links are temporary and can only be used once.
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
