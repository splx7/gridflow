from fastapi import APIRouter, Query

from engine.network.cable_library import get_cable_library, filter_cables
from engine.network.transformer_model import get_transformer_library

router = APIRouter()


@router.get(
    "/cable-library",
    summary="List cables",
    description="Return the built-in cable library with optional filtering by voltage class, material, or minimum ampacity.",
)
async def list_cables(
    voltage_class: str | None = Query(default=None, pattern="^(lv|mv)$"),
    material: str | None = Query(default=None, pattern="^(Cu|Al)$"),
    min_ampacity: float | None = Query(default=None, ge=0),
):
    if voltage_class or material or min_ampacity is not None:
        cables = filter_cables(voltage_class, material, min_ampacity)
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
            for c in cables
        ]
    return get_cable_library()


@router.get(
    "/transformer-library",
    summary="List transformers",
    description="Return the built-in transformer library with standard ratings and impedance data.",
)
async def list_transformers():
    return get_transformer_library()
