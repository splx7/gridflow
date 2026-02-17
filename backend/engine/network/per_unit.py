"""Per-unit system conversions per IEEE 399 (Brown Book).

Base quantities:
  S_base (MVA) — system-wide, typically 1 MVA or 100 MVA
  V_base (kV)  — per voltage zone (changes at transformers)
  Z_base = V_base² / S_base  (Ω)
  I_base = S_base / (√3 × V_base)  (kA)
"""

from __future__ import annotations

import math


def z_base(v_base_kv: float, s_base_mva: float) -> float:
    """Base impedance in ohms: Z_base = V²/S."""
    return (v_base_kv ** 2) / s_base_mva


def i_base(v_base_kv: float, s_base_mva: float) -> float:
    """Base current in kA: I_base = S / (√3·V)."""
    return s_base_mva / (math.sqrt(3) * v_base_kv)


def ohm_to_pu(z_ohm: complex, v_base_kv: float, s_base_mva: float) -> complex:
    """Convert impedance from ohms to per-unit."""
    zb = z_base(v_base_kv, s_base_mva)
    return z_ohm / zb


def pu_to_ohm(z_pu: complex, v_base_kv: float, s_base_mva: float) -> complex:
    """Convert impedance from per-unit to ohms."""
    zb = z_base(v_base_kv, s_base_mva)
    return z_pu * zb


def transformer_z_pu(
    impedance_pct: float,
    rating_kva: float,
    s_base_mva: float,
    x_r_ratio: float = 10.0,
) -> complex:
    """Convert transformer nameplate impedance to system per-unit.

    impedance_pct: transformer nameplate impedance (e.g. 6.0 for 6%)
    rating_kva: transformer rating in kVA
    s_base_mva: system base MVA
    x_r_ratio: X/R ratio (default 10)
    """
    z_pu_on_tx_base = impedance_pct / 100.0
    # Rebase to system base: Z_pu_sys = Z_pu_tx × (S_base / S_tx)
    z_pu = z_pu_on_tx_base * (s_base_mva / (rating_kva / 1000.0))
    # Split into R + jX using X/R ratio
    x_pu = z_pu * x_r_ratio / math.sqrt(1 + x_r_ratio ** 2)
    r_pu = x_pu / x_r_ratio
    return complex(r_pu, x_pu)


def cable_z_pu(
    r_ohm_per_km: float,
    x_ohm_per_km: float,
    length_km: float,
    v_base_kv: float,
    s_base_mva: float,
) -> complex:
    """Convert cable impedance to per-unit.

    r_ohm_per_km: resistance per km
    x_ohm_per_km: reactance per km
    length_km: cable length in km
    """
    z_ohm = complex(r_ohm_per_km * length_km, x_ohm_per_km * length_km)
    return ohm_to_pu(z_ohm, v_base_kv, s_base_mva)


def inverter_z_pu(efficiency: float, rating_kw: float, s_base_mva: float) -> complex:
    """Inverter efficiency-loss model as per-unit impedance.

    r_pu models conduction/switching losses, x_pu small for solver stability.
    """
    rating_mva = rating_kw / 1000.0
    if rating_mva <= 0:
        return complex(0.01, 0.001)
    loss_fraction = max(1 - efficiency, 0.001)
    r_pu = loss_fraction * (s_base_mva / rating_mva)
    x_pu = 0.001 * (s_base_mva / rating_mva)
    return complex(r_pu, x_pu)


def power_to_pu(p_kw: float, q_kvar: float, s_base_mva: float) -> complex:
    """Convert power (kW, kvar) to per-unit complex power S = P + jQ."""
    return complex(p_kw / 1000.0, q_kvar / 1000.0) / s_base_mva


def pf_to_q(p_kw: float, power_factor: float) -> float:
    """Calculate reactive power kvar from active power kW and power factor."""
    if power_factor >= 1.0:
        return 0.0
    return p_kw * math.sqrt(1.0 - power_factor ** 2) / power_factor
