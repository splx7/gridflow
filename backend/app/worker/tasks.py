import uuid
import zlib
import traceback
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.worker import celery_app
from app.models.database import Base
from app.models.simulation import Simulation, SimulationResult
from app.models.component import Component
from app.models.weather import WeatherDataset
from app.models.load_profile import LoadProfile

sync_engine = create_engine(settings.sync_database_url)


def _decompress(data: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(data), dtype=np.float64)


def _compress(arr: np.ndarray) -> bytes:
    return zlib.compress(arr.astype(np.float64).tobytes())


@celery_app.task(bind=True, name="run_simulation")
def run_simulation(self, simulation_id: str) -> dict:
    """Run a full simulation pipeline."""
    sim_uuid = uuid.UUID(simulation_id)

    with Session(sync_engine) as db:
        sim = db.execute(select(Simulation).where(Simulation.id == sim_uuid)).scalar_one()
        sim.status = "running"
        sim.progress = 0.0
        db.commit()

        try:
            # Load project components
            components = db.execute(
                select(Component).where(Component.project_id == sim.project_id)
            ).scalars().all()

            # Load weather data
            weather_id = uuid.UUID(sim.config_snapshot["weather_dataset_id"])
            weather = db.execute(
                select(WeatherDataset).where(WeatherDataset.id == weather_id)
            ).scalar_one()

            # Load profile
            load_id = uuid.UUID(sim.config_snapshot["load_profile_id"])
            load_profile = db.execute(
                select(LoadProfile).where(LoadProfile.id == load_id)
            ).scalar_one()

            # Decompress time-series data
            ghi = _decompress(weather.ghi)
            dni = _decompress(weather.dni)
            dhi = _decompress(weather.dhi)
            temperature = _decompress(weather.temperature)
            wind_speed = _decompress(weather.wind_speed)
            load_kw = _decompress(load_profile.hourly_kw)

            sim.progress = 10.0
            db.commit()

            # Parse components
            component_configs = {}
            for comp in components:
                component_configs[comp.component_type] = comp.config

            # Run simulation engine
            from engine.simulation.runner import SimulationRunner

            runner = SimulationRunner(
                components=component_configs,
                weather={
                    "ghi": ghi,
                    "dni": dni,
                    "dhi": dhi,
                    "temperature": temperature,
                    "wind_speed": wind_speed,
                },
                load_kw=load_kw,
                dispatch_strategy=sim.dispatch_strategy,
                progress_callback=lambda step, frac: _update_progress(db, sim, frac),
            )

            results = runner.run()

            sim.progress = 90.0
            db.commit()

            # Store results
            from engine.economics.metrics import compute_economics

            project = sim.project
            econ = compute_economics(
                results=results,
                components=component_configs,
                lifetime_years=project.lifetime_years,
                discount_rate=project.discount_rate,
            )

            # Map runner output keys to DB column names
            battery_power = (
                results["battery_discharge_kw"] - results["battery_charge_kw"]
                if "battery_charge_kw" in results else None
            )

            # Flatten cost_breakdown for frontend display
            raw_bd = econ["cost_breakdown"]
            flat_breakdown = {}
            # Capital costs per component
            for comp_type, cost in raw_bd.get("capital", {}).items():
                flat_breakdown[f"{comp_type}_capital"] = cost
            # Aggregated costs
            flat_breakdown["operations_maintenance"] = raw_bd.get("om_npv", 0.0)
            flat_breakdown["fuel"] = raw_bd.get("fuel_npv", 0.0)
            flat_breakdown["grid_costs"] = raw_bd.get("grid_npv", 0.0)
            flat_breakdown["battery_replacement"] = raw_bd.get("replacement_npv", 0.0)
            # Subtract salvage
            if raw_bd.get("salvage_npv", 0.0) > 0:
                flat_breakdown["salvage_value"] = -raw_bd["salvage_npv"]

            sim_result = SimulationResult(
                simulation_id=sim.id,
                npc=econ["npc"],
                lcoe=econ["lcoe"],
                irr=econ.get("irr"),
                payback_years=econ.get("payback_years"),
                renewable_fraction=results["renewable_fraction"],
                co2_emissions_kg=results["co2_emissions_kg"],
                cost_breakdown=flat_breakdown,
                ts_load=_compress(load_kw),
                ts_pv_output=_compress(results["pv_output_kw"]) if results.get("pv_output_kw") is not None else None,
                ts_wind_output=_compress(results["wind_output_kw"]) if results.get("wind_output_kw") is not None else None,
                ts_battery_soc=_compress(results["battery_soc"]) if results.get("battery_soc") is not None else None,
                ts_battery_power=_compress(battery_power) if battery_power is not None else None,
                ts_generator_output=_compress(results["generator_kw"]) if results.get("generator_kw") is not None else None,
                ts_grid_import=_compress(results["grid_import_kw"]) if results.get("grid_import_kw") is not None else None,
                ts_grid_export=_compress(results["grid_export_kw"]) if results.get("grid_export_kw") is not None else None,
                ts_excess=_compress(results["curtailed_kw"]) if results.get("curtailed_kw") is not None else None,
                ts_unmet=_compress(results["unmet_load_kw"]) if results.get("unmet_load_kw") is not None else None,
            )
            db.add(sim_result)

            sim.status = "completed"
            sim.progress = 100.0
            sim.completed_at = datetime.now(timezone.utc)
            db.commit()

            return {"status": "completed", "simulation_id": simulation_id}

        except Exception as e:
            sim.status = "failed"
            sim.error_message = str(e)[:2000]
            db.commit()
            raise


def _update_progress(db: Session, sim: Simulation, progress: float) -> None:
    sim.progress = 10.0 + progress * 0.8  # Scale to 10-90%
    db.commit()
