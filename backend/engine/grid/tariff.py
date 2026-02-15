"""Electricity tariff structures for grid-connection modelling.

Provides composable tariff objects used by :class:`GridConnection` to price
energy imports, exports, and demand charges.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List


# ======================================================================
# Abstract base
# ======================================================================

class TariffBase(ABC):
    """Interface that every tariff structure must implement."""

    @abstractmethod
    def buy_price(self, hour: int, month: int) -> float:
        """Return the cost to *buy* (import) 1 kWh at the given time.

        Parameters
        ----------
        hour : int
            Hour of day, 0 -- 23.
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        float
            Import price in $/kWh.
        """

    @abstractmethod
    def sell_price(self, hour: int, month: int) -> float:
        """Return the revenue for *selling* (exporting) 1 kWh.

        Parameters
        ----------
        hour : int
            Hour of day, 0 -- 23.
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        float
            Export price in $/kWh (may be zero).
        """


# ======================================================================
# Flat tariff
# ======================================================================

@dataclass
class FlatTariff(TariffBase):
    """Fixed $/kWh rate that does not vary with time.

    Parameters
    ----------
    buy_rate : float
        Cost to import energy ($/kWh).
    sell_rate : float
        Revenue for exporting energy ($/kWh).  Set to 0.0 if export is
        not compensated.
    """

    buy_rate: float = 0.12
    sell_rate: float = 0.04

    def __post_init__(self) -> None:
        if self.buy_rate < 0:
            raise ValueError(f"buy_rate must be >= 0, got {self.buy_rate}")
        if self.sell_rate < 0:
            raise ValueError(f"sell_rate must be >= 0, got {self.sell_rate}")

    def buy_price(self, hour: int, month: int) -> float:  # noqa: D401
        return self.buy_rate

    def sell_price(self, hour: int, month: int) -> float:  # noqa: D401
        return self.sell_rate


# ======================================================================
# Time-of-Use tariff
# ======================================================================

@dataclass
class TOUPeriod:
    """A single time-of-use pricing period.

    Parameters
    ----------
    name : str
        Human-readable label (e.g. ``"peak"``, ``"off-peak"``).
    rate : float
        Import price during this period ($/kWh).
    sell_rate : float
        Export price during this period ($/kWh).
    hours : List[int]
        Hours of the day when this period applies (0 -- 23).
    months : List[int]
        Months when this period applies (1 -- 12).
    """

    name: str
    rate: float
    sell_rate: float
    hours: List[int]
    months: List[int]


@dataclass
class TOUTariff(TariffBase):
    """Time-of-use tariff with multiple pricing periods.

    Parameters
    ----------
    schedule : Dict[str, dict]
        Mapping of period name to its definition.  Each value must contain:

        * ``rate`` (float): import $/kWh
        * ``hours`` (List[int]): applicable hours 0 -- 23
        * ``months`` (List[int]): applicable months 1 -- 12

        Optional keys:

        * ``sell_rate`` (float): export $/kWh (defaults to 0.0)

    default_buy_rate : float
        Fallback import price for any (hour, month) not covered by a
        defined period.
    default_sell_rate : float
        Fallback export price for uncovered (hour, month) pairs.

    Example
    -------
    >>> schedule = {
    ...     "peak": {
    ...         "rate": 0.25,
    ...         "sell_rate": 0.08,
    ...         "hours": [16, 17, 18, 19, 20],
    ...         "months": [6, 7, 8, 9],
    ...     },
    ...     "off_peak": {
    ...         "rate": 0.08,
    ...         "sell_rate": 0.03,
    ...         "hours": list(range(0, 16)) + [21, 22, 23],
    ...         "months": list(range(1, 13)),
    ...     },
    ... }
    >>> tariff = TOUTariff(schedule=schedule)
    """

    schedule: Dict[str, dict] = field(default_factory=dict)
    default_buy_rate: float = 0.10
    default_sell_rate: float = 0.03

    def __post_init__(self) -> None:
        # Pre-build lookup tables indexed by (hour, month) for O(1) access.
        self._buy_lookup: Dict[tuple, float] = {}
        self._sell_lookup: Dict[tuple, float] = {}

        for _name, period in self.schedule.items():
            rate = period["rate"]
            sell_rate = period.get("sell_rate", 0.0)
            hours: List[int] = period["hours"]
            months: List[int] = period["months"]

            for h in hours:
                for m in months:
                    key = (h, m)
                    # Last-write-wins if periods overlap; caller is
                    # responsible for non-overlapping definitions.
                    self._buy_lookup[key] = rate
                    self._sell_lookup[key] = sell_rate

    def buy_price(self, hour: int, month: int) -> float:  # noqa: D401
        return self._buy_lookup.get((hour, month), self.default_buy_rate)

    def sell_price(self, hour: int, month: int) -> float:  # noqa: D401
        return self._sell_lookup.get((hour, month), self.default_sell_rate)


# ======================================================================
# Demand charge
# ======================================================================

@dataclass
class DemandCharge(TariffBase):
    """Monthly peak-demand charge layered on top of an energy tariff.

    This tariff only produces a charge based on the highest instantaneous
    import recorded during each billing month.  Energy-based buy/sell
    prices are zero -- combine with a :class:`FlatTariff` or
    :class:`TOUTariff` for a complete rate structure.

    Parameters
    ----------
    rate_per_kw_month : float
        Charge in $/kW applied to the monthly peak demand.
    """

    rate_per_kw_month: float = 15.0

    def __post_init__(self) -> None:
        if self.rate_per_kw_month < 0:
            raise ValueError(
                f"rate_per_kw_month must be >= 0, got {self.rate_per_kw_month}"
            )
        # Track monthly peaks (index 0 = January, ..., 11 = December).
        self._monthly_peaks: List[float] = [0.0] * 12

    def buy_price(self, hour: int, month: int) -> float:  # noqa: D401
        """Demand charges are not per-kWh; return 0.0."""
        return 0.0

    def sell_price(self, hour: int, month: int) -> float:  # noqa: D401
        return 0.0

    def record_demand(self, power_kw: float, month: int) -> None:
        """Update the monthly peak if *power_kw* exceeds the current record.

        Parameters
        ----------
        power_kw : float
            Instantaneous import power (kW).
        month : int
            Month of year, 1 -- 12.
        """
        idx = month - 1
        if power_kw > self._monthly_peaks[idx]:
            self._monthly_peaks[idx] = power_kw

    def monthly_charge(self, month: int) -> float:
        """Calculate the demand charge for a given month.

        Parameters
        ----------
        month : int
            Month of year, 1 -- 12.

        Returns
        -------
        float
            Demand charge ($).
        """
        return self._monthly_peaks[month - 1] * self.rate_per_kw_month

    def total_annual_charge(self) -> float:
        """Sum of demand charges across all twelve months ($)."""
        return sum(
            peak * self.rate_per_kw_month for peak in self._monthly_peaks
        )

    def reset(self) -> None:
        """Clear all recorded monthly peaks."""
        self._monthly_peaks = [0.0] * 12
