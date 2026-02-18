"""Tests for authentication API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@gridflow.dev", "password": "SecurePass1", "full_name": "New User"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@gridflow.dev", "password": "SecurePass1", "full_name": "Dup"},
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@gridflow.dev", "password": "short"},
        )
        assert resp.status_code == 400

    async def test_register_missing_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"password": "SecurePass1"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@gridflow.dev", "password": "TestPass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@gridflow.dev", "password": "WrongPass1"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@gridflow.dev", "password": "Whatever1"},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_authenticated(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@gridflow.dev"
        assert data["full_name"] == "Test User"
        assert data["is_active"] is True

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)


class TestRefresh:
    async def test_refresh_token(self, client: AsyncClient, registered_user):
        refresh = registered_user["refresh_token"]
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert resp.status_code == 401


class TestAnonymous:
    async def test_anonymous_login(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/anonymous")
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_anonymous_can_access_me(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/anonymous")
        token = resp.json()["access_token"]
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert "anon-" in me_resp.json()["email"]
