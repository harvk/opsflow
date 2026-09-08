import { type FormEvent, useEffect, useRef, useState } from "react";

import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { confirmPasswordReset } from "../api/authApi";

import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_TOO_LONG_MESSAGE,
  PASSWORD_TOO_SHORT_MESSAGE,
  evaluatePasswordLength,
} from "../auth/passwordPolicy";

import "../styles/login.css";

export function ResetPasswordPage() {
  const navigate = useNavigate();

  const [searchParams, setSearchParams] = useSearchParams();

  /*
   * =======================================================
   * RESET CREDENTIAL
   * =======================================================
   *
   * The reset token is bearer authentication material.
   *
   * Capture it once from the URL and retain it only in
   * component memory.
   */

  const resetTokenRef = useRef<string | null>(searchParams.get("token"));

  /*
   * =======================================================
   * FORM STATE
   * =======================================================
   */

  const [newPassword, setNewPassword] = useState("");

  const [confirmPassword, setConfirmPassword] = useState("");

  const [showNewPassword, setShowNewPassword] = useState(false);

  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /*
   * =======================================================
   * REMOVE RESET TOKEN FROM VISIBLE URL
   * =======================================================
   *
   * Query-string credentials can otherwise remain in:
   *
   *     browser history
   *     copied URLs
   *     screenshots
   *     referrer data
   *
   * Capture first, then replace the visible route.
   */

  useEffect(() => {
    if (searchParams.has("token")) {
      setSearchParams(
        {},
        {
          replace: true,
        },
      );
    }
  }, [searchParams, setSearchParams]);

  /*
   * =======================================================
   * PASSWORD POLICY STATE
   * =======================================================
   */

  const passwordPolicy = evaluatePasswordLength(newPassword);

  const {
    length: passwordLength,

    meetsMinimumLength,

    withinMaximumLength,

    isValid: passwordLengthValid,

    progressPercent: passwordProgressPercent,
  } = passwordPolicy;

  /*
   * =======================================================
   * PASSWORD CONFIRMATION STATE
   * =======================================================
   */

  const confirmationStarted = confirmPassword.length > 0;

  const passwordsMatch = confirmationStarted && newPassword === confirmPassword;

  const formIsValid = passwordLengthValid && passwordsMatch;

  /*
   * =======================================================
   * RESET-CREDENTIAL STATE
   * =======================================================
   */

  const hasResetToken =
    resetTokenRef.current !== null && resetTokenRef.current.length > 0;

  /*
   * =======================================================
   * SUBMISSION
   * =======================================================
   */

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setErrorMessage(null);

    const resetToken = resetTokenRef.current;

    if (!resetToken) {
      setErrorMessage(
        "This password reset link is missing " + "its recovery credential.",
      );

      return;
    }

    if (!meetsMinimumLength) {
      setErrorMessage(PASSWORD_TOO_SHORT_MESSAGE);

      return;
    }

    if (!withinMaximumLength) {
      setErrorMessage(PASSWORD_TOO_LONG_MESSAGE);

      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("The password confirmation " + "does not match.");

      return;
    }

    setIsSubmitting(true);

    try {
      await confirmPasswordReset(resetToken, newPassword);

      /*
       * The one-time credential has now been consumed.
       *
       * Destroy our remaining in-memory reference before
       * navigating away.
       */

      resetTokenRef.current = null;

      setNewPassword("");

      setConfirmPassword("");

      navigate("/login?passwordReset=success", {
        replace: true,
      });
    } catch (error) {
      if (error instanceof Error) {
        setErrorMessage(error.message);

        return;
      }

      setErrorMessage("Unable to reset the password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  /*
   * =======================================================
   * INVALID / MISSING CREDENTIAL
   * =======================================================
   */

  if (!hasResetToken) {
    return (
      <main className="login-page">
        <div className="login-grid" aria-hidden="true" />

        <div className="login-ambient-glow" aria-hidden="true" />

        <section className="login-shell">
          <aside className="login-brand-panel" aria-hidden="true">
            <div className="brand-orbit">
              <div
                className="
                  brand-orbit-ring
                  brand-orbit-ring-one
                "
              />

              <div
                className="
                  brand-orbit-ring
                  brand-orbit-ring-two
                "
              />

              <div className="brand-orbit-core">OF</div>
            </div>

            <div className="login-brand-copy">
              <p className="login-kicker">Secure recovery</p>

              <h1>
                Protecting access to
                <span> OpsFlow.</span>
              </h1>

              <p>
                Invalid, expired, or already-used recovery credentials cannot be
                used to change an account password.
              </p>
            </div>
          </aside>

          <section className="login-form-panel">
            <div className="login-form-container">
              <div className="mobile-brand">
                <span className="mobile-brand-mark">OF</span>

                <span>OpsFlow</span>
              </div>

              <header className="login-header">
                <p className="login-kicker">Recovery unavailable</p>

                <h2>Invalid reset link</h2>

                <p>
                  This recovery link does not contain a usable reset credential.
                </p>
              </header>

              <div
                className="
                  login-alert
                  login-alert-error
                "
                role="alert"
              >
                Request a new password-reset link before trying again.
              </div>

              <Link
                to="/forgot-password"
                className="
                  login-submit-button
                  login-button-link
                "
              >
                Request another reset
              </Link>

              <div className="login-recovery-navigation">
                <Link to="/login" className="login-secondary-link">
                  ← Return to sign in
                </Link>
              </div>
            </div>
          </section>
        </section>
      </main>
    );
  }

  /*
   * =======================================================
   * RESET FORM
   * =======================================================
   */

  return (
    <main className="login-page">
      <div className="login-grid" aria-hidden="true" />

      <div className="login-ambient-glow" aria-hidden="true" />

      <div
        className="
          floating-shape
          floating-shape-one
        "
        aria-hidden="true"
      />

      <div
        className="
          floating-shape
          floating-shape-two
        "
        aria-hidden="true"
      />

      <section className="login-shell">
        <aside className="login-brand-panel" aria-hidden="true">
          <div className="brand-orbit">
            <div
              className="
                brand-orbit-ring
                brand-orbit-ring-one
              "
            />

            <div
              className="
                brand-orbit-ring
                brand-orbit-ring-two
              "
            />

            <div className="brand-orbit-core">OF</div>
          </div>

          <div className="login-brand-copy">
            <p className="login-kicker">Credential security</p>

            <h1>
              Establish your new
              <span> secure credential.</span>
            </h1>

            <p>
              Completing recovery revokes existing persistent sessions and
              requires a fresh sign-in with your new password.
            </p>
          </div>
        </aside>

        <section className="login-form-panel">
          <div className="login-form-container">
            <div className="mobile-brand">
              <span className="mobile-brand-mark">OF</span>

              <span>OpsFlow</span>
            </div>

            <header className="login-header">
              <p className="login-kicker">Password recovery</p>

              <h2>Choose a new password</h2>

              <p>Create a replacement credential for your OpsFlow account.</p>
            </header>

            {errorMessage !== null && (
              <div
                className="
                  login-alert
                  login-alert-error
                "
                role="alert"
                aria-live="assertive"
              >
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate>
              <div className="login-field">
                <label htmlFor="new-password">New password</label>

                <div className="login-input-wrapper">
                  <input
                    id="new-password"
                    name="newPassword"
                    type={showNewPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required
                    minLength={PASSWORD_MIN_LENGTH}
                    maxLength={PASSWORD_MAX_LENGTH}
                    value={newPassword}
                    disabled={isSubmitting}
                    aria-describedby="new-password-policy"
                    onChange={(event) => {
                      setNewPassword(event.target.value);

                      setErrorMessage(null);
                    }}
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={
                      showNewPassword
                        ? "Hide new password"
                        : "Show new password"
                    }
                    aria-pressed={showNewPassword}
                    disabled={isSubmitting}
                    onClick={() => {
                      setShowNewPassword((current) => !current);
                    }}
                  >
                    {showNewPassword ? "Hide" : "Show"}
                  </button>
                </div>

                <div
                  id="new-password-policy"
                  className="password-policy"
                  aria-live="polite"
                >
                  <div className="password-policy-heading">
                    <span>Password length</span>

                    <span>
                      {passwordLength}/{PASSWORD_MAX_LENGTH}
                    </span>
                  </div>

                  <div className="password-policy-track" aria-hidden="true">
                    <span
                      className={
                        "password-policy-progress " +
                        (passwordLengthValid ? "is-valid" : "")
                      }
                      style={{
                        width: `${passwordProgressPercent}%`,
                      }}
                    />
                  </div>

                  <div
                    className={
                      "password-requirement " +
                      (meetsMinimumLength ? "is-valid" : "")
                    }
                  >
                    <span aria-hidden="true">
                      {meetsMinimumLength ? "✓" : "○"}
                    </span>
                    At least {PASSWORD_MIN_LENGTH} characters
                  </div>

                  <div
                    className={
                      "password-requirement " +
                      (withinMaximumLength ? "is-valid" : "is-invalid")
                    }
                  >
                    <span aria-hidden="true">
                      {withinMaximumLength ? "✓" : "!"}
                    </span>
                    No more than {PASSWORD_MAX_LENGTH} characters
                  </div>
                </div>
              </div>

              <div className="login-field">
                <label htmlFor="confirm-password">Confirm new password</label>

                <div className="login-input-wrapper">
                  <input
                    id="confirm-password"
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required
                    minLength={PASSWORD_MIN_LENGTH}
                    maxLength={PASSWORD_MAX_LENGTH}
                    value={confirmPassword}
                    disabled={isSubmitting}
                    aria-describedby="password-match-status"
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);

                      setErrorMessage(null);
                    }}
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={
                      showConfirmPassword
                        ? "Hide password confirmation"
                        : "Show password confirmation"
                    }
                    aria-pressed={showConfirmPassword}
                    disabled={isSubmitting}
                    onClick={() => {
                      setShowConfirmPassword((current) => !current);
                    }}
                  >
                    {showConfirmPassword ? "Hide" : "Show"}
                  </button>
                </div>

                <p
                  id="password-match-status"
                  className={
                    "password-match-status " +
                    (!confirmationStarted
                      ? ""
                      : passwordsMatch
                        ? "is-valid"
                        : "is-invalid")
                  }
                  aria-live="polite"
                >
                  {!confirmationStarted
                    ? "Re-enter your new password."
                    : passwordsMatch
                      ? "✓ Passwords match."
                      : "Passwords do not match."}
                </p>
              </div>

              <button
                type="submit"
                className="login-submit-button"
                disabled={isSubmitting || !formIsValid}
              >
                {isSubmitting ? (
                  <>
                    <span
                      className="
                        spinner-border
                        spinner-border-sm
                      "
                      aria-hidden="true"
                    />
                    Securing account...
                  </>
                ) : (
                  "Reset password"
                )}
              </button>
            </form>

            <div className="login-recovery-navigation">
              <Link to="/login" className="login-secondary-link">
                ← Return to sign in
              </Link>
            </div>

            <div className="login-security-message">
              <span className="login-security-indicator" aria-hidden="true" />
              Successful recovery revokes existing persistent sessions.
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
