"""Tests for the shared password policy."""

import pytest

from app.utils.passwords import PASSWORD_MIN_LENGTH, password_policy_error


@pytest.mark.parametrize(
    "password",
    [
        "Abcdefg1!",
        "LongerPassword9#",
        "with spaces A1!",
    ],
)
def test_password_policy_accepts_strong_passwords(password: str) -> None:
    assert password_policy_error(password) is None


def test_password_policy_requires_minimum_length() -> None:
    assert password_policy_error("Aa1!") == (
        f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    )


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("lowercase1!", "Password must include an uppercase letter."),
        ("UPPERCASE1!", "Password must include a lowercase letter."),
        ("NoNumbers!!", "Password must include a number."),
        ("NoSpecial11", "Password must include a special character."),
        ("Has Space 1A", "Password must include a special character."),
    ],
)
def test_password_policy_reports_missing_character_classes(
    password: str, expected: str
) -> None:
    assert password_policy_error(password) == expected
