from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # App
    environment: str = "development"
    debug: bool = True
    app_name: str = "GridFlow"

    # Database
    database_url: str = "postgresql+asyncpg://gridflow:gridflow_dev@localhost:5432/gridflow"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # PVGIS
    pvgis_base_url: str = "https://re.jrc.ec.europa.eu/api/v5_3"

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")


settings = Settings()
