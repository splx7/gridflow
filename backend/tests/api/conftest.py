"""API test infrastructure — async httpx client with SQLite test database."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.models.database import Base, get_db

# ---------------------------------------------------------------------------
# SQLite compatibility for PostgreSQL column types
# ---------------------------------------------------------------------------

@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Enable foreign key enforcement for SQLite
        await conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI app with overridden dependencies
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app(db_engine):
    from app.main import create_app

    application = create_app()

    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with factory() as session:
            yield session

    application.dependency_overrides[get_db] = _override_get_db

    # Reset rate limiter between tests
    from app.core.rate_limit import auth_limiter
    auth_limiter._requests.clear()

    yield application

    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

TEST_PASSWORD = "TestPass123"
TEST_EMAIL = "test@gridflow.dev"


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user and return the token response."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def auth_headers(registered_user: dict) -> dict[str, str]:
    """Authorization headers for authenticated requests."""
    token = registered_user["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_project(client: AsyncClient, auth_headers: dict) -> dict:
    """Create and return a sample project."""
    resp = await client.post(
        "/api/v1/projects/",
        json={
            "name": "Test Project",
            "description": "A test project",
            "latitude": -1.28,
            "longitude": 36.82,
            "lifetime_years": 25,
            "discount_rate": 0.08,
            "currency": "USD",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()
