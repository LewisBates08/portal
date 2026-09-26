"""Public fictional fixture generated with cryptography 46.0.7, never a real secret."""

from app.config import get_settings
from app.mfa import decrypt, encrypt


def test_legacy_fernet_data_survives_runtime_upgrade(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "encryption_key", "qgbMsntKVeNMYMKIbMKeCQZwMzyztrTIPDDULXyt5Q8="
    )
    legacy_token = (
        "gAAAAABqt8hprvIvHAMlfFpv52-rSdTwj8Goi_QOwdLzHWXXH11AKs3lrBonRFINpP520jJAAkCd"
        "J2n6qY4wfpWizke0rE55HQ-wHaetmnzfNi5GHdUlwovZtkxMqME_bd9rWwMNfO4jY7QRs0-_y-"
        "NMVHSGVYhUJQ=="
    )
    value = "fictional legacy MFA secret and verification mail"
    assert decrypt(legacy_token) == value
    assert decrypt(encrypt(value)) == value
