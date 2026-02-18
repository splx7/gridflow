"""Grid Code Compliance Profiles.

Configurable voltage, thermal, and fault-level limits per standard.
Built-in profiles for IEC default, Fiji Grid Code, IEEE 1547, and custom.

Each profile specifies:
- Voltage limits (normal and contingency)
- Thermal loading limit (% of rating)
- Frequency limits
- Fault-level requirements
- Power factor limits
- Reconnection requirements (for DER)

These profiles are used by the contingency analysis and network advisor
to determine pass/fail criteria for voltage and thermal violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoltageLimits:
    """Voltage limits in per-unit."""
    normal_min: float = 0.95
    normal_max: float = 1.05
    contingency_min: float = 0.90
    contingency_max: float = 1.10

    def check_normal(self, v_pu: float) -> str | None:
        """Return violation type or None if within limits."""
        if v_pu < self.normal_min:
            return "low"
        if v_pu > self.normal_max:
            return "high"
        return None

    def check_contingency(self, v_pu: float) -> str | None:
        """Return violation type or None if within contingency limits."""
        if v_pu < self.contingency_min:
            return "low"
        if v_pu > self.contingency_max:
            return "high"
        return None


@dataclass
class FrequencyLimits:
    """Frequency limits in Hz."""
    nominal_hz: float = 50.0
    normal_min_hz: float = 49.5
    normal_max_hz: float = 50.5
    contingency_min_hz: float = 47.5
    contingency_max_hz: float = 52.0


@dataclass
class FaultLevelLimits:
    """Fault level requirements."""
    min_sc_ratio: float = 3.0   # Minimum short-circuit ratio (Ssc/Sgen)
    max_fault_ka: float = 50.0  # Maximum fault current (kA) for switchgear


@dataclass
class PowerFactorLimits:
    """Power factor requirements for DER interconnection."""
    min_pf: float = 0.90
    leading_allowed: bool = True
    lagging_allowed: bool = True


@dataclass
class ReconnectionRequirements:
    """DER reconnection after disturbance."""
    voltage_return_min: float = 0.90   # V must exceed this before reconnect
    voltage_return_max: float = 1.10
    frequency_return_min: float = 49.5
    frequency_return_max: float = 50.5
    intentional_delay_s: float = 300.0  # 5 minutes default


@dataclass
class GridCodeProfile:
    """Complete grid code compliance profile.

    Attributes:
        name: Human-readable profile name (e.g. "IEC Default")
        standard: Standard reference (e.g. "IEC 61727")
        voltage: Voltage limits for normal and contingency operation
        thermal_limit_pct: Maximum branch loading as % of thermal rating
        frequency: Frequency limits
        fault_level: Fault level requirements
        power_factor: Power factor limits for DER
        reconnection: Reconnection requirements after disturbance
        max_voltage_unbalance_pct: Maximum voltage unbalance (%)
        max_thd_pct: Maximum total harmonic distortion (%)
        metadata: Additional standard-specific data
    """
    name: str
    standard: str
    voltage: VoltageLimits = field(default_factory=VoltageLimits)
    thermal_limit_pct: float = 100.0
    frequency: FrequencyLimits = field(default_factory=FrequencyLimits)
    fault_level: FaultLevelLimits = field(default_factory=FaultLevelLimits)
    power_factor: PowerFactorLimits = field(default_factory=PowerFactorLimits)
    reconnection: ReconnectionRequirements = field(default_factory=ReconnectionRequirements)
    max_voltage_unbalance_pct: float = 2.0
    max_thd_pct: float = 5.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to a JSON-compatible dict."""
        return {
            "name": self.name,
            "standard": self.standard,
            "voltage_limits": {
                "normal": [self.voltage.normal_min, self.voltage.normal_max],
                "contingency": [self.voltage.contingency_min, self.voltage.contingency_max],
            },
            "thermal_limit_pct": self.thermal_limit_pct,
            "frequency_limits": {
                "nominal_hz": self.frequency.nominal_hz,
                "normal": [self.frequency.normal_min_hz, self.frequency.normal_max_hz],
                "contingency": [self.frequency.contingency_min_hz, self.frequency.contingency_max_hz],
            },
            "fault_level": {
                "min_sc_ratio": self.fault_level.min_sc_ratio,
                "max_fault_ka": self.fault_level.max_fault_ka,
            },
            "power_factor": {
                "min_pf": self.power_factor.min_pf,
                "leading_allowed": self.power_factor.leading_allowed,
                "lagging_allowed": self.power_factor.lagging_allowed,
            },
            "reconnection": {
                "voltage_return": [self.reconnection.voltage_return_min, self.reconnection.voltage_return_max],
                "frequency_return": [self.reconnection.frequency_return_min, self.reconnection.frequency_return_max],
                "intentional_delay_s": self.reconnection.intentional_delay_s,
            },
            "max_voltage_unbalance_pct": self.max_voltage_unbalance_pct,
            "max_thd_pct": self.max_thd_pct,
            "metadata": self.metadata,
        }


