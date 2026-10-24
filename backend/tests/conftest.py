import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

# Settings are cached at import time, so test configuration must be set before importing the app.
# Environment variables take precedence over backend/.env, so local developer settings cannot leak in.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "ALLOWED_EMAIL_DOMAINS": "example.edu",
        "COOKIE_SECURE": "true",
        "EMAIL_BACKEND": "console",
        "RATE_LIMIT_ENABLED": "true",
        "FRONTEND_BASE_URL": "http://localhost:4200",
    }
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import BACKEND_DIR  # noqa: E402
from app.db.enums import ReportType  # noqa: E402
from app.db.models import CampusLocation, Category, Item, User  # noqa: E402
from app.db.session import make_engine  # noqa: E402


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = database_url
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(database_url), "head")
    eng = make_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def make_user(db: Session):
    counter = iter(range(1, 10_000))

    def _make(**overrides) -> User:
        n = next(counter)
        fields = {"name": f"User {n}", "email": f"user{n}@example.edu", "password_hash": "not-a-real-hash"}
        user = User(**(fields | overrides))
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture
def reference_data(db: Session) -> tuple[Category, CampusLocation]:
    category = Category(name="Electronics")
    location = CampusLocation(name="Main Library")
    db.add_all([category, location])
    db.flush()
    return category, location


@pytest.fixture
def make_item(db: Session, make_user, reference_data):
    category, location = reference_data

    def _make(report_type: ReportType = ReportType.LOST, reporter: User | None = None, **overrides) -> Item:
        item = Item(
            reporter=reporter or make_user(),
            report_type=report_type,
            title=overrides.pop("title", "Black phone"),
            description=overrides.pop("description", "Black phone with a cracked case"),
            category=category,
            location=location,
            occurred_at=overrides.pop("occurred_at", datetime(2026, 10, 1, 12, 0, tzinfo=UTC)),
            **overrides,
        )
        db.add(item)
        db.flush()
        return item

    return _make


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def outbox():
    from app.services.email import MemoryEmailSender

    return MemoryEmailSender()


@pytest.fixture
def make_client(engine, outbox):
    """Factory for TestClients (each with its own cookie jar) bound to the test database."""
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app
    from app.services.email import get_email_sender

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: outbox
    clients = []

    def _make():
        client = TestClient(app, base_url="https://testserver")
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client):
    return make_client()
