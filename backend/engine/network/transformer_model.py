"""Transformer equivalent circuit model.

Provides standard transformer data for common distribution transformer sizes
and conversion to per-unit impedance for Y-bus inclusion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TransformerSpec:
    """Standard transformer specification."""
    name: str
    rating_kva: float
    hv_kv: float
    lv_kv: float
    impedance_pct: float
    x_r_ratio: float
    vector_group: str  # Dyn11, YNyn0, etc.
    no_load_loss_kw: float
    load_loss_kw: float


# Common distribution transformer library
TRANSFORMER_LIBRARY: list[TransformerSpec] = [
    # Oil-immersed distribution transformers (IEC 60076)
    TransformerSpec("100 kVA 11/0.4kV", 100, 11.0, 0.4, 4.0, 6.0, "Dyn11", 0.26, 1.75),
    TransformerSpec("160 kVA 11/0.4kV", 160, 11.0, 0.4, 4.0, 6.5, "Dyn11", 0.38, 2.35),
    TransformerSpec("250 kVA 11/0.4kV", 250, 11.0, 0.4, 4.0, 7.0, "Dyn11", 0.53, 3.25),
    TransformerSpec("315 kVA 11/0.4kV", 315, 11.0, 0.4, 4.0, 7.5, "Dyn11", 0.63, 3.90),
    TransformerSpec("400 kVA 11/0.4kV", 400, 11.0, 0.4, 4.0, 7.5, "Dyn11", 0.75, 4.60),
    TransformerSpec("500 kVA 11/0.4kV", 500, 11.0, 0.4, 4.0, 8.0, "Dyn11", 0.88, 5.50),
    TransformerSpec("630 kVA 11/0.4kV", 630, 11.0, 0.4, 4.5, 8.5, "Dyn11", 1.04, 6.50),
    TransformerSpec("800 kVA 11/0.4kV", 800, 11.0, 0.4, 5.0, 9.0, "Dyn11", 1.25, 7.80),
    TransformerSpec("1000 kVA 11/0.4kV", 1000, 11.0, 0.4, 5.0, 9.5, "Dyn11", 1.50, 9.50),
    TransformerSpec("1250 kVA 11/0.4kV", 1250, 11.0, 0.4, 5.5, 10.0, "Dyn11", 1.80, 11.50),
    TransformerSpec("1500 kVA 11/0.4kV", 1500, 11.0, 0.4, 6.0, 10.0, "Dyn11", 2.10, 13.50),
    TransformerSpec("2000 kVA 11/0.4kV", 2000, 11.0, 0.4, 6.0, 10.5, "Dyn11", 2.70, 17.00),
    TransformerSpec("2500 kVA 11/0.4kV", 2500, 11.0, 0.4, 6.0, 11.0, "Dyn11", 3.20, 20.00),

    # 33kV transformers
    TransformerSpec("1000 kVA 33/11kV", 1000, 33.0, 11.0, 7.0, 10.0, "YNyn0", 1.80, 10.50),
    TransformerSpec("2500 kVA 33/11kV", 2500, 33.0, 11.0, 7.0, 12.0, "YNyn0", 3.50, 22.00),
    TransformerSpec("5000 kVA 33/11kV", 5000, 33.0, 11.0, 8.0, 14.0, "YNyn0", 5.50, 38.00),
]


def get_transformer_library() -> list[dict]:
    """Return transformer library as list of dicts for API response."""
    return [
        {
            "name": t.name,
            "rating_kva": t.rating_kva,
            "hv_kv": t.hv_kv,
            "lv_kv": t.lv_kv,
            "impedance_pct": t.impedance_pct,
            "x_r_ratio": t.x_r_ratio,
            "vector_group": t.vector_group,
            "no_load_loss_kw": t.no_load_loss_kw,
            "load_loss_kw": t.load_loss_kw,
        }
        for t in TRANSFORMER_LIBRARY
    ]


def find_transformer(name: str) -> TransformerSpec | None:
    """Find transformer by name."""
    for t in TRANSFORMER_LIBRARY:
        if t.name == name:
            return t
    return None
