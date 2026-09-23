import { type FormEvent, useState } from "react";

import { Link, useNavigate } from "react-router-dom";

import { registerAccount } from "../api/authApi";
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_TOO_LONG_MESSAGE,
  PASSWORD_TOO_SHORT_MESSAGE,
  evaluatePasswordLength,
} from "../auth/passwordPolicy";

import "../styles/login.css";

export function RegisterPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const passwordPolicy = evaluatePasswordLength(password);
  const confirmationStarted = confirmPassword.length > 0;
  const passwordsMatch = confirmationStarted && password === confirmPassword;

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

    if (!passwordPolicy.meetsMinimumLength) {
      setErrorMessage(PASSWORD_TOO_SHORT_MESSAGE);
      return;
    }

    if (!passwordPolicy.withinMaximumLength) {
      setErrorMessage(PASSWORD_TOO_LONG_MESSAGE);
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("The password confirmation does not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await registerAccount({
        email: normalizedEmail,
        password,
      });

      setPassword("");
      setConfirmPassword("");

      navigate("/login?accountCreated=success", {
        replace: true,
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to create the account. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-grid" aria-hidden="true" />

      <div className="login-ambient-glow login-ambient-glow-one" aria-hidden="true" />
      <div className="login-ambient-glow login-ambient-glow-two" aria-hidden="true" />

      <div className="floating-shape shape-one" aria-hidden="true" />
      <div className="floating-shape shape-three" aria-hidden="true" />

      <section className="login-shell">
        <aside className="login-brand-panel" aria-hidden="true">
          <div className="login-brand-content">
            <div className="brand-mark">
              <span className="brand-mark-inner">OF</span>
            </div>

            <p className="brand-eyebrow">WORKSPACE ACCESS</p>

            <h1 className="login-brand-title">
              Join the
              <span> operational workspace.</span>
            </h1>

            <p className="login-brand-description">
              Create a secure OpsFlow account to view service health, incident
              activity, and your organization&apos;s operational picture.
            </p>

            <div className="system-status-card">
              <span className="system-status-indicator" aria-hidden="true" />

              <div>
                <span className="system-status-label">ACCOUNT SECURITY</span>
                <strong>Least-privilege access by default</strong>
              </div>
            </div>
          </div>

          <div className="brand-orbit brand-orbit-one" />
          <div className="brand-orbit brand-orbit-two" />
        </aside>

        <section className="login-form-panel">
          <div className="login-form-container">
            <div className="mobile-brand">
              <span>OF</span>
              OpsFlow
            </div>

            <header className="login-header">
              <p className="login-kicker">CREATE ACCOUNT</p>
              <h2>Set up your workspace access</h2>
              <p>Use your email address and a secure password to get started.</p>
            </header>

            {errorMessage !== null && (
              <div
                className="login-alert login-alert-error"
                role="alert"
                aria-live="assertive"
              >
                <span className="login-alert-icon" aria-hidden="true">
                  !
                </span>
                <span>{errorMessage}</span>
              </div>
            )}

            <form className="login-form" onSubmit={handleSubmit} noValidate>
              <div className="login-field">
                <label htmlFor="registration-email">Email address</label>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    @
                  </span>

                  <input
                    id="registration-email"
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

              <div className="login-field">
                <label htmlFor="registration-password">Password</label>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    ◆
                  </span>

                  <input
                    id="registration-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Create a secure password"
                    required
                    minLength={PASSWORD_MIN_LENGTH}
                    maxLength={PASSWORD_MAX_LENGTH}
                    value={password}
                    disabled={isSubmitting}
                    aria-describedby="registration-password-policy"
                    onChange={(event) => {
                      setPassword(event.target.value);
                      setErrorMessage(null);
                    }}
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    disabled={isSubmitting}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((current) => !current)}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>

                <div id="registration-password-policy" className="password-policy">
                  <div className="password-policy-heading">
                    <span>Password strength</span>
                    <span>
                      {passwordPolicy.length}/{PASSWORD_MIN_LENGTH} minimum
                    </span>
                  </div>

                  <div className="password-policy-track" aria-hidden="true">
                    <span
                      className={`password-policy-progress ${
                        passwordPolicy.isValid ? "is-valid" : ""
                      }`}
                      style={{ width: `${passwordPolicy.progressPercent}%` }}
                    />
                  </div>

                  <span
                    className={`password-requirement ${
                      passwordPolicy.isValid ? "is-valid" : ""
                    }`}
                  >
                    {passwordPolicy.isValid ? "✓" : "○"} At least {PASSWORD_MIN_LENGTH}
                    characters
                  </span>
                </div>
              </div>

              <div className="login-field">
                <label htmlFor="registration-confirm-password">
                  Confirm password
                </label>

                <div className="login-input-wrapper">
                  <span className="login-input-icon" aria-hidden="true">
                    ◆
                  </span>

                  <input
                    id="registration-confirm-password"
                    name="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Re-enter your password"
                    required
                    maxLength={PASSWORD_MAX_LENGTH}
                    value={confirmPassword}
                    disabled={isSubmitting}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);
                      setErrorMessage(null);
                    }}
                  />
                </div>

                {confirmationStarted && (
                  <p
                    className={`password-match-status ${
                      passwordsMatch ? "is-valid" : "is-invalid"
                    }`}
                    role="status"
                  >
                    {passwordsMatch
                      ? "✓ Passwords match"
                      : "Passwords do not match yet"}
                  </p>
                )}
              </div>

              <button
                type="submit"
                className="login-submit-button"
                disabled={isSubmitting}
              >
                <span>{isSubmitting ? "Creating account..." : "Create account"}</span>

                {isSubmitting ? (
                  <span className="login-button-spinner" aria-hidden="true" />
                ) : (
                  <span className="login-button-arrow" aria-hidden="true">
                    →
                  </span>
                )}
              </button>
            </form>

            <div className="login-recovery-navigation">
              <Link to="/login" className="login-secondary-link">
                Already have an account? Sign in
              </Link>
            </div>

            <div className="login-security-message">
              <span className="login-security-indicator" aria-hidden="true" />
              New accounts start with read-only viewer access.
            </div>

            <footer className="login-footer">OpsFlow secure operations platform</footer>
          </div>
        </section>
      </section>
    </main>
  );
}
