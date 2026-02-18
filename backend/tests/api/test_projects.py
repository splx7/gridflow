"""Tests for projects and components API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ======================================================================
# Projects CRUD
# ======================================================================


class TestProjectCRUD:
    async def test_create_project(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/projects/",
            json={
                "name": "Nairobi Solar",
                "latitude": -1.28,
                "longitude": 36.82,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Nairobi Solar"
        assert data["latitude"] == -1.28
        assert data["network_mode"] == "single_bus"

    async def test_list_projects(self, client: AsyncClient, auth_headers, sample_project):
        resp = await client.get("/api/v1/projects/", headers=auth_headers)
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) >= 1
        assert any(p["name"] == "Test Project" for p in projects)

    async def test_get_project(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        resp = await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    async def test_get_project_not_found(self, client: AsyncClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_project(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        resp = await client.patch(
            f"/api/v1/projects/{pid}",
            json={"name": "Updated Name", "discount_rate": 0.06},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["discount_rate"] == 0.06

    async def test_delete_project(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        resp = await client.delete(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert resp2.status_code == 404

    async def test_project_unauthorized(self, client: AsyncClient):
        resp = await client.get("/api/v1/projects/")
        assert resp.status_code in (401, 403)

    async def test_project_cross_user_isolation(self, client: AsyncClient, auth_headers, sample_project):
        """A second user cannot access the first user's project."""
        # Register second user
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "other@gridflow.dev", "password": "OtherPass1"},
        )
        other_token = resp.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        pid = sample_project["id"]
        resp = await client.get(f"/api/v1/projects/{pid}", headers=other_headers)
        assert resp.status_code == 404  # Not found for other user


# ======================================================================
# Components CRUD
# ======================================================================


class TestComponentCRUD:
    async def test_create_component(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        resp = await client.post(
            f"/api/v1/projects/{pid}/components",
            json={
                "component_type": "solar_pv",
                "name": "PV Array",
                "config": {"capacity_kwp": 15.0, "tilt": 15},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["component_type"] == "solar_pv"
        assert data["config"]["capacity_kwp"] == 15.0

    async def test_list_components(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        # Create a component first
        await client.post(
            f"/api/v1/projects/{pid}/components",
            json={"component_type": "battery", "name": "BESS", "config": {"capacity_kwh": 100}},
            headers=auth_headers,
        )
        resp = await client.get(f"/api/v1/projects/{pid}/components", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_component(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        create_resp = await client.post(
            f"/api/v1/projects/{pid}/components",
            json={"component_type": "solar_pv", "name": "PV", "config": {"capacity_kwp": 10}},
            headers=auth_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/projects/{pid}/components/{cid}",
            json={"name": "PV Array Updated", "config": {"capacity_kwp": 20}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "PV Array Updated"
        assert resp.json()["config"]["capacity_kwp"] == 20

    async def test_delete_component(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        create_resp = await client.post(
            f"/api/v1/projects/{pid}/components",
            json={"component_type": "battery", "name": "BESS", "config": {}},
            headers=auth_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/projects/{pid}/components/{cid}", headers=auth_headers
        )
        assert resp.status_code == 204

    async def test_component_not_found(self, client: AsyncClient, auth_headers, sample_project):
        pid = sample_project["id"]
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/projects/{pid}/components/{fake_id}", headers=auth_headers
        )
        assert resp.status_code == 404
