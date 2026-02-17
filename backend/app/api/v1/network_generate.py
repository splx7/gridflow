import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.bus import Bus
from app.models.branch import Branch
from app.models.component import Component
from app.models.load_allocation import LoadAllocation
from app.models.load_profile import LoadProfile
from app.models.project import Project
from app.models.user import User
from app.schemas.network_generate import (
    AutoGenerateRequest,
    AutoGenerateResponse,
    NetworkRecommendation,
)
from app.schemas.bus import BusResponse
from app.schemas.branch import BranchResponse
from app.schemas.load_allocation import LoadAllocationResponse

from engine.network.topology_generator import generate_radial_topology

router = APIRouter()


async def _get_user_project(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post(
    "/{project_id}/network/auto-generate",
    response_model=AutoGenerateResponse,
)
async def auto_generate_network(
    project_id: uuid.UUID,
    body: AutoGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate a radial network topology from project components.

    Deletes existing buses/branches/load-allocations, generates a new
    topology based on the project's components, creates all DB objects,
    assigns components to buses, and sets network_mode to multi_bus.
    """
    project = await _get_user_project(project_id, user, db)

    # Clear component bus_id references first (before deleting buses)
    comp_result = await db.execute(
        select(Component).where(Component.project_id == project_id)
    )
    components_orm = comp_result.scalars().all()
    for comp in components_orm:
        comp.bus_id = None

    # Delete existing network objects (order: load_alloc → branches → buses)
    await db.execute(
        delete(LoadAllocation).where(LoadAllocation.project_id == project_id)
    )
    await db.execute(
        delete(Branch).where(Branch.project_id == project_id)
    )
    await db.execute(
        delete(Bus).where(Bus.project_id == project_id)
    )
    await db.flush()

    # Load components and load profiles
    components_data = [
        {
            "id": str(comp.id),
            "component_type": comp.component_type,
            "name": comp.name,
            "config": comp.config,
        }
        for comp in components_orm
    ]

    lp_result = await db.execute(
        select(LoadProfile).where(LoadProfile.project_id == project_id)
    )
    load_profiles_data = [
        {"id": str(lp.id), "name": lp.name}
        for lp in lp_result.scalars().all()
    ]

    if not components_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No components in project. Add components before generating network.",
        )

    # Generate topology
    topo = generate_radial_topology(
        components=components_data,
        load_profiles=load_profiles_data,
        mv_voltage_kv=body.mv_voltage_kv,
        lv_voltage_kv=body.lv_voltage_kv,
        cable_material=body.cable_material,
        default_cable_length_km=body.cable_length_km,
    )

    # Create buses
    bus_orm_list: list[Bus] = []
    for bus_data in topo["buses"]:
        bus = Bus(
            project_id=project_id,
            name=bus_data["name"],
            bus_type=bus_data["bus_type"],
            nominal_voltage_kv=bus_data["nominal_voltage_kv"],
            x_position=bus_data.get("x_position"),
            y_position=bus_data.get("y_position"),
            config=bus_data.get("config", {}),
        )
        db.add(bus)
        bus_orm_list.append(bus)

    await db.flush()  # Get bus IDs

    # Create branches (map from_bus_idx → actual bus ID)
    branch_orm_list: list[Branch] = []
    for br_data in topo["branches"]:
        from_bus = bus_orm_list[br_data["from_bus_idx"]]
        to_bus = bus_orm_list[br_data["to_bus_idx"]]
        branch = Branch(
            project_id=project_id,
            from_bus_id=from_bus.id,
            to_bus_id=to_bus.id,
            branch_type=br_data["branch_type"],
            name=br_data["name"],
            config=br_data.get("config", {}),
        )
        db.add(branch)
        branch_orm_list.append(branch)

    # Assign components to buses
    comp_by_id = {str(c.id): c for c in components_orm}
    for assignment in topo["component_assignments"]:
        comp = comp_by_id.get(assignment["component_id"])
        if comp:
            bus = bus_orm_list[assignment["bus_idx"]]
            comp.bus_id = bus.id

    # Create load allocations
    la_orm_list: list[LoadAllocation] = []
    for la_data in topo["load_allocations"]:
        bus = bus_orm_list[la_data["bus_idx"]]
        la = LoadAllocation(
            project_id=project_id,
            load_profile_id=uuid.UUID(la_data["load_profile_id"]),
            bus_id=bus.id,
            name=la_data["name"],
            fraction=la_data["fraction"],
            power_factor=la_data["power_factor"],
        )
        db.add(la)
        la_orm_list.append(la)

    # Set network mode
    project.network_mode = "multi_bus"

    await db.commit()

    # Refresh all objects for response
    for obj in bus_orm_list + branch_orm_list + la_orm_list:
        await db.refresh(obj)

    return AutoGenerateResponse(
        buses=[BusResponse.model_validate(b) for b in bus_orm_list],
        branches=[BranchResponse.model_validate(br) for br in branch_orm_list],
        load_allocations=[LoadAllocationResponse.model_validate(la) for la in la_orm_list],
        recommendations=[
            NetworkRecommendation(**r) for r in topo["recommendations"]
        ],
    )
