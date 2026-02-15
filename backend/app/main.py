from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import auth, projects, components, simulations, weather, comparisons
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

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
