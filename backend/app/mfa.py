import base64
import hashlib
from cryptography.fernet import Fernet
from fastapi import HTTPException
import pyotp
from .config import get_settings
from .security import digest


def cipher():
    settings = get_settings()
    key = (
        settings.encryption_key
        or base64.urlsafe_b64encode(
            hashlib.sha256(settings.jwt_secret.encode()).digest()
        ).decode()
    )
    return Fernet(key.encode())


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    return cipher().decrypt(value.encode()).decode()


def validate_code(user, code):
    import time

    step = int(time.time()) // 30
    if (
        user.mfa_secret
        and step > user.mfa_last_step
        and pyotp.TOTP(decrypt(user.mfa_secret)).verify(code)
    ):
        user.mfa_last_step = step
        return
    hashes = list(user.recovery_hashes)
    if user.mfa_enabled and digest(code) in hashes:
        hashes.remove(digest(code))
        user.recovery_hashes = hashes
        return
    raise HTTPException(401, "Invalid or already used authenticator/recovery code.")
