"""Sensitivity analysis for power system economics.

Provides one-at-a-time (OAT) sensitivity sweeps suitable for spider
plots and tornado diagrams.  Each variable is varied independently
while all others remain at their base-case values.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import numpy as np


# ======================================================================
# Helpers
# ======================================================================

def _set_nested(d: dict, path: str, value: Any) -> dict:
    """Set a value in a nested dict using a dot-separated *path*.

    Parameters
    ----------
    d : dict
        The dictionary to modify (a deep copy is recommended beforehand).
    path : str
        Dot-separated key path, e.g. ``"diesel_generator.fuel_price"``.
    value : Any
        The value to assign at the terminal key.

    Returns
    -------
    dict
        The modified dictionary (same reference as *d*).
    """
    keys = path.split(".")
    obj = d
    for key in keys[:-1]:
        # Navigate into nested dicts; create intermediate dicts if absent.
        if key not in obj or not isinstance(obj[key], dict):
            obj[key] = {}
        obj = obj[key]
    obj[keys[-1]] = value
    return d


def _get_nested(d: dict, path: str, default: Any = None) -> Any:
    """Retrieve a value from a nested dict using a dot-separated *path*.

    Parameters
    ----------
    d : dict
        Source dictionary.
    path : str
        Dot-separated key path.
    default : Any
        Value to return if the path does not exist.

    Returns
    -------
    Any
        The value found at *path*, or *default*.
    """
    keys = path.split(".")
    obj = d
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            return default
        obj = obj[key]
    return obj


# ======================================================================
# Metrics of interest
# ======================================================================

_METRIC_KEYS = ("npc", "lcoe", "irr", "payback_years")


def _extract_metrics(result: dict) -> dict[str, float | None]:
    """Pull the standard economic metrics out of a run result."""
    return {k: result.get(k) for k in _METRIC_KEYS}


# ======================================================================
# Main entry point
# ======================================================================

def sensitivity_analysis(
    base_params: dict,
    variables: list[dict],
    run_fn: Callable[[dict], dict],
) -> dict:
    """Run one-at-a-time sensitivity analysis.

    Parameters
    ----------
    base_params : dict
        Base-case simulation parameters.  A deep copy is made for each
        evaluation so the original is never mutated.
    variables : list[dict]
        Each entry describes one sensitivity variable::

            {
                "name": "Fuel Price",
                "param_path": "components.diesel_generator.fuel_price",
                "range": [0.80, 2.00],
                "points": 11,          # optional, default 11
            }

        * ``name`` -- human-readable label for the variable.
        * ``param_path`` -- dot-separated path into *base_params* to the
          scalar that should be varied.
        * ``range`` -- ``[min_value, max_value]`` for the sweep.
        * ``points`` -- number of evaluation points (linearly spaced).

    run_fn : callable
        ``run_fn(params) -> dict`` that accepts a complete parameter set
        and returns a results dictionary containing at minimum ``npc``,
        ``lcoe``, and ``irr`` keys.

    Returns
    -------
    dict
        Top-level keys:

        * ``"spider"`` -- data formatted for spider / sensitivity plots.
          ``{variable_name: [{"value": v, "npc": ..., "lcoe": ..., ...}, ...]}``
        * ``"tornado"`` -- data formatted for tornado diagrams.
          ``{variable_name: {"low_value", "high_value", "low_npc",
          "high_npc", "base_npc"}}``
        * ``"base_results"`` -- metrics from the unperturbed base case.
    """
    # --- Run the base case first ---
    base_results = run_fn(copy.deepcopy(base_params))
    base_metrics = _extract_metrics(base_results)
    base_npc = base_metrics.get("npc", 0.0)

    spider: dict[str, list[dict[str, Any]]] = {}
    tornado: dict[str, dict[str, Any]] = {}

    for var in variables:
        name: str = var["name"]
        param_path: str = var["param_path"]
        val_range: list[float] = var["range"]
        n_points: int = int(var.get("points", 11))

        if n_points < 2:
            n_points = 2

        low_val = float(val_range[0])
        high_val = float(val_range[1])
        sweep_values = np.linspace(low_val, high_val, n_points).tolist()

        sweep_results: list[dict[str, Any]] = []

        for val in sweep_values:
            # Only deep-copy mutable config dicts; share weather/load arrays
            # (they are never mutated by the simulation runner).
            params = {
                "components": copy.deepcopy(base_params["components"]),
                "project": copy.deepcopy(base_params["project"]),
                "dispatch_strategy": base_params["dispatch_strategy"],
                "weather": base_params["weather"],
                "load_kw": base_params["load_kw"],
            }
            _set_nested(params, param_path, val)

            result = run_fn(params)
            metrics = _extract_metrics(result)
            entry: dict[str, Any] = {"value": val}
            entry.update(metrics)
            sweep_results.append(entry)

        spider[name] = sweep_results

        # Tornado data: use the extreme ends of the sweep.
        low_result = sweep_results[0]
        high_result = sweep_results[-1]

        tornado[name] = {
            "low_value": low_val,
            "high_value": high_val,
            "low_npc": low_result.get("npc"),
            "high_npc": high_result.get("npc"),
            "low_lcoe": low_result.get("lcoe"),
            "high_lcoe": high_result.get("lcoe"),
            "low_irr": low_result.get("irr"),
            "high_irr": high_result.get("irr"),
            "base_npc": base_npc,
            "base_lcoe": base_metrics.get("lcoe"),
            "base_irr": base_metrics.get("irr"),
            "npc_spread": abs(
                (high_result.get("npc") or 0.0) - (low_result.get("npc") or 0.0)
            ),
        }

    return {
        "spider": spider,
        "tornado": tornado,
        "base_results": base_metrics,
    }
