"""Grid connection model with import/export limits and tariff accounting.

Represents the point of common coupling (PCC) between a microgrid or
distributed-energy-resource site and the utility grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .tariff import DemandCharge, TariffBase


@dataclass
class GridConnection:
    """Bi-directional grid interconnection with metering and billing.

    Parameters
    ----------
    max_import_kw : float
        Maximum power the site can draw from the grid (kW).
        Typically set by the utility interconnection agreement.
    max_export_kw : float
        Maximum power the site can push back to the grid (kW).
        Set to 0.0 to disallow any export.
    tariff : TariffBase
        Energy tariff used for import/export pricing.
    sell_back_enabled : bool
        If ``False``, any excess generation is curtailed rather than sold.
    net_metering : bool
        If ``True``, exported energy offsets imported energy at the buy
        rate within each billing period, rather than being compensated at
        the (usually lower) sell rate.
    demand_charge : Optional[DemandCharge]
        An optional monthly demand-charge component.  If ``None``, no
        demand charges are applied.
    """

    max_import_kw: float = 1_000.0
    max_export_kw: float = 500.0
    tariff: TariffBase = field(default=None)  # type: ignore[assignment]
    sell_back_enabled: bool = True
    net_metering: bool = False
    demand_charge: Optional[DemandCharge] = None

    # --- Accumulators (not constructor params) ----------------------------
    total_import_kwh: float = field(default=0.0, init=False, repr=False)
    total_export_kwh: float = field(default=0.0, init=False, repr=False)
    total_cost: float = field(default=0.0, init=False, repr=False)
    monthly_peaks: List[float] = field(
        default_factory=lambda: [0.0] * 12, init=False, repr=False
    )

    # Per-month energy accumulators for net-metering settlement.
    _monthly_import_kwh: List[float] = field(
        default_factory=lambda: [0.0] * 12, init=False, repr=False
    )
    _monthly_export_kwh: List[float] = field(
        default_factory=lambda: [0.0] * 12, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.tariff is None:
            from .tariff import FlatTariff

            self.tariff = FlatTariff()

        if self.max_import_kw < 0:
            raise ValueError(
                f"max_import_kw must be >= 0, got {self.max_import_kw}"
            )
        if self.max_export_kw < 0:
            raise ValueError(
                f"max_export_kw must be >= 0, got {self.max_export_kw}"
            )

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_power(
        self, kw_needed: float, hour: int, month: int
    ) -> Tuple[float, float]:
        """Import energy from the grid.

        Parameters
        ----------
        kw_needed : float
            Desired import power (kW).  Clamped to ``max_import_kw``.
        hour : int
            Hour of day, 0 -- 23.
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        actual_kw : float
            Power actually imported (kW), after applying the interconnect
            limit.
        cost : float
            Energy cost for this one-hour time-step ($).
        """
        if kw_needed <= 0:
            return 0.0, 0.0

        actual_kw = min(kw_needed, self.max_import_kw)
        energy_kwh = actual_kw  # 1-hour time step

        price = self.tariff.buy_price(hour, month)
        cost = energy_kwh * price

        # Update accumulators.
        self.total_import_kwh += energy_kwh
        self.total_cost += cost
        self._monthly_import_kwh[month - 1] += energy_kwh

        # Track peak demand for this month.
        idx = month - 1
        if actual_kw > self.monthly_peaks[idx]:
            self.monthly_peaks[idx] = actual_kw

        # Record demand for optional demand-charge tariff.
        if self.demand_charge is not None:
            self.demand_charge.record_demand(actual_kw, month)

        return actual_kw, cost

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_power(
        self, kw_excess: float, hour: int, month: int
    ) -> Tuple[float, float]:
        """Export surplus energy to the grid.

        Parameters
        ----------
        kw_excess : float
            Surplus power available for export (kW).
        hour : int
            Hour of day, 0 -- 23.
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        actual_kw : float
            Power actually exported (kW).  Zero if sell-back is disabled.
        revenue : float
            Revenue (or credit) earned for this one-hour step ($).
        """
        if kw_excess <= 0 or not self.sell_back_enabled:
            return 0.0, 0.0

        actual_kw = min(kw_excess, self.max_export_kw)
        energy_kwh = actual_kw  # 1-hour time step

        if self.net_metering:
            # Under net metering, export is valued at the buy rate.
            price = self.tariff.buy_price(hour, month)
        else:
            price = self.tariff.sell_price(hour, month)

        revenue = energy_kwh * price

        # Update accumulators.
        self.total_export_kwh += energy_kwh
        self.total_cost -= revenue  # revenue reduces net cost
        self._monthly_export_kwh[month - 1] += energy_kwh

        return actual_kw, revenue

    # ------------------------------------------------------------------
    # Demand-charge settlement
    # ------------------------------------------------------------------

    def monthly_demand_charge(self, month: int) -> float:
        """Calculate the demand charge for a specific month.

        Parameters
        ----------
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        float
            Demand charge ($).  Returns 0.0 if no demand-charge tariff
            is attached.
        """
        if self.demand_charge is None:
            return 0.0
        return self.demand_charge.monthly_charge(month)

    def total_demand_charges(self) -> float:
        """Total demand charges across all twelve months ($)."""
        if self.demand_charge is None:
            return 0.0
        return self.demand_charge.total_annual_charge()

    # ------------------------------------------------------------------
    # Net-metering settlement
    # ------------------------------------------------------------------

    def net_metering_balance(self, month: int) -> float:
        """Net energy balance for a month under net metering.

        Parameters
        ----------
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        float
            Net kWh: positive means net import, negative means net export.
        """
        idx = month - 1
        return self._monthly_import_kwh[idx] - self._monthly_export_kwh[idx]

    # ------------------------------------------------------------------
    # Summary & reset
    # ------------------------------------------------------------------

    def net_cost(self) -> float:
        """Total net grid cost including demand charges ($).

        Positive values represent a net expense; negative values mean
        the site earned more from exports than it spent on imports.
        """
        return self.total_cost + self.total_demand_charges()

    def reset(self) -> None:
        """Zero-out all accumulators for a fresh simulation run."""
        self.total_import_kwh = 0.0
        self.total_export_kwh = 0.0
        self.total_cost = 0.0
        self.monthly_peaks = [0.0] * 12
        self._monthly_import_kwh = [0.0] * 12
        self._monthly_export_kwh = [0.0] * 12
        if self.demand_charge is not None:
            self.demand_charge.reset()
