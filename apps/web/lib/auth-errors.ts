/**
 * Signup error handling shared by the Next.js BFF route handler and the
 * browser auth client.
 *
 * The FastAPI backend is the authority on registration rules. This module only
 * mirrors the client-visible part of those rules (so the UI can enforce and
 * explain them) and maps backend failure statuses to safe user-facing copy.
 * Raw backend error content — pydantic validation arrays, exception text, SQL
 * details, internal paths — is never forwarded to the browser.
 *
 * Keep SIGNUP_MIN_PASSWORD_LENGTH in sync with the backend policy in
 * packages/utils/password_policy.py (validate_password requires >= 12) and the
 * SignupRequest schema (password min_length=12). The backend stays
 * authoritative; this constant exists so the UI can enforce the same rule
 * before the request is ever sent.
 */

export const SIGNUP_MIN_PASSWORD_LENGTH = 12;

export const SIGNUP_ERROR_MESSAGES = {
  duplicateEmail: "An account with this email already exists.",
  passwordPolicy: `Password must be at least ${SIGNUP_MIN_PASSWORD_LENGTH} characters long.`,
  validation: "Please check the information you entered.",
  unavailable: "Registration is temporarily unavailable. Please try again.",
  network: "Unable to connect to the server. Please try again.",
  generic: "Registration failed. Please try again.",
} as const;

interface SignupErrorPayload {
  detail?: unknown;
}

/**
 * Returns true when the backend's 422 `detail` array flags a password that is
 * shorter than the enforced minimum. Used only to pick an explanatory message;
 * the underlying pydantic text is never surfaced.
 */
function flagsPasswordTooShort(detail: unknown): boolean {
  if (!Array.isArray(detail)) return false;
  return detail.some((item): boolean => {
    if (typeof item !== "object" || item === null) return false;
    const { loc, msg } = item as { loc?: unknown; msg?: unknown };
    const passwordField =
      Array.isArray(loc) && loc.some((part) => part === "password");
    const mentionsMinimum =
      typeof msg === "string" &&
      msg.includes(`at least ${SIGNUP_MIN_PASSWORD_LENGTH} characters`);
    return passwordField && mentionsMinimum;
  });
}

/**
 * Maps a failed signup attempt to safe user-facing copy from the HTTP status
 * (and, when available, the backend error body). Never returns raw backend
 * text and never reveals which accounts exist beyond the intentional 409
 * duplicate-email contract.
 */
export function signupErrorMessage(
  status: number,
  payload?: SignupErrorPayload | null
): string {
  if (status === 409) {
    return SIGNUP_ERROR_MESSAGES.duplicateEmail;
  }
  if (status === 422) {
    if (flagsPasswordTooShort(payload?.detail)) {
      return SIGNUP_ERROR_MESSAGES.passwordPolicy;
    }
    return SIGNUP_ERROR_MESSAGES.validation;
  }
  if (status >= 500) {
    return SIGNUP_ERROR_MESSAGES.unavailable;
  }
  return SIGNUP_ERROR_MESSAGES.generic;
}
