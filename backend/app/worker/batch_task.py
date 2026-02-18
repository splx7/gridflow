"""Celery task for batch / parametric sweep simulations.

Iterates a parameter grid, creates Simulation + SimulationResult records
for each combination, and updates the BatchRun progress.
"""
import copy
import itertools
import uuid
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.worker import celery_app

# Use synchronous engine for Celery context
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("+aiosqlite", "")


def _get_sync_session() -> Session:
    engine = create_engine(_sync_url)
    return Session(engine)


def _set_nested(d: dict, path: str, value: float) -> dict:
    """Set a nested value in a dict using dot-separated path.

    E.g. _set_nested(cfg, 'solar_pv.capacity_kw', 20) sets cfg['solar_pv']['capacity_kw'] = 20
    """
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return d


@celery_app.task(name="app.worker.batch_task.run_batch_sweep", bind=True)
def run_batch_sweep(self, batch_id: str):
    """Execute a parametric sweep batch run."""
    from app.models.batch import BatchRun
    from app.models.simulation import Simulation, SimulationResult
    from app.models.component import Component
    from app.models.weather import WeatherDataset
    from app.models.load_profile import LoadProfile

    session = _get_sync_session()

    try:
        batch = session.execute(
            select(BatchRun).where(BatchRun.id == uuid.UUID(batch_id))
        ).scalar_one()

        batch.status = "running"
        session.commit()

        sweep_config = batch.sweep_config
        sweep_params = sweep_config["sweep_params"]
        dispatch_strategy = sweep_config["dispatch_strategy"]
        weather_dataset_id = uuid.UUID(sweep_config["weather_dataset_id"])
        load_profile_id = uuid.UUID(sweep_config["load_profile_id"])

        # Build base component config
        components = session.execute(
            select(Component).where(Component.project_id == batch.project_id)
        ).scalars().all()

        base_config = {}
        for comp in components:
            base_config[comp.component_type] = {
                "name": comp.name,
                **(comp.config or {}),
            }

        # Build parameter grid
        param_paths = [sp["param_path"] for sp in sweep_params]
        param_names = [sp["name"] for sp in sweep_params]
        param_values = []
        for sp in sweep_params:
            vals = list(np.arange(sp["start"], sp["end"] + sp["step"] * 0.5, sp["step"]))
            param_values.append(vals)

        grid = list(itertools.product(*param_values))

        results_summary = []

        for idx, combo in enumerate(grid):
            # Deep-copy base config and apply parameter overrides
            cfg = copy.deepcopy(base_config)
            param_dict = {}
            for i, val in enumerate(combo):
                _set_nested(cfg, param_paths[i], float(val))
                param_dict[param_names[i]] = float(val)

            # Create simulation name
            param_label = ", ".join(f"{param_names[i]}={combo[i]:.2f}" for i in range(len(combo)))
            sim_name = f"{batch.name} [{param_label}]"

            # Create Simulation record
            sim = Simulation(
                project_id=batch.project_id,
                name=sim_name,
                status="running",
                dispatch_strategy=dispatch_strategy,
                config_snapshot={
                    "components": cfg,
                    "weather_dataset_id": str(weather_dataset_id),
                    "load_profile_id": str(load_profile_id),
                    "sweep_params": param_dict,
                },
                batch_run_id=batch.id,
            )
            session.add(sim)
            session.commit()
            session.refresh(sim)

            # Run simulation via existing task (called inline, not async)
            try:
                from app.worker.tasks import run_simulation
                run_simulation(str(sim.id))

                # Re-read to get results
                session.expire(sim)
                session.refresh(sim)

                # Get the result for summary
                sr = session.execute(
                    select(SimulationResult).where(SimulationResult.simulation_id == sim.id)
                ).scalar_one_or_none()

                if sr:
                    results_summary.append({
                        "simulation_id": str(sim.id),
                        "params": param_dict,
                        "npc": sr.npc,
                        "lcoe": sr.lcoe,
                        "irr": sr.irr,
                        "renewable_fraction": sr.renewable_fraction,
                    })

            except Exception as e:
                sim.status = "failed"
                sim.error_message = str(e)[:2000]
                session.commit()

            # Update batch progress
            batch.completed_runs = idx + 1
            session.commit()

        # Finalize
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
        batch.results_summary = results_summary
        session.commit()

    except Exception as e:
        try:
            batch = session.execute(
                select(BatchRun).where(BatchRun.id == uuid.UUID(batch_id))
            ).scalar_one()
            batch.status = "failed"
            batch.error_message = str(e)[:2000]
            session.commit()
        except Exception:
            pass
        raise

    finally:
        session.close()
