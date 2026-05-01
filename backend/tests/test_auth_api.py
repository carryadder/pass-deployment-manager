from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.user import User

client = TestClient(app)


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, users=None):
        self.users = users or []
        self.added = []
        self.committed = False

    def exec(self, _statement):
        return FakeQuery(self.users)

    def add(self, user):
        self.added.append(user)
        self.users.append(user)

    def commit(self):
        self.committed = True

    def refresh(self, _user):
        return None


def test_register_creates_first_owner_user() -> None:
    fake_session = FakeSession()
    app.dependency_overrides[get_session] = lambda: fake_session

    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecret",
            "full_name": "Owner User",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["is_owner"] is True
    assert fake_session.committed is True


def test_login_returns_access_and_refresh_tokens(monkeypatch) -> None:
    user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed-password",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    fake_session = FakeSession(users=[user])

    app.dependency_overrides[get_session] = lambda: fake_session
    monkeypatch.setattr("backend.app.api.auth.verify_password", lambda plain, hashed: True)

    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "supersecret"},
    )

    app.dependency_overrides.clear()

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
