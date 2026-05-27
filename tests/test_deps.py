from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError

from app.api.deps import get_current_admin, get_current_user
from app.models.models import User, UserRole


def test_get_current_user_success():
    """Ensures a valid JWT subject resolves to a user."""
    db = MagicMock()
    user = User(id=5, username="cashier", hashed_password="hash", role=UserRole.USER)
    db.get.return_value = user

    with patch("app.api.deps.jwt.decode", return_value={"sub": "5"}):
        result = get_current_user(db=db, token="valid.jwt")

    assert result == user
    db.get.assert_called_once_with(User, "5")


def test_get_current_user_invalid_token():
    """Ensures invalid JWTs are rejected."""
    db = MagicMock()

    with patch("app.api.deps.jwt.decode", side_effect=JWTError("bad token")):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db=db, token="bad.jwt")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Could not validate credentials"


def test_get_current_user_missing_subject():
    """Ensures JWTs without a subject are rejected."""
    db = MagicMock()

    with patch("app.api.deps.jwt.decode", return_value={}):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db=db, token="missing-sub.jwt")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Could not validate credentials"


def test_get_current_user_not_found():
    """Ensures a valid token for a missing user returns 404."""
    db = MagicMock()
    db.get.return_value = None

    with patch("app.api.deps.jwt.decode", return_value={"sub": "99"}):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db=db, token="valid.jwt")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


def test_get_current_admin_success():
    """Ensures admin users pass the admin guard."""
    admin = User(id=1, username="admin", hashed_password="hash", role=UserRole.ADMIN)

    assert get_current_admin(current_user=admin) == admin


def test_get_current_admin_forbidden_for_regular_user():
    """Ensures regular users fail the admin guard."""
    user = User(id=2, username="cashier", hashed_password="hash", role=UserRole.USER)

    with pytest.raises(HTTPException) as exc_info:
        get_current_admin(current_user=user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "The user does not have enough privileges"
