from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.main import app
from backend.app.models.user import User

client = TestClient(app)


def test_register_creates_first_owner_user(monkeypatch) -> None:
    created_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    monkeypatch.setattr(
        "backend.app.api.auth._register_user",
        lambda payload: {
            "id": str(created_user.id),
            "email": created_user.email,
            "full_name": created_user.full_name,
            "is_active": created_user.is_active,
            "is_owner": created_user.is_owner,
        },
    )

    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecret",
            "full_name": "Owner User",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["is_owner"] is True


def test_login_returns_access_and_refresh_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.api.auth._login_user",
        lambda payload: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "supersecret"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_me_requires_authentication() -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication credentials were not provided"}


def test_me_returns_current_user_from_dependency_override() -> None:
    user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed-password",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/auth/me")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["is_owner"] is True