# ======================================================================
# Built-in profiles
# ======================================================================

IEC_DEFAULT = GridCodeProfile(
    name="IEC Default",
    standard="IEC 61727 / IEC 62116",
    voltage=VoltageLimits(
        normal_min=0.95, normal_max=1.05,
        contingency_min=0.90, contingency_max=1.10,
    ),
    thermal_limit_pct=100.0,
    frequency=FrequencyLimits(
        nominal_hz=50.0,
        normal_min_hz=49.5, normal_max_hz=50.5,
        contingency_min_hz=47.5, contingency_max_hz=52.0,
    ),
    fault_level=FaultLevelLimits(min_sc_ratio=3.0, max_fault_ka=50.0),
    power_factor=PowerFactorLimits(min_pf=0.90),
    reconnection=ReconnectionRequirements(intentional_delay_s=300.0),
    max_voltage_unbalance_pct=2.0,
    max_thd_pct=5.0,
)

FIJI_GRID_CODE = GridCodeProfile(
    name="Fiji Grid Code",
    standard="Fiji Electricity Authority Grid Code 2019",
    voltage=VoltageLimits(
        normal_min=0.94, normal_max=1.06,
        contingency_min=0.90, contingency_max=1.10,
    ),
    thermal_limit_pct=90.0,  # More conservative
    frequency=FrequencyLimits(
        nominal_hz=50.0,
        normal_min_hz=49.0, normal_max_hz=51.0,
        contingency_min_hz=47.0, contingency_max_hz=53.0,
    ),
    fault_level=FaultLevelLimits(min_sc_ratio=3.0, max_fault_ka=31.5),
    power_factor=PowerFactorLimits(min_pf=0.85, leading_allowed=True, lagging_allowed=True),
    reconnection=ReconnectionRequirements(
        voltage_return_min=0.90, voltage_return_max=1.10,
        frequency_return_min=49.5, frequency_return_max=50.5,
        intentional_delay_s=60.0,  # 1 minute for Fiji
    ),
    max_voltage_unbalance_pct=2.0,
    max_thd_pct=5.0,
    metadata={
        "region": "Pacific Islands",
        "authority": "Fiji Electricity Authority",
        "notes": "Based on FEA Grid Code for embedded generation",
    },
)

IEEE_1547 = GridCodeProfile(
    name="IEEE 1547",
    standard="IEEE 1547-2018 (Interconnection of DER)",
    voltage=VoltageLimits(
        normal_min=0.95, normal_max=1.05,
        contingency_min=0.88, contingency_max=1.10,
    ),
    thermal_limit_pct=100.0,
    frequency=FrequencyLimits(
        nominal_hz=60.0,  # IEEE 1547 is 60 Hz
        normal_min_hz=59.5, normal_max_hz=60.5,
        contingency_min_hz=57.0, contingency_max_hz=61.8,
    ),
    fault_level=FaultLevelLimits(min_sc_ratio=2.0, max_fault_ka=65.0),
    power_factor=PowerFactorLimits(min_pf=0.85, leading_allowed=True, lagging_allowed=True),
    reconnection=ReconnectionRequirements(
        voltage_return_min=0.917, voltage_return_max=1.05,
        frequency_return_min=59.3, frequency_return_max=60.5,
        intentional_delay_s=300.0,
    ),
    max_voltage_unbalance_pct=3.0,
    max_thd_pct=5.0,
    metadata={
        "region": "North America",
        "categories": ["Category I", "Category II", "Category III"],
        "notes": "IEEE 1547-2018 with amendments. Category II assumed.",
    },
)

