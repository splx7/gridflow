"""Simulation orchestrator for hybrid power system analysis.

``SimulationRunner`` wires together the solar, wind, battery, generator,
and grid engine modules into a single end-to-end annual simulation.  It
runs each component model, performs energy dispatch according to the
chosen strategy, and collects time-series and summary results.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from engine.solar.pv_system import simulate_pv
from engine.wind.weibull import simulate_wind_turbine
from engine.battery.battery_system import BatterySystem
from engine.generator.diesel_generator import DieselGenerator
from engine.generator.fuel_curve import FuelCurve
from engine.grid.grid_connection import GridConnection
from engine.grid.tariff import FlatTariff, TOUTariff

logger = logging.getLogger(__name__)

# ======================================================================
# Constants
# ======================================================================

HOURS_PER_YEAR: int = 8760

# Emission factors
CO2_KG_PER_LITRE_DIESEL: float = 2.68   # kg CO2 per litre of diesel
CO2_KG_PER_KWH_GRID: float = 0.50       # kg CO2 per kWh from grid


# ======================================================================
# Hour / month mapping
# ======================================================================

def _hour_to_month(hour_index: int) -> int:
    """Convert a 0-based hour-of-year index to a 1-based month (1--12)."""
    _MONTH_START_HOURS = [
        0, 744, 1416, 2160, 2880, 3624,
        4344, 5088, 5832, 6552, 7296, 8016,
    ]
    for m in range(11, -1, -1):
        if hour_index >= _MONTH_START_HOURS[m]:
            return m + 1  # 1-based
    return 1  # pragma: no cover


def _hour_of_day(hour_index: int) -> int:
    """Convert a 0-based hour-of-year index to hour of day (0--23)."""
    return hour_index % 24


# ======================================================================
# Tariff construction helper
# ======================================================================

def _build_tariff(tariff_cfg: dict | None):
    """Instantiate a tariff object from a configuration dict."""
    if tariff_cfg is None:
        return FlatTariff()

    tariff_type = tariff_cfg.get("type", "flat")

    if tariff_type == "flat":
        return FlatTariff(
            buy_rate=float(tariff_cfg.get("buy_rate", 0.12)),
            sell_rate=float(tariff_cfg.get("sell_rate", 0.04)),
        )
    elif tariff_type == "tou":
        return TOUTariff(
            schedule=tariff_cfg.get("schedule", {}),
            default_buy_rate=float(tariff_cfg.get("default_buy_rate", 0.10)),
            default_sell_rate=float(tariff_cfg.get("default_sell_rate", 0.03)),
        )
    else:
        return FlatTariff(
            buy_rate=float(tariff_cfg.get("buy_rate", 0.12)),
            sell_rate=float(tariff_cfg.get("sell_rate", 0.04)),
        )


# ======================================================================
# Dispatch strategies
# ======================================================================

def _dispatch_load_following(
    net_load: float,
    battery: BatterySystem | None,
    generator: DieselGenerator | None,
    grid: GridConnection | None,
    hour: int,
    month: int,
    gen_running: bool,
) -> dict[str, float]:
    """Load-following dispatch: RE first, then battery, then generator, then grid.

    The generator only runs to meet residual load that cannot be served
    by renewables or stored energy.  It does *not* charge the battery.
    """
    result: dict[str, float] = {
        "battery_charge_kw": 0.0,
        "battery_discharge_kw": 0.0,
        "generator_kw": 0.0,
        "generator_fuel_l": 0.0,
        "generator_cost": 0.0,
        "grid_import_kw": 0.0,
        "grid_import_cost": 0.0,
        "grid_export_kw": 0.0,
        "grid_export_revenue": 0.0,
        "unmet_kw": 0.0,
        "curtailed_kw": 0.0,
        "gen_running": gen_running,
    }

    deficit = net_load  # positive = load exceeds RE; negative = surplus RE

    if deficit > 0:
        # --- Serve deficit ---
        # 1) Battery discharge
        if battery is not None:
            discharged = battery.discharge(deficit)
            result["battery_discharge_kw"] = discharged
            deficit -= discharged

        # 2) Generator
        if deficit > 0 and generator is not None:
            out_kw, fuel_l, cost, running = generator.simulate_hour(
                deficit, gen_running
            )
            result["generator_kw"] = out_kw
            result["generator_fuel_l"] = fuel_l
            result["generator_cost"] = cost
            result["gen_running"] = running
            deficit -= out_kw

        # 3) Grid import
        if deficit > 0 and grid is not None:
            imported, cost = grid.import_power(deficit, _hour_of_day(hour), month)
            result["grid_import_kw"] = imported
            result["grid_import_cost"] = cost
            deficit -= imported

        # 4) Unmet load
        if deficit > 0:
            result["unmet_kw"] = deficit

    else:
        # --- Surplus RE ---
        surplus = -deficit

        # 1) Charge battery
        if battery is not None and surplus > 0:
            charged = battery.charge(surplus)
            result["battery_charge_kw"] = charged
            surplus -= charged

        # 2) Export to grid
        if surplus > 0 and grid is not None:
            exported, revenue = grid.export_power(
                surplus, _hour_of_day(hour), month
            )
            result["grid_export_kw"] = exported
            result["grid_export_revenue"] = revenue
            surplus -= exported

        # 3) Curtailed
        if surplus > 0:
            result["curtailed_kw"] = surplus

        # Turn off generator if running and no load
        if generator is not None and gen_running:
            generator.stop()
            result["gen_running"] = False

    return result


def _dispatch_cycle_charging(
    net_load: float,
    battery: BatterySystem | None,
    generator: DieselGenerator | None,
    grid: GridConnection | None,
    hour: int,
    month: int,
    gen_running: bool,
) -> dict[str, float]:
    """Cycle-charging dispatch: when the generator runs, it charges the battery too.

    If the generator must run, it operates at full rated capacity.
    Any surplus above the load is used to charge the battery.
    """
    result: dict[str, float] = {
        "battery_charge_kw": 0.0,
        "battery_discharge_kw": 0.0,
        "generator_kw": 0.0,
        "generator_fuel_l": 0.0,
        "generator_cost": 0.0,
        "grid_import_kw": 0.0,
        "grid_import_cost": 0.0,
        "grid_export_kw": 0.0,
        "grid_export_revenue": 0.0,
        "unmet_kw": 0.0,
        "curtailed_kw": 0.0,
        "gen_running": gen_running,
    }

    deficit = net_load

    if deficit > 0:
        # 1) Battery discharge
        if battery is not None:
            discharged = battery.discharge(deficit)
            result["battery_discharge_kw"] = discharged
            deficit -= discharged

        # 2) Generator at full load (cycle charging)
        if deficit > 0 and generator is not None:
            # Run at rated capacity for cycle charging
            gen_request = generator.rated_power_kw
            out_kw, fuel_l, cost, running = generator.simulate_hour(
                gen_request, gen_running
            )
            result["generator_kw"] = out_kw
            result["generator_fuel_l"] = fuel_l
            result["generator_cost"] = cost
            result["gen_running"] = running

            gen_surplus = out_kw - deficit
            deficit = 0.0

            # Use generator surplus to charge battery
            if gen_surplus > 0 and battery is not None:
                charged = battery.charge(gen_surplus)
                result["battery_charge_kw"] = charged
                gen_surplus -= charged

        # 3) Grid import for remaining deficit
        if deficit > 0 and grid is not None:
            imported, cost = grid.import_power(deficit, _hour_of_day(hour), month)
            result["grid_import_kw"] = imported
            result["grid_import_cost"] = cost
            deficit -= imported

        if deficit > 0:
            result["unmet_kw"] = deficit

    else:
        # Surplus RE -- same as load following
        surplus = -deficit

        if battery is not None and surplus > 0:
            charged = battery.charge(surplus)
            result["battery_charge_kw"] = charged
            surplus -= charged

        if surplus > 0 and grid is not None:
            exported, revenue = grid.export_power(
                surplus, _hour_of_day(hour), month
            )
            result["grid_export_kw"] = exported
            result["grid_export_revenue"] = revenue
            surplus -= exported

        if surplus > 0:
            result["curtailed_kw"] = surplus

        if generator is not None and gen_running:
            generator.stop()
            result["gen_running"] = False

    return result


def _dispatch_combined(
    net_load: float,
    battery: BatterySystem | None,
    generator: DieselGenerator | None,
    grid: GridConnection | None,
    hour: int,
    month: int,
    gen_running: bool,
) -> dict[str, float]:
    """Combined dispatch: load following when battery SOC is high, cycle charging when low.

    Switches to cycle-charging mode when the battery SOC drops below 30 %.
    """
    soc_threshold = 0.30

    if battery is not None:
        state = battery.get_state()
        soc = state["soc"]
    else:
        soc = 1.0  # no battery -- behave as load following

    if soc < soc_threshold:
        return _dispatch_cycle_charging(
            net_load, battery, generator, grid, hour, month, gen_running
        )
    else:
        return _dispatch_load_following(
            net_load, battery, generator, grid, hour, month, gen_running
        )


def _dispatch_optimal(
    net_load: float,
    battery: BatterySystem | None,
    generator: DieselGenerator | None,
    grid: GridConnection | None,
    hour: int,
    month: int,
    gen_running: bool,
) -> dict[str, float]:
    """Simplified optimal dispatch using a cost-priority heuristic.

    For each timestep, the cheapest available source is dispatched first:
    RE (free) > battery > grid (if cheap) > generator.
    """
    result: dict[str, float] = {
        "battery_charge_kw": 0.0,
        "battery_discharge_kw": 0.0,
        "generator_kw": 0.0,
        "generator_fuel_l": 0.0,
        "generator_cost": 0.0,
        "grid_import_kw": 0.0,
        "grid_import_cost": 0.0,
        "grid_export_kw": 0.0,
        "grid_export_revenue": 0.0,
        "unmet_kw": 0.0,
        "curtailed_kw": 0.0,
        "gen_running": gen_running,
    }

    deficit = net_load

    if deficit > 0:
        # Estimate marginal cost of each source
        grid_price = 0.0
        if grid is not None:
            grid_price = grid.tariff.buy_price(_hour_of_day(hour), month)

        gen_marginal = float("inf")
        if generator is not None:
            # Approximate marginal fuel cost per kWh
            fuel_l_per_kwh = (
                generator.fuel_curve.a1  # L/kWh marginal
            )
            gen_marginal = fuel_l_per_kwh * generator.fuel_price + (
                generator.om_cost_per_hour / max(generator.rated_power_kw, 1.0)
            )

        # Battery marginal cost is ~0 (already paid for via capital)
        battery_marginal = 0.01  # small value representing wear cost

        # Build priority list: (marginal_cost, source_name)
        sources = []
        if battery is not None:
            sources.append((battery_marginal, "battery"))
        if grid is not None:
            sources.append((grid_price, "grid"))
        if generator is not None:
            sources.append((gen_marginal, "generator"))

        sources.sort(key=lambda x: x[0])

        for _cost, source in sources:
            if deficit <= 0:
                break

            if source == "battery" and battery is not None:
                discharged = battery.discharge(deficit)
                result["battery_discharge_kw"] = discharged
                deficit -= discharged

            elif source == "grid" and grid is not None:
                imported, cost = grid.import_power(
                    deficit, _hour_of_day(hour), month
                )
                result["grid_import_kw"] = imported
                result["grid_import_cost"] = cost
                deficit -= imported

            elif source == "generator" and generator is not None:
                out_kw, fuel_l, cost, running = generator.simulate_hour(
                    deficit, gen_running
                )
                result["generator_kw"] = out_kw
                result["generator_fuel_l"] = fuel_l
                result["generator_cost"] = cost
                result["gen_running"] = running
                deficit -= out_kw

        if deficit > 0:
            result["unmet_kw"] = deficit

    else:
        # Surplus RE
        surplus = -deficit

        if battery is not None and surplus > 0:
            charged = battery.charge(surplus)
            result["battery_charge_kw"] = charged
            surplus -= charged

        if surplus > 0 and grid is not None:
            exported, revenue = grid.export_power(
                surplus, _hour_of_day(hour), month
            )
            result["grid_export_kw"] = exported
            result["grid_export_revenue"] = revenue
            surplus -= exported

        if surplus > 0:
            result["curtailed_kw"] = surplus

        if generator is not None and gen_running:
            generator.stop()
            result["gen_running"] = False

    return result


_DISPATCH_STRATEGIES = {
    "load_following": _dispatch_load_following,
    "cycle_charging": _dispatch_cycle_charging,
    "combined": _dispatch_combined,
    "optimal": _dispatch_optimal,
}


# ======================================================================
# SimulationRunner
# ======================================================================

class SimulationRunner:
    """End-to-end simulation orchestrator for a hybrid power system.

    Parameters
    ----------
    components : dict[str, dict]
        Component configurations keyed by type.  Recognised keys:

        * ``"solar_pv"`` -- PV system parameters (capacity_kwp, tilt,
          azimuth, latitude, longitude, and optional PVSystemConfig
          fields).
        * ``"wind_turbine"`` -- Wind turbine parameters (rated_power_kw,
          hub_height, rotor_diameter, and optional config dict).
        * ``"battery"`` -- Battery parameters (capacity_kwh,
          max_charge_kw, max_discharge_kw, etc.).
        * ``"diesel_generator"`` -- Generator parameters (rated_power_kw,
          min_load_ratio, fuel_price, etc.).
        * ``"grid_connection"`` -- Grid parameters (max_import_kw,
          max_export_kw, tariff config, etc.).

    weather : dict
        Weather data with at least the following 8760-element arrays:

        * ``"ghi"`` -- Global Horizontal Irradiance (W/m^2)
        * ``"dni"`` -- Direct Normal Irradiance (W/m^2)
        * ``"dhi"`` -- Diffuse Horizontal Irradiance (W/m^2)
        * ``"temperature"`` -- Ambient temperature (deg C)
        * ``"wind_speed"`` -- Wind speed (m/s)

    load_kw : ndarray, shape (8760,)
        Hourly electrical load demand in kW.
    dispatch_strategy : str
        One of ``"load_following"``, ``"cycle_charging"``,
        ``"combined"``, or ``"optimal"``.
    progress_callback : callable or None
        Optional ``callback(step: str, fraction: float)`` invoked at
        each major simulation stage.  *fraction* ranges from 0.0 to 1.0.
    """

    def __init__(
        self,
        components: dict[str, dict],
        weather: dict,
        load_kw: NDArray[np.floating],
        dispatch_strategy: str = "load_following",
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> None:
        self.components = components
        self.weather = weather
        self.load_kw = np.asarray(load_kw, dtype=np.float64)
        self.dispatch_strategy = dispatch_strategy
        self._progress = progress_callback

        if self.load_kw.shape[0] != HOURS_PER_YEAR:
            raise ValueError(
                f"load_kw must have {HOURS_PER_YEAR} elements, "
                f"got {self.load_kw.shape[0]}"
            )

        if dispatch_strategy not in _DISPATCH_STRATEGIES:
            raise ValueError(
                f"Unknown dispatch strategy '{dispatch_strategy}'. "
                f"Choose from: {sorted(_DISPATCH_STRATEGIES.keys())}"
            )

    # ------------------------------------------------------------------
    # Progress reporting
    # ------------------------------------------------------------------

    def _report(self, step: str, fraction: float) -> None:
        """Fire the progress callback if one was provided."""
        if self._progress is not None:
            try:
                self._progress(step, fraction)
            except Exception:
                pass  # Never let a callback error crash the simulation.
        logger.debug("Simulation step: %s (%.0f %%)", step, fraction * 100)

    # ------------------------------------------------------------------
    # Component instantiation helpers
    # ------------------------------------------------------------------

    def _build_battery(self) -> BatterySystem | None:
        cfg = self.components.get("battery")
        if cfg is None:
            return None

        return BatterySystem(
            capacity_kwh=float(cfg["capacity_kwh"]),
            max_charge_kw=float(cfg.get("max_charge_rate_kw", cfg.get("max_charge_kw", cfg["capacity_kwh"]))),
            max_discharge_kw=float(cfg.get("max_discharge_rate_kw", cfg.get("max_discharge_kw", cfg["capacity_kwh"]))),
            efficiency=float(cfg.get("round_trip_efficiency", cfg.get("efficiency", 0.90))),
            min_soc=float(cfg.get("min_soc", 0.10)),
            max_soc=float(cfg.get("max_soc", 0.95)),
            initial_soc=float(cfg.get("initial_soc", 0.50)),
            kibam_c=float(cfg.get("kibam_c", 0.7)),
            kibam_k=float(cfg.get("kibam_k", 0.5)),
            cycle_life=float(cfg.get("cycle_life", 5000.0)),
            chemistry=str(cfg.get("chemistry", "nmc")),
            depth_stress_factor=float(cfg.get("depth_stress_factor", 2.0)),
        )

    def _build_generator(self) -> DieselGenerator | None:
        cfg = self.components.get("diesel_generator")
        if cfg is None:
            return None

        fuel_curve_cfg = cfg.get("fuel_curve", {})
        fuel_curve = FuelCurve(
            a0=float(fuel_curve_cfg.get("a0", 0.0845)),
            a1=float(fuel_curve_cfg.get("a1", 0.2460)),
        )

        return DieselGenerator(
            rated_power_kw=float(cfg["rated_power_kw"]),
            min_load_ratio=float(cfg.get("min_load_ratio", 0.30)),
            fuel_curve=fuel_curve,
            fuel_price=float(cfg.get("fuel_price", 1.20)),
            om_cost_per_hour=float(cfg.get("om_cost_per_hour", 5.0)),
            start_cost=float(cfg.get("start_cost", 15.0)),
        )

    def _build_grid(self) -> GridConnection | None:
        cfg = self.components.get("grid_connection")
        if cfg is None:
            return None

        tariff = _build_tariff(cfg.get("tariff"))

        return GridConnection(
            max_import_kw=float(cfg.get("max_import_kw", 1000.0)),
            max_export_kw=float(cfg.get("max_export_kw", 500.0)),
            tariff=tariff,
            sell_back_enabled=bool(cfg.get("sell_back_enabled", True)),
            net_metering=bool(cfg.get("net_metering", False)),
        )

    # ------------------------------------------------------------------
    # Main simulation
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute the full annual simulation pipeline.

        Returns
        -------
        dict
            Comprehensive results including:

            Time-series arrays (8760,):
                ``load_kw``, ``pv_output_kw``, ``wind_output_kw``,
                ``re_output_kw``, ``battery_charge_kw``,
                ``battery_discharge_kw``, ``battery_soc``,
                ``generator_kw``, ``generator_fuel_l``,
                ``grid_import_kw``, ``grid_export_kw``,
                ``unmet_load_kw``, ``curtailed_kw``

            Summary scalars:
                ``annual_load_kwh``, ``annual_re_kwh``,
                ``renewable_fraction``, ``co2_emissions_kg``,
                ``total_fuel_l``, ``grid_import_kwh``,
                ``grid_export_kwh``, ``grid_import_cost``,
                ``grid_export_revenue``, ``unmet_load_kwh``,
                ``curtailed_kwh``, ``peak_load_kw``
        """
        n = HOURS_PER_YEAR

        # ---- Weather arrays ----
        ghi = np.asarray(self.weather.get("ghi", np.zeros(n)), dtype=np.float64)
        dni = np.asarray(self.weather.get("dni", np.zeros(n)), dtype=np.float64)
        dhi = np.asarray(self.weather.get("dhi", np.zeros(n)), dtype=np.float64)
        temperature = np.asarray(
            self.weather.get("temperature", np.full(n, 25.0)), dtype=np.float64
        )
        wind_speed = np.asarray(
            self.weather.get("wind_speed", np.zeros(n)), dtype=np.float64
        )

        # ==============================================================
        # Step 1: Parse component configs
        # ==============================================================
        self._report("Initialising components", 0.0)

        # ==============================================================
        # Step 2: Solar PV simulation
        # ==============================================================
        pv_output = np.zeros(n, dtype=np.float64)
        pv_cfg = self.components.get("solar_pv")

        if pv_cfg is not None:
            self._report("Running solar PV simulation", 0.10)
            pv_output = simulate_pv(
                capacity_kwp=float(pv_cfg["capacity_kwp"]),
                tilt=float(pv_cfg.get("tilt", 30.0)),
                azimuth=float(pv_cfg.get("azimuth", 180.0)),
                latitude=float(pv_cfg["latitude"]),
                longitude=float(pv_cfg["longitude"]),
                ghi_8760=ghi,
                dni_8760=dni,
                dhi_8760=dhi,
                temp_8760=temperature,
                config=pv_cfg.get("config"),
            )
            # Apply inverter capacity clipping (DC/AC ratio)
            pv_cap_kwp = float(pv_cfg["capacity_kwp"])
            inv_cap = float(pv_cfg.get("inverter_capacity_kw") or pv_cap_kwp)
            if inv_cap < pv_cap_kwp:
                clipped_kwh = float(np.sum(np.maximum(pv_output - inv_cap, 0)))
                pv_output = np.minimum(pv_output, inv_cap)
                logger.info(
                    "Inverter clipping: %.0f kWh/year clipped (DC/AC=%.2f)",
                    clipped_kwh,
                    pv_cap_kwp / inv_cap,
                )

            logger.info(
                "PV simulation complete: %.0f kWh/year",
                float(np.sum(pv_output)),
            )

        # ==============================================================
        # Step 3: Wind turbine simulation
        # ==============================================================
        wind_output = np.zeros(n, dtype=np.float64)
        wind_cfg = self.components.get("wind_turbine")

        if wind_cfg is not None:
            self._report("Running wind turbine simulation", 0.25)
            wind_output = simulate_wind_turbine(
                rated_power_kw=float(wind_cfg["rated_power_kw"]),
                hub_height=float(wind_cfg.get("hub_height", 80.0)),
                rotor_diameter=float(wind_cfg.get("rotor_diameter", 50.0)),
                wind_speed_8760=wind_speed,
                temp_8760=temperature,
                config=wind_cfg.get("config"),
            )
            logger.info(
                "Wind simulation complete: %.0f kWh/year",
                float(np.sum(wind_output)),
            )

        # ==============================================================
        # Step 4: Sum renewable output
        # ==============================================================
        self._report("Computing renewable energy totals", 0.40)
        re_output = pv_output + wind_output

        # ==============================================================
        # Step 5-7: Set up storage, generator, and grid
        # ==============================================================
        self._report("Setting up dispatchable resources", 0.45)
        battery = self._build_battery()
        generator = self._build_generator()
        grid = self._build_grid()

        # ==============================================================
        # Step 8: Run dispatch
        # ==============================================================
        self._report("Running energy dispatch", 0.50)

        # Pre-allocate time-series output arrays.
        ts_battery_charge = np.zeros(n, dtype=np.float64)
        ts_battery_discharge = np.zeros(n, dtype=np.float64)
        ts_battery_soc = np.zeros(n, dtype=np.float64)
        ts_generator_kw = np.zeros(n, dtype=np.float64)
        ts_generator_fuel_l = np.zeros(n, dtype=np.float64)
        ts_grid_import = np.zeros(n, dtype=np.float64)
        ts_grid_export = np.zeros(n, dtype=np.float64)
        ts_unmet = np.zeros(n, dtype=np.float64)
        ts_curtailed = np.zeros(n, dtype=np.float64)

        total_grid_import_cost = 0.0
        total_grid_export_revenue = 0.0
        total_generator_cost = 0.0

        if self.dispatch_strategy == "optimal":
            # ----- LP optimal dispatch: solve entire year at once -----
            from engine.dispatch.optimal import dispatch_optimal as lp_dispatch

            lp_battery_cfg = None
            if "battery" in self.components:
                bc = self.components["battery"]
                lp_battery_cfg = {
                    "capacity_kwh": bc.get("capacity_kwh", 100),
                    "max_charge_kw": bc.get("max_charge_rate_kw", bc.get("max_charge_kw", 50)),
                    "max_discharge_kw": bc.get("max_discharge_rate_kw", bc.get("max_discharge_kw", 50)),
                    "efficiency": bc.get("round_trip_efficiency", bc.get("efficiency", 0.90)),
                    "min_soc": bc.get("min_soc", 0.10),
                    "max_soc": bc.get("max_soc", 0.95),
                    "initial_soc": bc.get("initial_soc", 0.50),
                }

            lp_gen_cfg = None
            if "diesel_generator" in self.components:
                gc = self.components["diesel_generator"]
                fc = gc.get("fuel_curve", {})
                lp_gen_cfg = {
                    "rated_power_kw": gc.get("rated_power_kw", 100),
                    "min_load_ratio": gc.get("min_load_ratio", 0.30),
                    "fuel_curve_a0": fc.get("a0", gc.get("fuel_curve_a0", 0.0845)),
                    "fuel_curve_a1": fc.get("a1", gc.get("fuel_curve_a1", 0.246)),
                    "fuel_price": gc.get("fuel_price", gc.get("fuel_price_per_liter", 1.20)),
                    "om_cost_per_hour": gc.get("om_cost_per_hour", 5.0),
                }

            lp_grid_cfg = None
            if grid is not None:
                lp_grid_cfg = {
                    "max_import_kw": grid.max_import_kw,
                    "max_export_kw": grid.max_export_kw,
                    "tariff": grid.tariff,
                    "sell_back_enabled": grid.sell_back_enabled,
                }

            self._report("Running LP optimal dispatch (HiGHS)", 0.55)
            lp_result = lp_dispatch(
                load_kw=self.load_kw,
                re_output_kw=re_output,
                battery_config=lp_battery_cfg,
                generator_config=lp_gen_cfg,
                grid_config=lp_grid_cfg,
            )
            self._report("LP dispatch complete", 0.90)

            # Map LP results to runner output arrays.
            ts_battery_charge = lp_result["battery_charge"]
            ts_battery_discharge = lp_result["battery_discharge"]
            ts_battery_soc = lp_result["battery_soc"]
            ts_generator_kw = lp_result["generator_output"]
            ts_grid_import = lp_result["grid_import"]
            ts_grid_export = lp_result["grid_export"]
            ts_unmet = lp_result["unmet"]
            ts_curtailed = lp_result["excess"]

            # Recompute fuel consumption from generator output.
            if generator is not None:
                for h in range(n):
                    if ts_generator_kw[h] > 0:
                        ts_generator_fuel_l[h] = (
                            generator.fuel_curve.a0 * generator.rated_power_kw
                            + generator.fuel_curve.a1 * ts_generator_kw[h]
                        )

            # Recompute grid costs from tariff.
            if grid is not None:
                for h in range(n):
                    month = _hour_to_month(h)
                    hod = _hour_of_day(h)
                    total_grid_import_cost += ts_grid_import[h] * grid.tariff.buy_price(hod, month)
                    total_grid_export_revenue += ts_grid_export[h] * grid.tariff.sell_price(hod, month)

            if generator is not None:
                total_generator_cost = float(np.sum(ts_generator_fuel_l)) * generator.fuel_price

        else:
            # ----- Hourly heuristic dispatch -----
            dispatch_fn = _DISPATCH_STRATEGIES[self.dispatch_strategy]
            gen_running = False

            # Report progress every ~10 % through the dispatch loop.
            progress_interval = n // 10

            for h in range(n):
                month = _hour_to_month(h)
                net_load = self.load_kw[h] - re_output[h]

                step_result = dispatch_fn(
                    net_load=net_load,
                    battery=battery,
                    generator=generator,
                    grid=grid,
                    hour=h,
                    month=month,
                    gen_running=gen_running,
                )

                ts_battery_charge[h] = step_result["battery_charge_kw"]
                ts_battery_discharge[h] = step_result["battery_discharge_kw"]
                ts_generator_kw[h] = step_result["generator_kw"]
                ts_generator_fuel_l[h] = step_result["generator_fuel_l"]
                ts_grid_import[h] = step_result["grid_import_kw"]
                ts_grid_export[h] = step_result["grid_export_kw"]
                ts_unmet[h] = step_result["unmet_kw"]
                ts_curtailed[h] = step_result["curtailed_kw"]

                total_grid_import_cost += step_result["grid_import_cost"]
                total_grid_export_revenue += step_result["grid_export_revenue"]
                total_generator_cost += step_result["generator_cost"]

                gen_running = step_result["gen_running"]

                # Track battery SOC.
                if battery is not None:
                    state = battery.get_state()
                    ts_battery_soc[h] = state["soc"]

                # Periodic progress update.
                if progress_interval > 0 and h % progress_interval == 0 and h > 0:
                    frac = 0.50 + 0.40 * (h / n)
                    self._report("Dispatching", frac)

        # ==============================================================
        # Step 9: Compute summary metrics
        # ==============================================================
        self._report("Computing summary metrics", 0.95)

        annual_load_kwh = float(np.sum(self.load_kw))
        annual_re_kwh = float(np.sum(re_output))
        annual_pv_kwh = float(np.sum(pv_output))
        annual_wind_kwh = float(np.sum(wind_output))
        total_fuel_l = float(np.sum(ts_generator_fuel_l))
        grid_import_kwh = float(np.sum(ts_grid_import))
        grid_export_kwh = float(np.sum(ts_grid_export))
        generator_kwh = float(np.sum(ts_generator_kw))
        unmet_kwh = float(np.sum(ts_unmet))
        curtailed_kwh = float(np.sum(ts_curtailed))

        # Energy actually served = load - unmet
        energy_served_kwh = annual_load_kwh - unmet_kwh

        # Renewable fraction: fraction of served energy from RE sources.
        # RE serves load directly or via battery (net of losses).
        if energy_served_kwh > 0:
            non_re_served = generator_kwh + grid_import_kwh
            renewable_fraction = max(
                0.0, 1.0 - non_re_served / energy_served_kwh
            )
        else:
            renewable_fraction = 0.0

        # CO2 emissions.
        co2_diesel_kg = total_fuel_l * CO2_KG_PER_LITRE_DIESEL
        co2_grid_kg = grid_import_kwh * CO2_KG_PER_KWH_GRID
        co2_total_kg = co2_diesel_kg + co2_grid_kg

        # Battery end-of-year state.
        battery_state: dict[str, float] | None = None
        if battery is not None:
            battery_state = battery.get_state()

        # Generator statistics.
        generator_stats: dict[str, float] | None = None
        if generator is not None:
            generator_stats = {
                "running_hours": generator.running_hours,
                "fuel_consumed_total_l": generator.fuel_consumed_total,
                "starts_count": generator.starts_count,
                "total_fuel_cost": generator.total_fuel_cost(),
                "total_om_cost": generator.total_om_cost(),
                "total_start_cost": generator.total_start_cost(),
            }

        # Grid statistics.
        grid_stats: dict[str, float] | None = None
        if grid is not None:
            grid_stats = {
                "total_import_kwh": grid.total_import_kwh,
                "total_export_kwh": grid.total_export_kwh,
                "net_cost": grid.net_cost(),
                "monthly_peaks": list(grid.monthly_peaks),
            }

        # ==============================================================
        # Step 10: Return results
        # ==============================================================
        self._report("Simulation complete", 1.0)

        return {
            # Time-series.
            "load_kw": self.load_kw,
            "pv_output_kw": pv_output,
            "wind_output_kw": wind_output,
            "re_output_kw": re_output,
            "battery_charge_kw": ts_battery_charge,
            "battery_discharge_kw": ts_battery_discharge,
            "battery_soc": ts_battery_soc,
            "generator_kw": ts_generator_kw,
            "generator_fuel_l": ts_generator_fuel_l,
            "grid_import_kw": ts_grid_import,
            "grid_export_kw": ts_grid_export,
            "unmet_load_kw": ts_unmet,
            "curtailed_kw": ts_curtailed,
            # Summary scalars.
            "annual_load_kwh": annual_load_kwh,
            "annual_re_kwh": annual_re_kwh,
            "annual_pv_kwh": annual_pv_kwh,
            "annual_wind_kwh": annual_wind_kwh,
            "energy_served_kwh": energy_served_kwh,
            "renewable_fraction": renewable_fraction,
            "co2_emissions_kg": co2_total_kg,
            "co2_diesel_kg": co2_diesel_kg,
            "co2_grid_kg": co2_grid_kg,
            "total_fuel_l": total_fuel_l,
            "generator_kwh": generator_kwh,
            "grid_import_kwh": grid_import_kwh,
            "grid_export_kwh": grid_export_kwh,
            "grid_import_cost": total_grid_import_cost,
            "grid_export_revenue": total_grid_export_revenue,
            "generator_cost": total_generator_cost,
            "unmet_load_kwh": unmet_kwh,
            "curtailed_kwh": curtailed_kwh,
            "peak_load_kw": float(np.max(self.load_kw)),
            # Sub-system state.
            "battery_state": battery_state,
            "generator_stats": generator_stats,
            "grid_stats": grid_stats,
            "dispatch_strategy": self.dispatch_strategy,
        }
