import pytest
from pydantic import ValidationError

from app.password_policy import validate_new_password
from app.schemas import AcceptInvite, Register, ResetPassword


def test_password_policy_accepts_boundaries_and_rejects_common_values():
    assert validate_new_password("A-secure-pass-15") == "A-secure-pass-15"
    assert validate_new_password("x" * 128) == "x" * 128
    for value in ("short", "passwordpassword", "x" * 129):
        with pytest.raises(ValueError):
            validate_new_password(value)


@pytest.mark.parametrize(
    "schema,payload",
    [
        (
            Register,
            {
                "email": "policy@example.com",
                "name": "Policy",
                "agency_name": "Agency",
                "password": "too-short",
            },
        ),
        (
            AcceptInvite,
            {"token": "token", "name": "Policy", "password": "too-short"},
        ),
        (
            ResetPassword,
            {"token": "token", "password": "passwordpassword"},
        ),
    ],
)
def test_every_password_setting_schema_uses_shared_policy(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)
