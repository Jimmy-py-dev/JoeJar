from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlmodel import select

from app.models.models import RefreshToken, User


def test_register_user_success(client, db_session, auth_url):
    """Ensures a brand new user can register successfully when admin authorized."""
    with patch("app.core.security.get_password_hash", return_value="hashed_secret") as mock_hash:
        response = client.post(
            f"{auth_url}/register",
            json={"username": "newuser", "password": "securepassword"},
        )

    assert response.status_code == 200
    assert response.json()["username"] == "newuser"
    mock_hash.assert_called_once_with("securepassword")

    db_user = db_session.exec(select(User).where(User.username == "newuser")).first()
    assert db_user is not None
    assert db_user.hashed_password == "hashed_secret"


def test_register_user_already_exists(client, db_session, auth_url):
    """Ensures registration drops a 400 error if username is taken."""
    db_session.add(User(username="taken_name", hashed_password="abc"))
    db_session.commit()

    response = client.post(
        f"{auth_url}/register",
        json={"username": "taken_name", "password": "somepassword"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"


def test_login_success(client, db_session, auth_url):
    """Ensures valid user credentials generate appropriate auth tokens."""
    db_user = User(username="testuser", hashed_password="hashed_password")
    db_session.add(db_user)
    db_session.commit()

    with patch("app.core.security.verify_password", return_value=True), patch(
        "app.core.security.create_token", side_effect=["access_jwt", "refresh_jwt"]
    ):
        response = client.post(
            f"{auth_url}/login",
            data={"username": "testuser", "password": "password123"},
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access_jwt"
    assert response.json()["refresh_token"] == "refresh_jwt"

    db_token = db_session.exec(
        select(RefreshToken).where(RefreshToken.token == "refresh_jwt")
    ).first()
    assert db_token is not None
    assert db_token.user_id == db_user.id


def test_login_invalid_credentials(client, db_session, auth_url):
    """Ensures invalid credentials are rejected."""
    db_session.add(User(username="testuser", hashed_password="hashed_password"))
    db_session.commit()

    with patch("app.core.security.verify_password", return_value=False):
        response = client.post(
            f"{auth_url}/login",
            data={"username": "testuser", "password": "wrongpassword"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_refresh_token_rotation_success(client, db_session, auth_url, mock_user):
    """Ensures token rotation successfully revokes the old token and issues a new pair."""
    db_token = RefreshToken(
        token="old_refresh_jwt",
        user_id=mock_user.id,
        revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(db_token)
    db_session.commit()

    with patch("app.core.security.create_token", side_effect=["new_access_jwt", "new_refresh_jwt"]):
        response = client.post(f"{auth_url}/refresh", params={"token": "old_refresh_jwt"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "new_access_jwt"
    assert response.json()["refresh_token"] == "new_refresh_jwt"

    db_session.refresh(db_token)
    assert db_token.revoked is True
    assert db_session.exec(
        select(RefreshToken).where(RefreshToken.token == "new_refresh_jwt")
    ).first()


def test_refresh_token_invalid(client, db_session, auth_url):
    """Ensures missing or revoked refresh tokens are rejected."""
    response = client.post(f"{auth_url}/refresh", params={"token": "missing_refresh_jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"
    assert db_session.exec(select(RefreshToken)).all() == []


def test_logout_revokes_token(client, db_session, auth_url, mock_user):
    """Ensures logout endpoint flags targeted token as revoked."""
    db_token = RefreshToken(token="active_token", user_id=mock_user.id, revoked=False)
    db_session.add(db_token)
    db_session.commit()

    response = client.post(f"{auth_url}/logout", params={"token": "active_token"})

    assert response.status_code == 200
    db_session.refresh(db_token)
    assert db_token.revoked is True


def test_logout_missing_token_still_succeeds(client, db_session, auth_url):
    """Ensures logout is idempotent when the token is already absent."""
    response = client.post(f"{auth_url}/logout", params={"token": "missing_token"})

    assert response.status_code == 200
    assert response.json()["detail"] == "Successfully logged out"
