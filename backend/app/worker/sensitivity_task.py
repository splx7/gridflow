import uuid
import copy
import zlib
import traceback

import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.worker import celery_app
from app.models import (
    Simulation, SimulationResult, Component, WeatherDataset, LoadProfile, Project,
)

sync_engine = create_engine(settings.sync_database_url)


def _decompress(data: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(data), dtype=np.float64)


def _load_simulation_config(db: Session, sim: Simulation):
    """Load weather, load profile, and component configs for a simulation.

    Returns (weather_dict, load_kw, component_configs, project).
    """
    components = db.execute(
        select(Component).where(Component.project_id == sim.project_id)
    ).scalars().all()

    weather_id = uuid.UUID(sim.config_snapshot["weather_dataset_id"])
    weather = db.execute(
        select(WeatherDataset).where(WeatherDataset.id == weather_id)
    ).scalar_one()

    load_id = uuid.UUID(sim.config_snapshot["load_profile_id"])
    load_profile = db.execute(
        select(LoadProfile).where(LoadProfile.id == load_id)
    ).scalar_one()

    weather_dict = {
        "ghi": _decompress(weather.ghi),
        "dni": _decompress(weather.dni),
        "dhi": _decompress(weather.dhi),
        "temperature": _decompress(weather.temperature),
        "wind_speed": _decompress(weather.wind_speed),
    }
    load_kw = _decompress(load_profile.hourly_kw)

    project = sim.project
    component_configs = {}
    for comp in components:
        cfg = dict(comp.config)
        if comp.component_type == "solar_pv":
            if "capacity_kw" in cfg and "capacity_kwp" not in cfg:
                cfg["capacity_kwp"] = cfg["capacity_kw"]
            cfg.setdefault("latitude", project.latitude)
            cfg.setdefault("longitude", project.longitude)
        elif comp.component_type == "diesel_generator":
            if "fuel_curve_a0" in cfg:
                cfg["fuel_curve"] = {
                    "a0": cfg.pop("fuel_curve_a0"),
                    "a1": cfg.pop("fuel_curve_a1", 0.246),
                }
            elif "fuel_curve_a" in cfg:
                cfg["fuel_curve"] = {
                    "a0": cfg.pop("fuel_curve_a"),
                    "a1": cfg.pop("fuel_curve_b", 0.246),
                }
            if "fuel_price_per_liter" in cfg and "fuel_price" not in cfg:
                cfg["fuel_price"] = cfg.pop("fuel_price_per_liter")
        elif comp.component_type == "grid_connection":
            if "buy_rate" in cfg and "tariff" not in cfg:
                cfg["tariff"] = {
                    "type": "flat",
                    "buy_rate": cfg.get("buy_rate", 0.12),
                    "sell_rate": cfg.get("sell_rate", 0.05),
                }
        component_configs[comp.component_type] = cfg

    return weather_dict, load_kw, component_configs, project


@celery_app.task(bind=True, name="run_sensitivity")
def run_sensitivity(self, simulation_id: str, variables: list[dict]) -> dict:
    """Run OAT sensitivity analysis for a completed simulation."""
    sim_uuid = uuid.UUID(simulation_id)

    with Session(sync_engine) as db:
        sim = db.execute(
            select(Simulation).where(Simulation.id == sim_uuid)
        ).scalar_one()

        sim_result = db.execute(
            select(SimulationResult).where(
                SimulationResult.simulation_id == sim_uuid
            )
        ).scalar_one_or_none()

        if sim_result is None:
            raise ValueError("Simulation has no results — run it first")

        try:
            weather_dict, load_kw, component_configs, project = (
                _load_simulation_config(db, sim)
            )

            # Build the base parameter set for sensitivity analysis.
            # The param_path in variables uses dot notation into this dict.
            base_params = {
                "components": copy.deepcopy(component_configs),
                "weather": weather_dict,
                "load_kw": load_kw,
                "dispatch_strategy": sim.dispatch_strategy,
                "project": {
                    "lifetime_years": project.lifetime_years,
                    "discount_rate": project.discount_rate,
                },
            }

            def run_fn(params: dict) -> dict:
                """Run simulation + economics with modified params."""
                from engine.simulation.runner import SimulationRunner
                from engine.economics.metrics import compute_economics

                runner = SimulationRunner(
                    components=params["components"],
                    weather=params["weather"],
                    load_kw=params["load_kw"],
                    dispatch_strategy=params["dispatch_strategy"],
                )
                results = runner.run()
                econ = compute_economics(
                    results=results,
                    components=params["components"],
                    lifetime_years=params["project"]["lifetime_years"],
                    discount_rate=params["project"]["discount_rate"],
                )
                return {
                    "npc": econ["npc"],
                    "lcoe": econ["lcoe"],
                    "irr": econ.get("irr"),
                    "payback_years": econ.get("payback_years"),
                }

            from engine.economics.sensitivity import sensitivity_analysis

            result = sensitivity_analysis(
                base_params=base_params,
                variables=variables,
                run_fn=run_fn,
            )

            # Sanitize for JSON (replace None with null, inf/nan with None).
            def _sanitize(obj):
                if isinstance(obj, dict):
                    return {k: _sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_sanitize(v) for v in obj]
                if isinstance(obj, float):
                    if obj != obj or obj == float("inf") or obj == float("-inf"):
                        return None
                return obj

            sanitized = _sanitize(result)

            sim_result.sensitivity_results = sanitized
            db.commit()

            return {"status": "completed", "simulation_id": simulation_id}

        except Exception as e:
            traceback.print_exc()
            raise
