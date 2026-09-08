/*
 * =========================================================
 * AUTHENTICATION ERROR HEADER
 * =========================================================
 *
 * FastAPI exposes this response header through CORS.
 *
 * Authentication clients use this machine-readable value
 * instead of attempting to infer security state from:
 *
 *   HTTP status alone
 *   backend prose
 *   exception text
 */

export const AUTH_ERROR_CODE_HEADER = "X-Auth-Error-Code";

/*
 * =========================================================
 * AUTHENTICATION ERROR CODES
 * =========================================================
 *
 * These values intentionally mirror the stable backend
 * AuthErrorCode contract.
 *
 * They are public protocol identifiers.
 *
 * Do not use backend human-readable response text as an
 * authentication discriminator.
 */

export const AuthErrorCode = {
  ACCESS_CREDENTIALS_INVALID: "AUTH_ACCESS_CREDENTIALS_INVALID",

  LOGIN_CREDENTIALS_INVALID: "AUTH_LOGIN_CREDENTIALS_INVALID",

  LOGIN_THROTTLED: "AUTH_LOGIN_THROTTLED",

  REFRESH_CREDENTIALS_INVALID: "AUTH_REFRESH_CREDENTIALS_INVALID",

  CSRF_VALIDATION_FAILED: "AUTH_CSRF_VALIDATION_FAILED",

  REAUTHENTICATION_FAILED: "AUTH_REAUTHENTICATION_FAILED",

  REAUTHENTICATION_REQUIRED: "AUTH_REAUTHENTICATION_REQUIRED",

  PASSWORD_CHANGE_REJECTED: "AUTH_PASSWORD_CHANGE_REJECTED",

  PASSWORD_RESET_THROTTLED: "AUTH_PASSWORD_RESET_THROTTLED",

  PASSWORD_RESET_CREDENTIAL_INVALID: "AUTH_PASSWORD_RESET_CREDENTIAL_INVALID",

  PASSWORD_RESET_PASSWORD_REJECTED: "AUTH_PASSWORD_RESET_PASSWORD_REJECTED",
} as const;

export type AuthErrorCode = (typeof AuthErrorCode)[keyof typeof AuthErrorCode];

/*
 * =========================================================
 * KNOWN CODE SET
 * =========================================================
 */

const KNOWN_AUTH_ERROR_CODES: ReadonlySet<string> = new Set(
  Object.values(AuthErrorCode),
);

/*
 * =========================================================
 * TYPE GUARD
 * =========================================================
 */

export function isAuthErrorCode(value: string | null): value is AuthErrorCode {
  if (value === null) {
    return false;
  }

  return KNOWN_AUTH_ERROR_CODES.has(value);
}

/*
 * =========================================================
 * RESPONSE CODE READER
 * =========================================================
 */

export function readAuthErrorCode(
  response: Pick<Response, "headers">,
): AuthErrorCode | null {
  const rawCode = response.headers.get(AUTH_ERROR_CODE_HEADER);

  if (!isAuthErrorCode(rawCode)) {
    return null;
  }

  return rawCode;
}

/*
 * =========================================================
 * FRONTEND AUTHENTICATION ERROR
 * =========================================================
 *
 * The message is frontend-controlled display text.
 *
 * code:
 *   stable backend protocol meaning
 *
 * status:
 *   transport-level HTTP status
 *
 * The UI therefore does not need to parse backend prose.
 */

export class AuthApiError extends Error {
  readonly code: AuthErrorCode | null;

  readonly status: number;

  constructor(
    message: string,
    options: {
      code: AuthErrorCode | null;

      status: number;
    },
  ) {
    super(message);

    this.name = "AuthApiError";

    this.code = options.code;

    this.status = options.status;
  }
}
