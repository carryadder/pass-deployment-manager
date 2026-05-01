from backend.app.core.secrets import decrypt_secret, encrypt_secret


def test_encrypt_secret_round_trip() -> None:
    plaintext = "super-secret-value"
    encrypted = encrypt_secret(plaintext)

    assert encrypted != plaintext
    assert decrypt_secret(encrypted) == plaintext
