from datetime import timedelta

from jose import jwt

from app.core.config import settings
from app.core.security import create_token, get_password_hash, verify_password


def test_create_token_contains_subject_and_type():
    """Ensures created JWTs contain the expected auth claims."""
    token = create_token(subject=123, expires_delta=timedelta(minutes=5), token_type="access")

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "123"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_password_hash_round_trip():
    """Ensures password hashing verifies the original password only."""
    hashed_password = get_password_hash("secret-password")

    assert hashed_password != "secret-password"
    assert verify_password("secret-password", hashed_password) is True
    assert verify_password("wrong-password", hashed_password) is False
