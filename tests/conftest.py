import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel, Session, create_engine

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.db.engine import get_session
from app.main import app
from app.models.models import User, UserRole


def _build_test_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or settings.DATABASE_URL
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    url = make_url(database_url)
    if url.drivername.startswith("postgresql") and not url.database:
        raise RuntimeError("Test PostgreSQL DATABASE_URL must include a database name")

    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


test_engine = _build_test_engine()


@pytest.fixture
def db_session():
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def mock_admin(db_session):
    admin_user = User(username="admin", hashed_password="fakehashed", role=UserRole.ADMIN)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)
    return admin_user


@pytest.fixture
def mock_user(db_session):
    user = User(username="user", hashed_password="fakehashed", role=UserRole.USER)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


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
def client(db_session, mock_admin, mock_user):
    def get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_current_admin] = lambda: mock_admin
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
