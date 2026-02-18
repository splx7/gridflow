"""Tests for simulation API endpoints (Celery mocked)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Patch at the source module where run_simulation is defined
_PATCH_TARGET = "app.worker.tasks.run_simulation"


class TestSimulationCRUD:
    @patch(_PATCH_TARGET)
    async def test_create_simulation(
        self, mock_task, client: AsyncClient, auth_headers, sample_project
    ):
        mock_task.delay.return_value = MagicMock(id="celery-task-id-123")
        pid = sample_project["id"]

        resp = await client.post(
            f"/api/v1/projects/{pid}/simulations",
            json={
                "name": "Test Sim",
                "dispatch_strategy": "load_following",
                "weather_dataset_id": str(uuid.uuid4()),
                "load_profile_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Sim"
        assert data["status"] == "pending"
        assert data["dispatch_strategy"] == "load_following"
        mock_task.delay.assert_called_once()

    @patch(_PATCH_TARGET)
    async def test_list_simulations(
        self, mock_task, client: AsyncClient, auth_headers, sample_project
    ):
        mock_task.delay.return_value = MagicMock(id="celery-task-id-456")
        pid = sample_project["id"]

        # Create a simulation
        await client.post(
            f"/api/v1/projects/{pid}/simulations",
            json={
                "name": "Sim 1",
                "dispatch_strategy": "load_following",
                "weather_dataset_id": str(uuid.uuid4()),
                "load_profile_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )

        resp = await client.get(
            f"/api/v1/projects/{pid}/simulations", headers=auth_headers
        )
        assert resp.status_code == 200
        sims = resp.json()
        assert len(sims) >= 1
        assert sims[0]["name"] == "Sim 1"

    @patch(_PATCH_TARGET)
    async def test_get_simulation_status(
        self, mock_task, client: AsyncClient, auth_headers, sample_project
    ):
        mock_task.delay.return_value = MagicMock(id="celery-task-id-789")
        pid = sample_project["id"]

        create_resp = await client.post(
            f"/api/v1/projects/{pid}/simulations",
            json={
                "name": "Status Sim",
                "dispatch_strategy": "load_following",
                "weather_dataset_id": str(uuid.uuid4()),
                "load_profile_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )
        sim_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/simulations/{sim_id}/status", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["progress"] == 0.0

    async def test_create_simulation_project_not_found(
        self, client: AsyncClient, auth_headers
    ):
        fake_pid = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/projects/{fake_pid}/simulations",
            json={
                "name": "No Project Sim",
                "dispatch_strategy": "load_following",
                "weather_dataset_id": str(uuid.uuid4()),
                "load_profile_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @patch(_PATCH_TARGET)
    async def test_delete_simulation(
        self, mock_task, client: AsyncClient, auth_headers, sample_project
    ):
        mock_task.delay.return_value = MagicMock(id="celery-task-id-del")
        pid = sample_project["id"]

        create_resp = await client.post(
            f"/api/v1/projects/{pid}/simulations",
            json={
                "name": "Delete Me",
                "dispatch_strategy": "load_following",
                "weather_dataset_id": str(uuid.uuid4()),
                "load_profile_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )
        sim_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/projects/{pid}/simulations/{sim_id}", headers=auth_headers
        )
        assert resp.status_code == 204
