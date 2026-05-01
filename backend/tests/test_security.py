from backend.app.core.security import hash_password, verify_password


def test_hash_password_accepts_long_passwords() -> None:
    password = "a" * 100

    hashed = hash_password(password)

    assert hashed.startswith("bcrypt_sha256$")
    assert verify_password(password, hashed) is True
