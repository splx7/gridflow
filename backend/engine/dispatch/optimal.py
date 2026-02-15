"""LP-optimal dispatch using the HiGHS solver via highspy.

Formulates the hourly dispatch of battery, generator, and grid as a linear
program and solves it to global optimality.  The objective minimises total
system cost over 8760 hours comprising:

* Generator fuel + O&M costs
* Grid import energy charges (time-of-use aware)
* Grid export revenue (subtracted from cost)
* A large penalty for any unmet load

Decision variables (per hour t, 0 <= t < 8760):
    battery_charge[t], battery_discharge[t], gen_output[t],
    grid_import[t], grid_export[t], excess[t], unmet[t]

Plus one SOC variable per hour:
    soc[t]   (state of charge in kWh)

Total variables: ~8 x 8760 = 70,080
Total constraints: ~4 x 8760 + 1 cyclic = 35,041 (approx.)

This module requires the ``highspy`` package (``pip install highspy``).
"""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from engine.grid.tariff import FlatTariff, TariffBase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOURS_PER_YEAR = 8760

# Penalty for unmet load -- high enough to discourage it, but finite so
# the solver can always find a feasible solution.
UNMET_PENALTY_PER_KWH = 10.0

# Cumulative hours at the start of each month (non-leap year).
_MONTH_START_HOURS = np.array(
    [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016],
    dtype=np.int64,
)


def _hour_to_month_and_hod(hour_of_year: int) -> tuple[int, int]:
    """Convert hour-of-year (0-8759) to (month 1-12, hour_of_day 0-23)."""
    month = int(np.searchsorted(_MONTH_START_HOURS, hour_of_year, side="right"))
    hour_of_day = hour_of_year % 24
    return month, hour_of_day


# ---------------------------------------------------------------------------
# Config extraction helpers
# ---------------------------------------------------------------------------


def _extract_battery_params(config: dict[str, Any] | None) -> dict[str, float] | None:
    """Normalise a battery configuration dict.

    Expected keys (all optional, with defaults):
        capacity_kwh, max_charge_kw, max_discharge_kw, efficiency,
        min_soc, max_soc, initial_soc.
    """
    if config is None:
        return None

    eff = float(config.get("efficiency", 0.90))
    one_way_eff = math.sqrt(eff)

    return {
        "capacity_kwh": float(config.get("capacity_kwh", 100.0)),
        "max_charge_kw": float(config.get("max_charge_kw", 50.0)),
        "max_discharge_kw": float(config.get("max_discharge_kw", 50.0)),
        "efficiency": eff,
        "one_way_eff": one_way_eff,
        "min_soc_kwh": float(config.get("min_soc", 0.10))
        * float(config.get("capacity_kwh", 100.0)),
        "max_soc_kwh": float(config.get("max_soc", 0.95))
        * float(config.get("capacity_kwh", 100.0)),
        "initial_soc_kwh": float(config.get("initial_soc", 0.50))
        * float(config.get("capacity_kwh", 100.0)),
    }


def _extract_generator_params(
    config: dict[str, Any] | None,
) -> dict[str, float] | None:
    """Normalise a generator configuration dict.

    Expected keys:
        rated_power_kw, min_load_ratio, fuel_curve_a0, fuel_curve_a1,
        fuel_price, om_cost_per_hour.
    """
    if config is None:
        return None

    rated = float(config.get("rated_power_kw", 100.0))
    a0 = float(config.get("fuel_curve_a0", 0.0845))
    a1 = float(config.get("fuel_curve_a1", 0.2460))
    fuel_price = float(config.get("fuel_price", 1.20))
    om_per_hr = float(config.get("om_cost_per_hour", 5.0))

    # Marginal cost per kWh of generator output:
    # cost = (a0 * rated + a1 * P) * fuel_price + om_per_hr
    # The LP uses a linear cost per kW of gen_output:
    #   variable_cost_per_kw = a1 * fuel_price  (marginal fuel)
    # plus a fixed cost when running: a0 * rated * fuel_price + om_per_hr.
    # Since the LP does not model on/off decisions (that would require MIP),
    # we approximate by spreading the no-load cost across the minimum load
    # range and penalising output below min_load with the marginal rate.
    # For the LP relaxation we simply use:
    #   gen_cost[t] = (a0 * rated * fuel_price + om_per_hr) / rated * gen[t]
    #               + a1 * fuel_price * gen[t]
    # i.e. cost_per_kw = (a0 * fuel_price + om_per_hr / rated) + a1 * fuel_price
    # This slightly under-estimates cost at low loading but is exact at rated.
    cost_per_kw = (a0 * fuel_price + om_per_hr / rated) + a1 * fuel_price

    return {
        "rated_power_kw": rated,
        "min_load_ratio": float(config.get("min_load_ratio", 0.30)),
        "cost_per_kw": cost_per_kw,
    }


