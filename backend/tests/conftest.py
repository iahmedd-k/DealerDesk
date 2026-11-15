import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["SUPABASE_CONNECTION_STRING"] = "sqlite:///./data/test_dealerdesk.db"
os.environ["DATABASE_URL"] = os.environ["SUPABASE_CONNECTION_STRING"]
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-that-is-at-least-32-bytes"

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import User
from app.services import auth_service


@pytest.fixture(autouse=True)
def reset_database() -> Iterator[None]:
    auth_service.revoked_tokens.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    auth_service.revoked_tokens.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_users() -> tuple[User, User]:
    from seed.seed_demo_user import seed_demo_users

    return seed_demo_users()
