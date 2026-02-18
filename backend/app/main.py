from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import (
    auth, projects, components, simulations, weather, comparisons, advisor,
    buses, branches, load_allocations, power_flow, cable_library,
    network_generate, sensitivity, reports, contingency,
    component_templates, project_templates,
)
from app.models.database import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    application.include_router(
        components.router, prefix="/api/v1/projects", tags=["components"]
    )
    application.include_router(
        simulations.router, prefix="/api/v1", tags=["simulations"]
    )
    application.include_router(weather.router, prefix="/api/v1/projects", tags=["weather"])
    application.include_router(comparisons.router, prefix="/api/v1/comparisons", tags=["comparisons"])
    application.include_router(advisor.router, prefix="/api/v1/projects", tags=["advisor"])
    application.include_router(buses.router, prefix="/api/v1/projects", tags=["buses"])
    application.include_router(branches.router, prefix="/api/v1/projects", tags=["branches"])
    application.include_router(
        load_allocations.router, prefix="/api/v1/projects", tags=["load-allocations"]
    )
    application.include_router(power_flow.router, prefix="/api/v1/projects", tags=["power-flow"])
    application.include_router(cable_library.router, prefix="/api/v1", tags=["cable-library"])
    application.include_router(
        network_generate.router, prefix="/api/v1/projects", tags=["network-generate"]
    )
    application.include_router(
        sensitivity.router, prefix="/api/v1", tags=["sensitivity"]
    )
    application.include_router(
        reports.router, prefix="/api/v1/simulations", tags=["reports"]
    )
    application.include_router(
        contingency.router, prefix="/api/v1/projects", tags=["contingency"]
    )
    application.include_router(
        contingency.grid_codes_router, prefix="/api/v1", tags=["grid-codes"]
    )
    application.include_router(
        component_templates.router, prefix="/api/v1", tags=["component-templates"]
    )
    application.include_router(
        project_templates.router, prefix="/api/v1", tags=["project-templates"]
    )

    @application.get("/health")
    async def health_check() -> dict:
        from app.models.database import get_session_factory

        result: dict = {"status": "ok", "services": {}}

        # Check database
        try:
            async with get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
            result["services"]["database"] = "ok"
        except Exception as e:
            result["services"]["database"] = f"error: {e}"
            result["status"] = "degraded"

        # Check Redis
        try:
            import redis

            r = redis.from_url(settings.redis_url)
            r.ping()
            result["services"]["redis"] = "ok"
        except Exception as e:
            result["services"]["redis"] = f"error: {e}"
            result["status"] = "degraded"

        return result

    return application


app = create_app()
