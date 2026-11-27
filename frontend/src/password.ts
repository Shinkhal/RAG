export const PASSWORD_MIN_LENGTH = 8;

export const PASSWORD_POLICY_HINT =
  "At least 8 characters with an uppercase letter, a lowercase letter, a number, and a special character.";

/**
 * Return a user-facing error when the password does not meet the policy,
 * or null when it is valid. Keep this in sync with the backend policy in
 * `backend/app/utils/passwords.py`.
 */
export function passwordPolicyError(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (!/[A-Z]/.test(password)) {
    return "Password must include an uppercase letter.";
  }
  if (!/[a-z]/.test(password)) {
    return "Password must include a lowercase letter.";
  }
  if (!/[0-9]/.test(password)) {
    return "Password must include a number.";
  }
  if (!/[^A-Za-z0-9\s]/.test(password)) {
    return "Password must include a special character.";
  }
  return null;
}
