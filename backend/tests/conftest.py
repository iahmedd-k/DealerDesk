import os
from collections.abc import Iterator

import pytest
import psycopg
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings


test_database_url = os.environ.get("TEST_DATABASE_URL") or Settings().database_url
test_schema = "dealerdesk_test"
psycopg_database_url = test_database_url.replace(
    "postgresql+psycopg://",
    "postgresql://",
    1,
)
with psycopg.connect(psycopg_database_url, autocommit=True) as connection:
    connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{test_schema}"')
os.environ["SUPABASE_CONNECTION_STRING"] = test_database_url
os.environ["DATABASE_URL"] = test_database_url
os.environ["DATABASE_SCHEMA"] = test_schema
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-that-is-at-least-32-bytes"
os.environ["RESEND_API_KEY"] = ""

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


def _reset_test_schema() -> None:
    assert test_database_url is not None
    database_url = test_database_url.replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE')
        connection.execute(f'CREATE SCHEMA "{test_schema}"')


@pytest.fixture(autouse=True)
def reset_database() -> Iterator[None]:
    _reset_test_schema()
    Base.metadata.create_all(bind=engine)
    yield
    _reset_test_schema()


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