# Profile registry
PROFILES: dict[str, GridCodeProfile] = {
    "iec_default": IEC_DEFAULT,
    "fiji": FIJI_GRID_CODE,
    "ieee_1547": IEEE_1547,
}


def get_profile(name: str) -> GridCodeProfile:
    """Get a built-in grid code profile by name.

    Args:
        name: Profile key (iec_default, fiji, ieee_1547)

    Returns:
        GridCodeProfile instance

    Raises:
        KeyError if profile name not found
    """
    if name not in PROFILES:
        available = ", ".join(sorted(PROFILES.keys()))
        raise KeyError(f"Unknown grid code profile '{name}'. Available: {available}")
    return PROFILES[name]


def list_profiles() -> list[dict[str, Any]]:
    """List all available grid code profiles with summary info."""
    return [
        {
            "key": key,
            "name": profile.name,
            "standard": profile.standard,
            "voltage_normal": [profile.voltage.normal_min, profile.voltage.normal_max],
            "thermal_limit_pct": profile.thermal_limit_pct,
            "frequency_nominal_hz": profile.frequency.nominal_hz,
        }
        for key, profile in PROFILES.items()
    ]


def build_custom_profile(config: dict[str, Any]) -> GridCodeProfile:
    """Build a custom grid code profile from a configuration dict.

    Args:
        config: Dictionary with optional keys:
            name, standard, voltage_limits, thermal_limit_pct,
            frequency_limits, fault_level, power_factor, reconnection,
            max_voltage_unbalance_pct, max_thd_pct

    Returns:
        GridCodeProfile with custom settings (IEC defaults for unspecified fields)
    """
    vl = config.get("voltage_limits", {})
    normal = vl.get("normal", [0.95, 1.05])
    contingency = vl.get("contingency", [0.90, 1.10])

    fl = config.get("frequency_limits", {})
    freq_normal = fl.get("normal", [49.5, 50.5])
    freq_contingency = fl.get("contingency", [47.5, 52.0])

    fault = config.get("fault_level", {})
    pf = config.get("power_factor", {})
    recon = config.get("reconnection", {})
    recon_v = recon.get("voltage_return", [0.90, 1.10])
    recon_f = recon.get("frequency_return", [49.5, 50.5])

    return GridCodeProfile(
        name=config.get("name", "Custom"),
        standard=config.get("standard", "Custom Standard"),
        voltage=VoltageLimits(
            normal_min=normal[0], normal_max=normal[1],
            contingency_min=contingency[0], contingency_max=contingency[1],
        ),
        thermal_limit_pct=config.get("thermal_limit_pct", 100.0),
        frequency=FrequencyLimits(
            nominal_hz=fl.get("nominal_hz", 50.0),
            normal_min_hz=freq_normal[0], normal_max_hz=freq_normal[1],
            contingency_min_hz=freq_contingency[0], contingency_max_hz=freq_contingency[1],
        ),
        fault_level=FaultLevelLimits(
            min_sc_ratio=fault.get("min_sc_ratio", 3.0),
            max_fault_ka=fault.get("max_fault_ka", 50.0),
        ),
        power_factor=PowerFactorLimits(
            min_pf=pf.get("min_pf", 0.90),
            leading_allowed=pf.get("leading_allowed", True),
            lagging_allowed=pf.get("lagging_allowed", True),
        ),
        reconnection=ReconnectionRequirements(
            voltage_return_min=recon_v[0],
            voltage_return_max=recon_v[1],
            frequency_return_min=recon_f[0],
            frequency_return_max=recon_f[1],
            intentional_delay_s=recon.get("intentional_delay_s", 300.0),
        ),
        max_voltage_unbalance_pct=config.get("max_voltage_unbalance_pct", 2.0),
        max_thd_pct=config.get("max_thd_pct", 5.0),
        metadata=config.get("metadata", {}),
    )
