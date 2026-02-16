"""IEC 60228 standard cable impedance library.

Provides typical cable parameters for common sizes used in
low-voltage (0.4kV) and medium-voltage (11kV, 33kV) systems.

Each entry provides:
  - r_ohm_per_km: AC resistance at 90°C
  - x_ohm_per_km: reactance
  - ampacity_a: continuous current rating (in air, 40°C ambient)
  - material: Cu or Al
  - voltage_class: "lv" (≤1kV), "mv" (1-36kV)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CableSpec:
    """Standard cable specification."""
    name: str
    size_mm2: float
    cores: int
    material: str  # Cu, Al
    voltage_class: str  # lv, mv
    insulation: str  # XLPE, PVC
    r_ohm_per_km: float
    x_ohm_per_km: float
    ampacity_a: float
    max_voltage_kv: float


# IEC standard cable library
CABLE_LIBRARY: list[CableSpec] = [
    # Low Voltage (0.6/1kV) Copper XLPE
    CableSpec("Cu XLPE 4×16mm²", 16, 4, "Cu", "lv", "XLPE", 1.150, 0.080, 91, 1.0),
    CableSpec("Cu XLPE 4×25mm²", 25, 4, "Cu", "lv", "XLPE", 0.727, 0.078, 116, 1.0),
    CableSpec("Cu XLPE 4×35mm²", 35, 4, "Cu", "lv", "XLPE", 0.524, 0.076, 140, 1.0),
    CableSpec("Cu XLPE 4×50mm²", 50, 4, "Cu", "lv", "XLPE", 0.387, 0.074, 167, 1.0),
    CableSpec("Cu XLPE 4×70mm²", 70, 4, "Cu", "lv", "XLPE", 0.268, 0.073, 207, 1.0),
    CableSpec("Cu XLPE 4×95mm²", 95, 4, "Cu", "lv", "XLPE", 0.193, 0.072, 250, 1.0),
    CableSpec("Cu XLPE 4×120mm²", 120, 4, "Cu", "lv", "XLPE", 0.153, 0.071, 286, 1.0),
    CableSpec("Cu XLPE 4×150mm²", 150, 4, "Cu", "lv", "XLPE", 0.124, 0.070, 324, 1.0),
    CableSpec("Cu XLPE 4×185mm²", 185, 4, "Cu", "lv", "XLPE", 0.099, 0.070, 368, 1.0),
    CableSpec("Cu XLPE 4×240mm²", 240, 4, "Cu", "lv", "XLPE", 0.075, 0.069, 430, 1.0),
    CableSpec("Cu XLPE 4×300mm²", 300, 4, "Cu", "lv", "XLPE", 0.060, 0.068, 490, 1.0),

    # Low Voltage Aluminium XLPE
    CableSpec("Al XLPE 4×50mm²", 50, 4, "Al", "lv", "XLPE", 0.641, 0.074, 127, 1.0),
    CableSpec("Al XLPE 4×70mm²", 70, 4, "Al", "lv", "XLPE", 0.443, 0.073, 158, 1.0),
    CableSpec("Al XLPE 4×95mm²", 95, 4, "Al", "lv", "XLPE", 0.320, 0.072, 192, 1.0),
    CableSpec("Al XLPE 4×120mm²", 120, 4, "Al", "lv", "XLPE", 0.253, 0.071, 220, 1.0),
    CableSpec("Al XLPE 4×150mm²", 150, 4, "Al", "lv", "XLPE", 0.206, 0.070, 249, 1.0),
    CableSpec("Al XLPE 4×185mm²", 185, 4, "Al", "lv", "XLPE", 0.164, 0.070, 284, 1.0),
    CableSpec("Al XLPE 4×240mm²", 240, 4, "Al", "lv", "XLPE", 0.125, 0.069, 333, 1.0),
    CableSpec("Al XLPE 4×300mm²", 300, 4, "Al", "lv", "XLPE", 0.100, 0.068, 380, 1.0),

    # Medium Voltage (8.7/15kV) Copper XLPE — single core
    CableSpec("Cu XLPE 1×50mm² 11kV", 50, 1, "Cu", "mv", "XLPE", 0.387, 0.130, 180, 15.0),
    CableSpec("Cu XLPE 1×95mm² 11kV", 95, 1, "Cu", "mv", "XLPE", 0.193, 0.115, 275, 15.0),
    CableSpec("Cu XLPE 1×120mm² 11kV", 120, 1, "Cu", "mv", "XLPE", 0.153, 0.110, 315, 15.0),
    CableSpec("Cu XLPE 1×150mm² 11kV", 150, 1, "Cu", "mv", "XLPE", 0.124, 0.107, 355, 15.0),
    CableSpec("Cu XLPE 1×185mm² 11kV", 185, 1, "Cu", "mv", "XLPE", 0.099, 0.104, 405, 15.0),
    CableSpec("Cu XLPE 1×240mm² 11kV", 240, 1, "Cu", "mv", "XLPE", 0.075, 0.100, 475, 15.0),
    CableSpec("Cu XLPE 1×300mm² 11kV", 300, 1, "Cu", "mv", "XLPE", 0.060, 0.097, 540, 15.0),

    # Medium Voltage Aluminium XLPE
    CableSpec("Al XLPE 1×120mm² 11kV", 120, 1, "Al", "mv", "XLPE", 0.253, 0.110, 240, 15.0),
    CableSpec("Al XLPE 1×185mm² 11kV", 185, 1, "Al", "mv", "XLPE", 0.164, 0.104, 310, 15.0),
    CableSpec("Al XLPE 1×240mm² 11kV", 240, 1, "Al", "mv", "XLPE", 0.125, 0.100, 365, 15.0),
    CableSpec("Al XLPE 1×300mm² 11kV", 300, 1, "Al", "mv", "XLPE", 0.100, 0.097, 415, 15.0),
]


def get_cable_library() -> list[dict]:
    """Return cable library as list of dicts for API response."""
    return [
        {
            "name": c.name,
            "size_mm2": c.size_mm2,
            "cores": c.cores,
            "material": c.material,
            "voltage_class": c.voltage_class,
            "insulation": c.insulation,
            "r_ohm_per_km": c.r_ohm_per_km,
            "x_ohm_per_km": c.x_ohm_per_km,
            "ampacity_a": c.ampacity_a,
            "max_voltage_kv": c.max_voltage_kv,
        }
        for c in CABLE_LIBRARY
    ]


def find_cable(name: str) -> CableSpec | None:
    """Find a cable by name."""
    for c in CABLE_LIBRARY:
        if c.name == name:
            return c
    return None


def filter_cables(
    voltage_class: str | None = None,
    material: str | None = None,
    min_ampacity: float | None = None,
) -> list[CableSpec]:
    """Filter cables by criteria."""
    result = CABLE_LIBRARY
    if voltage_class:
        result = [c for c in result if c.voltage_class == voltage_class]
    if material:
        result = [c for c in result if c.material == material]
    if min_ampacity is not None:
        result = [c for c in result if c.ampacity_a >= min_ampacity]
    return result