def _extract_grid_params(
    config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalise a grid configuration dict.

    Expected keys:
        max_import_kw, max_export_kw, tariff (TariffBase instance or None),
        sell_back_enabled.
    """
    if config is None:
        return None

    tariff: TariffBase = config.get("tariff", None) or FlatTariff()

    return {
        "max_import_kw": float(config.get("max_import_kw", 1_000.0)),
        "max_export_kw": float(config.get("max_export_kw", 500.0)),
        "tariff": tariff,
        "sell_back_enabled": bool(config.get("sell_back_enabled", True)),
    }


# ---------------------------------------------------------------------------
# LP formulation and solve
# ---------------------------------------------------------------------------


def dispatch_optimal(
    load_kw: NDArray[np.floating],
    re_output_kw: NDArray[np.floating],
    battery_config: Optional[dict[str, Any]] = None,
    generator_config: Optional[dict[str, Any]] = None,
    grid_config: Optional[dict[str, Any]] = None,
) -> dict[str, NDArray[np.floating]]:
    """Solve the optimal dispatch LP using the HiGHS solver.

    Parameters
    ----------
    load_kw : ndarray, shape (8760,)
        Hourly electrical load in kW.
    re_output_kw : ndarray, shape (8760,)
        Combined renewable-energy output in kW.
    battery_config : dict or None
        Battery parameters.  Keys: ``capacity_kwh``, ``max_charge_kw``,
        ``max_discharge_kw``, ``efficiency``, ``min_soc``, ``max_soc``,
        ``initial_soc``.
    generator_config : dict or None
        Generator parameters.  Keys: ``rated_power_kw``, ``min_load_ratio``,
        ``fuel_curve_a0``, ``fuel_curve_a1``, ``fuel_price``,
        ``om_cost_per_hour``.
    grid_config : dict or None
        Grid parameters.  Keys: ``max_import_kw``, ``max_export_kw``,
        ``tariff`` (:class:`TariffBase`), ``sell_back_enabled``.

    Returns
    -------
    dict[str, ndarray]
        Keys (all ndarray of shape (8760,)):

        * ``battery_charge``   -- Power into battery (kW, >= 0).
        * ``battery_discharge``-- Power out of battery (kW, >= 0).
        * ``battery_power``    -- Net battery power (positive = discharge).
        * ``battery_soc``      -- Battery SOC fraction at end of each hour.
        * ``generator_output`` -- Generator output (kW).
        * ``grid_import``      -- Grid import (kW).
        * ``grid_export``      -- Grid export (kW).
        * ``excess``           -- Curtailed energy (kW).
        * ``unmet``            -- Unserved load (kW).
        * ``objective_value``  -- Scalar total cost (repeated as array for
                                  consistency, first element is the value).

    Raises
    ------
    ImportError
        If ``highspy`` is not installed.
    RuntimeError
        If the solver fails to find an optimal solution.
    """
    try:
        import highspy  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "The 'highspy' package is required for optimal dispatch. "
            "Install it with: pip install highspy"
        ) from exc

    load_kw = np.asarray(load_kw, dtype=np.float64)
    re_output_kw = np.asarray(re_output_kw, dtype=np.float64)

    if load_kw.shape != (HOURS_PER_YEAR,):
        raise ValueError(
            f"load_kw must have shape ({HOURS_PER_YEAR},), got {load_kw.shape}"
        )
    if re_output_kw.shape != (HOURS_PER_YEAR,):
        raise ValueError(
            f"re_output_kw must have shape ({HOURS_PER_YEAR},), "
            f"got {re_output_kw.shape}"
        )

    # ----- Parse configs ---------------------------------------------------
    batt = _extract_battery_params(battery_config)
    gen = _extract_generator_params(generator_config)
    grid = _extract_grid_params(grid_config)

    has_batt = batt is not None
    has_gen = gen is not None
    has_grid = grid is not None

    T = HOURS_PER_YEAR
    INF = highspy.kHighsInf

    # ----- Variable index layout -------------------------------------------
    # For each hour t we have 7 decision variables:
    #   batt_charge[t], batt_discharge[t], gen_out[t],
    #   grid_imp[t], grid_exp[t], excess[t], unmet[t]
    # Plus 1 state variable:
    #   soc[t]  (battery SOC in kWh)

    VARS_PER_HOUR = 7
    BATT_CH = 0
    BATT_DISCH = 1
    GEN_OUT = 2
    GRID_IMP = 3
    GRID_EXP = 4
    EXCESS = 5
    UNMET = 6

    n_dispatch_vars = VARS_PER_HOUR * T
    # SOC variables start after all dispatch variables.
    soc_offset = n_dispatch_vars
    n_soc_vars = T if has_batt else 0
    n_vars = n_dispatch_vars + n_soc_vars

    def _idx(var_type: int, t: int) -> int:
        """Column index for a dispatch variable at hour t."""
        return t * VARS_PER_HOUR + var_type

    def _soc_idx(t: int) -> int:
        """Column index for the SOC variable at hour t."""
        return soc_offset + t

    # ----- Pre-compute hourly tariff prices --------------------------------
    import_price = np.zeros(T, dtype=np.float64)
    export_price = np.zeros(T, dtype=np.float64)

    if has_grid:
        grid_tariff: TariffBase = grid["tariff"]
        for t in range(T):
            month, hod = _hour_to_month_and_hod(t)
            import_price[t] = grid_tariff.buy_price(hod, month)
            export_price[t] = grid_tariff.sell_price(hod, month)

    # ----- Build objective coefficients ------------------------------------
    col_cost = np.zeros(n_vars, dtype=np.float64)

    gen_cost_per_kw = gen["cost_per_kw"] if has_gen else 0.0

    for t in range(T):
        # Generator cost.
        col_cost[_idx(GEN_OUT, t)] = gen_cost_per_kw if has_gen else 0.0

        # Grid import cost.
        col_cost[_idx(GRID_IMP, t)] = import_price[t] if has_grid else 0.0

        # Grid export revenue (negative cost).
        if has_grid and grid["sell_back_enabled"]:
            col_cost[_idx(GRID_EXP, t)] = -export_price[t]
        else:
            col_cost[_idx(GRID_EXP, t)] = 0.0

        # Excess has zero cost (curtailment is free).
        col_cost[_idx(EXCESS, t)] = 0.0

        # Unmet load penalty.
        col_cost[_idx(UNMET, t)] = UNMET_PENALTY_PER_KWH

        # Battery charge/discharge: zero direct cost (cost is implicit
        # through the grid/gen that provides the power).
        col_cost[_idx(BATT_CH, t)] = 0.0
        col_cost[_idx(BATT_DISCH, t)] = 0.0

    # SOC variables have zero cost.
    # (already zero from initialization)

    # ----- Variable bounds -------------------------------------------------
    col_lower = np.zeros(n_vars, dtype=np.float64)
    col_upper = np.full(n_vars, INF, dtype=np.float64)

    for t in range(T):
        # Battery charge/discharge bounds.
        if has_batt:
            col_upper[_idx(BATT_CH, t)] = batt["max_charge_kw"]
            col_upper[_idx(BATT_DISCH, t)] = batt["max_discharge_kw"]
        else:
            col_upper[_idx(BATT_CH, t)] = 0.0
            col_upper[_idx(BATT_DISCH, t)] = 0.0

        # Generator bounds.
        if has_gen:
            # LP relaxation: allow any output between 0 and rated.
            # (Minimum-load constraint would require MIP for on/off.)
            col_upper[_idx(GEN_OUT, t)] = gen["rated_power_kw"]
        else:
            col_upper[_idx(GEN_OUT, t)] = 0.0

        # Grid bounds.
        if has_grid:
            col_upper[_idx(GRID_IMP, t)] = grid["max_import_kw"]
            if grid["sell_back_enabled"]:
                col_upper[_idx(GRID_EXP, t)] = grid["max_export_kw"]
            else:
                col_upper[_idx(GRID_EXP, t)] = 0.0
        else:
            col_upper[_idx(GRID_IMP, t)] = 0.0
            col_upper[_idx(GRID_EXP, t)] = 0.0

        # Excess and unmet are non-negative (lower=0, upper=INF).

    # SOC variable bounds.
    if has_batt:
        for t in range(T):
            col_lower[_soc_idx(t)] = batt["min_soc_kwh"]
            col_upper[_soc_idx(t)] = batt["max_soc_kwh"]

    # ----- Build constraint matrix (sparse, row-by-row) --------------------
    # We will collect constraints in COO format and convert to CSC.
    row_indices: list[int] = []
    col_indices: list[int] = []
    values: list[float] = []
    row_lower: list[float] = []
    row_upper: list[float] = []
    n_rows = 0

    def _add_constraint(
        coeffs: list[tuple[int, float]],
        lb: float,
        ub: float,
    ) -> None:
        """Register one constraint row."""
        nonlocal n_rows
        for col, val in coeffs:
            row_indices.append(n_rows)
            col_indices.append(col)
            values.append(val)
        row_lower.append(lb)
        row_upper.append(ub)
        n_rows += 1

    for t in range(T):
        month, hod = _hour_to_month_and_hod(t)

        # ---- 1. Energy balance (equality) ---------------------------------
        # re[t] + gen[t] + batt_discharge[t] + grid_import[t]
        #   = load[t] + batt_charge[t] + grid_export[t] + excess[t] - unmet[t]
        #
        # Rearranged to LHS:
        # gen[t] + batt_discharge[t] + grid_import[t]
        #   - batt_charge[t] - grid_export[t] - excess[t] + unmet[t]
        #   = load[t] - re[t]
        rhs = load_kw[t] - re_output_kw[t]
        coeffs: list[tuple[int, float]] = [
            (_idx(BATT_DISCH, t), 1.0),
            (_idx(BATT_CH, t), -1.0),
            (_idx(GEN_OUT, t), 1.0),
            (_idx(GRID_IMP, t), 1.0),
            (_idx(GRID_EXP, t), -1.0),
            (_idx(EXCESS, t), -1.0),
            (_idx(UNMET, t), 1.0),
        ]
        _add_constraint(coeffs, rhs, rhs)

        # ---- 2. Battery SOC continuity ------------------------------------
        if has_batt:
            # soc[t] = soc[t-1] + charge[t] * eta_one_way - discharge[t] / eta_one_way
            # => soc[t] - charge[t] * eta + discharge[t] / eta = soc[t-1]
            eta = batt["one_way_eff"]
            if t == 0:
                # soc[-1] is the initial SOC.
                rhs_soc = batt["initial_soc_kwh"]
            else:
                rhs_soc = 0.0  # we add soc[t-1] coefficient below

            soc_coeffs: list[tuple[int, float]] = [
                (_soc_idx(t), 1.0),
                (_idx(BATT_CH, t), -eta),
                (_idx(BATT_DISCH, t), 1.0 / eta),
            ]
            if t > 0:
                soc_coeffs.append((_soc_idx(t - 1), -1.0))

            _add_constraint(soc_coeffs, rhs_soc, rhs_soc)

    # ---- 3. Cyclic SOC constraint: soc[T-1] = initial_soc -----------------
    if has_batt:
        cyc_coeffs: list[tuple[int, float]] = [(_soc_idx(T - 1), 1.0)]
        cyc_rhs = batt["initial_soc_kwh"]
        _add_constraint(cyc_coeffs, cyc_rhs, cyc_rhs)

    # ----- Create HiGHS model and solve ------------------------------------
    h = highspy.Highs()
    h.silent()

    # Build sparse column representation from COO data.
    # Convert to numpy arrays for efficient handoff.
    coo_row = np.array(row_indices, dtype=np.int32)
    coo_col = np.array(col_indices, dtype=np.int32)
    coo_val = np.array(values, dtype=np.float64)

    # Add variables.
    h.addVars(n_vars, col_lower, col_upper)

    # Set objective (minimise).
    h.changeObjectiveSense(highspy.ObjSense.kMinimize)
    for j in range(n_vars):
        if col_cost[j] != 0.0:
            h.changeObjectiveCost(j, float(col_cost[j]))

    # Add constraints row by row.  While this is not the fastest method,
    # it avoids building a full CSC matrix in Python and is adequate for
    # ~35k rows.
    rl = np.array(row_lower, dtype=np.float64)
    ru = np.array(row_upper, dtype=np.float64)

    # Group entries by row for efficient addRow calls.
    # Pre-sort by row index.
    sort_order = np.argsort(coo_row, kind="stable")
    coo_row = coo_row[sort_order]
    coo_col = coo_col[sort_order]
    coo_val = coo_val[sort_order]

    # Find row boundaries.
    row_starts = np.searchsorted(coo_row, np.arange(n_rows), side="left")
    row_ends = np.searchsorted(coo_row, np.arange(n_rows), side="right")

    for r in range(n_rows):
        s, e = int(row_starts[r]), int(row_ends[r])
        if s == e:
            # Empty row (should not happen but handle gracefully).
            h.addRow(float(rl[r]), float(ru[r]), 0, np.array([], dtype=np.int32), np.array([], dtype=np.float64))
        else:
            h.addRow(
                float(rl[r]),
                float(ru[r]),
                int(e - s),
                coo_col[s:e].astype(np.int32),
                coo_val[s:e],
            )

    # Solve.
    h.run()

    status = h.getInfoValue("primal_solution_status")[1]
    # HiGHS primal_solution_status: 2 = feasible
    model_status = h.getModelStatus()
    if model_status != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(
            f"HiGHS did not find an optimal solution. "
            f"Model status: {model_status}"
        )

    sol = np.array(h.getSolution().col_value, dtype=np.float64)
    obj_val = h.getInfoValue("objective_function_value")[1]

    # ----- Extract results -------------------------------------------------
    batt_ch = np.array([sol[_idx(BATT_CH, t)] for t in range(T)])
    batt_disch = np.array([sol[_idx(BATT_DISCH, t)] for t in range(T)])
    gen_out = np.array([sol[_idx(GEN_OUT, t)] for t in range(T)])
    g_imp = np.array([sol[_idx(GRID_IMP, t)] for t in range(T)])
    g_exp = np.array([sol[_idx(GRID_EXP, t)] for t in range(T)])
    ex = np.array([sol[_idx(EXCESS, t)] for t in range(T)])
    un = np.array([sol[_idx(UNMET, t)] for t in range(T)])

    # Battery SOC in kWh -> fraction.
    if has_batt:
        soc_kwh = np.array([sol[_soc_idx(t)] for t in range(T)])
        soc_frac = soc_kwh / batt["capacity_kwh"]
    else:
        soc_frac = np.zeros(T, dtype=np.float64)

    # Net battery power (positive = discharge convention).
    batt_net = batt_disch - batt_ch

    # Clip tiny negative values from solver tolerance.
    batt_ch = np.maximum(batt_ch, 0.0)
    batt_disch = np.maximum(batt_disch, 0.0)
    gen_out = np.maximum(gen_out, 0.0)
    g_imp = np.maximum(g_imp, 0.0)
    g_exp = np.maximum(g_exp, 0.0)
    ex = np.maximum(ex, 0.0)
    un = np.maximum(un, 0.0)

    objective_arr = np.zeros(T, dtype=np.float64)
    objective_arr[0] = obj_val

    return {
        "battery_charge": batt_ch,
        "battery_discharge": batt_disch,
        "battery_power": batt_net,
        "battery_soc": soc_frac,
        "generator_output": gen_out,
        "grid_import": g_imp,
        "grid_export": g_exp,
        "excess": ex,
        "unmet": un,
        "objective_value": objective_arr,
    }
