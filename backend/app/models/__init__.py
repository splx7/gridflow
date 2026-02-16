# Import all models so SQLAlchemy can resolve relationships
from app.models.database import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.component import Component  # noqa: F401
from app.models.weather import WeatherDataset  # noqa: F401
from app.models.load_profile import LoadProfile  # noqa: F401
from app.models.simulation import Simulation, SimulationResult  # noqa: F401
from app.models.bus import Bus  # noqa: F401
from app.models.branch import Branch  # noqa: F401
from app.models.load_allocation import LoadAllocation  # noqa: F401
