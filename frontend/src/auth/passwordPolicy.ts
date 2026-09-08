/*
 * =========================================================
 * FRONTEND PASSWORD POLICY
 * =========================================================
 *
 * This module is the single frontend source of truth for
 * replacement-password length behavior.
 *
 * The backend remains authoritative for security.
 *
 * These values intentionally mirror the current FastAPI
 * password policy:
 *
 *     minimum: 15 Unicode/JavaScript string characters
 *     maximum: 128
 *
 * React uses these constants for:
 *
 *     form eligibility
 *     HTML input attributes
 *     validation messages
 *     password-policy text
 *     progress presentation
 *
 * A backend rejection must still be treated as final even
 * if client-side validation passes.
 * =========================================================
 */

export const PASSWORD_MIN_LENGTH = 15;

export const PASSWORD_MAX_LENGTH = 128;

/*
 * =========================================================
 * USER-FACING POLICY MESSAGES
 * =========================================================
 */

export const PASSWORD_TOO_SHORT_MESSAGE =
  "Your new password must contain " +
  `at least ${PASSWORD_MIN_LENGTH} characters.`;

export const PASSWORD_TOO_LONG_MESSAGE =
  "Your new password must not exceed " + `${PASSWORD_MAX_LENGTH} characters.`;

/*
 * =========================================================
 * POLICY STATE
 * =========================================================
 */

export interface PasswordLengthState {
  length: number;

  meetsMinimumLength: boolean;

  withinMaximumLength: boolean;

  isValid: boolean;

  progressPercent: number;
}

/*
 * =========================================================
 * POLICY EVALUATION
 * =========================================================
 */

export function evaluatePasswordLength(password: string): PasswordLengthState {
  const length = password.length;

  const meetsMinimumLength = length >= PASSWORD_MIN_LENGTH;

  const withinMaximumLength = length <= PASSWORD_MAX_LENGTH;

  const isValid = meetsMinimumLength && withinMaximumLength;

  /*
   * The progress bar communicates progress toward the
   * minimum acceptable length.
   *
   * Once the minimum is reached it stays at 100%.
   *
   * Maximum-length validity is communicated separately by
   * the requirement state.
   */

  const progressPercent = Math.min((length / PASSWORD_MIN_LENGTH) * 100, 100);

  return {
    length,

    meetsMinimumLength,

    withinMaximumLength,

    isValid,

    progressPercent,
  };
}
