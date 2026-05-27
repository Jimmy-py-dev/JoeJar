from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models.models import User, UserRole
from app.db.engine import get_session
from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings

@pytest.fixture
def mock_session():
    mock_session = MagicMock(spec=Session)
    yield mock_session

@pytest.fixture
def mock_admin():
    admin_user = User(id=1, username="admin", hashed_password="fakehashed", role=UserRole.ADMIN)
    return admin_user

@pytest.fixture
def mock_user():
    return User(id=2, username="user", hashed_password="fakehashed", role=UserRole.USER)

@pytest.fixture
def auth_url():
    return f"{settings.API_V1_STR}/auth"

@pytest.fixture
def products_url():
    return f"{settings.API_V1_STR}/products"

@pytest.fixture
def sales_url():
    return f"{settings.API_V1_STR}/sales"

@pytest.fixture
def admin_url():
    return f"{settings.API_V1_STR}/admin"

@pytest.fixture
def client(mock_session, mock_admin, mock_user):
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
