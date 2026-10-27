"""Shared password policy for every flow that sets a password."""

from typing import Annotated

from pydantic import AfterValidator


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128

# Deliberately small and local: this catches only the most obvious choices without
# adding an external service, network dependency, or non-deterministic behaviour.
COMMON_PASSWORDS = frozenset(
    {
        "123456789012345",
        "letmeinletmein",
        "password123456",
        "passwordpassword",
        "qwertyqwertyqwerty",
        "searchroom123456",
    }
)


def validate_new_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if value.casefold() in COMMON_PASSWORDS:
        raise ValueError("Choose a less common password.")
    return value


NewPassword = Annotated[str, AfterValidator(validate_new_password)]
