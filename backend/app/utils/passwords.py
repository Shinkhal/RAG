"""Shared password policy for every credential-setting flow."""

import re

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_POLICY_HINT = (
    "Use at least 8 characters with an uppercase letter, a lowercase letter, "
    "a number, and a special character."
)

_SPECIAL_CHARACTER = re.compile(r"[^A-Za-z0-9\s]")


def password_policy_error(password: str) -> str | None:
    """Return a user-facing error when ``password`` does not meet the policy."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if not re.search(r"[A-Z]", password):
        return "Password must include an uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must include a lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must include a number."
    if not _SPECIAL_CHARACTER.search(password):
        return "Password must include a special character."
    return None
