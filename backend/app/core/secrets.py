from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from backend.app.config import get_settings


def _build_fernet() -> Fernet:
    settings = get_settings()
    derived_key = hashlib.sha256(settings.fernet_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def encrypt_secret(value: str) -> str:
    return _build_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _build_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


__all__ = ["decrypt_secret", "encrypt_secret"]
