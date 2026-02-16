from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models.database import Base
from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.component import Component  # noqa: F401
from app.models.weather import WeatherDataset  # noqa: F401
from app.models.load_profile import LoadProfile  # noqa: F401
from app.models.simulation import Simulation, SimulationResult  # noqa: F401
from app.models.bus import Bus  # noqa: F401
from app.models.branch import Branch  # noqa: F401
from app.models.load_allocation import LoadAllocation  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
