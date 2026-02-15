"""TMY (Typical Meteorological Year) data parsing utilities."""

import csv
import io
from dataclasses import dataclass

import numpy as np


@dataclass
class TMYData:
    """Container for parsed TMY weather data (8760 hourly values)."""

    ghi: np.ndarray  # Global Horizontal Irradiance (W/m²)
    dni: np.ndarray  # Direct Normal Irradiance (W/m²)
    dhi: np.ndarray  # Diffuse Horizontal Irradiance (W/m²)
    temperature: np.ndarray  # Ambient temperature (°C)
    wind_speed: np.ndarray  # Wind speed at 10m (m/s)
    pressure: np.ndarray | None = None  # Atmospheric pressure (Pa)
    relative_humidity: np.ndarray | None = None  # Relative humidity (%)

    def validate(self) -> None:
        """Validate all arrays have 8760 elements."""
        for name in ("ghi", "dni", "dhi", "temperature", "wind_speed"):
            arr = getattr(self, name)
            if len(arr) != 8760:
                raise ValueError(f"{name} has {len(arr)} values, expected 8760")


def parse_pvgis_csv(csv_text: str) -> TMYData:
    """Parse PVGIS TMY CSV output into TMYData.

    PVGIS CSV has header metadata lines before the actual data table.
    Data columns: time(UTC), T2m, RH, G(h), Gb(n), Gd(h), IR(h), WS10m, WD10m, SP
    """
    lines = csv_text.strip().split("\n")

    # Find the data header line
    data_start = 0
    for i, line in enumerate(lines):
        if "T2m" in line and ("G(h)" in line or "Gb(n)" in line):
            data_start = i
            break

    if data_start == 0:
        # Try alternative: look for first line with enough commas
        for i, line in enumerate(lines):
            if line.count(",") >= 5 and not line.startswith("#"):
                data_start = i
                break

    reader = csv.DictReader(lines[data_start:])

    ghi, dni, dhi, temp, wind = [], [], [], [], []
    pressure, humidity = [], []

    for row in reader:
        if not row:
            continue
        try:
            ghi.append(float(row.get("G(h)", row.get("ghi", "0"))))
            dni.append(float(row.get("Gb(n)", row.get("dni", "0"))))
            dhi.append(float(row.get("Gd(h)", row.get("dhi", "0"))))
            temp.append(float(row.get("T2m", row.get("temperature", "20"))))
            wind.append(float(row.get("WS10m", row.get("wind_speed", "3"))))
            if "SP" in row:
                pressure.append(float(row["SP"]))
            if "RH" in row:
                humidity.append(float(row["RH"]))
        except (ValueError, TypeError):
            continue

    n = len(ghi)
    if n < 8760:
        raise ValueError(f"Insufficient data: got {n} records, need 8760")

    data = TMYData(
        ghi=np.array(ghi[:8760], dtype=np.float64),
        dni=np.array(dni[:8760], dtype=np.float64),
        dhi=np.array(dhi[:8760], dtype=np.float64),
        temperature=np.array(temp[:8760], dtype=np.float64),
        wind_speed=np.array(wind[:8760], dtype=np.float64),
        pressure=np.array(pressure[:8760], dtype=np.float64) if len(pressure) >= 8760 else None,
        relative_humidity=(
            np.array(humidity[:8760], dtype=np.float64) if len(humidity) >= 8760 else None
        ),
    )
    data.validate()
    return data


def parse_generic_csv(csv_text: str, column_map: dict[str, str] | None = None) -> TMYData:
    """Parse a generic CSV with configurable column mapping.

    Args:
        csv_text: CSV content as string
        column_map: Optional mapping from standard names to CSV column headers.
            Standard names: ghi, dni, dhi, temperature, wind_speed
    """
    default_map = {
        "ghi": "ghi",
        "dni": "dni",
        "dhi": "dhi",
        "temperature": "temperature",
        "wind_speed": "wind_speed",
    }
    col_map = {**default_map, **(column_map or {})}

    reader = csv.DictReader(io.StringIO(csv_text))
    ghi, dni, dhi, temp, wind = [], [], [], [], []

    for row in reader:
        try:
            ghi.append(float(row[col_map["ghi"]]))
            dni.append(float(row[col_map["dni"]]))
            dhi.append(float(row[col_map["dhi"]]))
            temp.append(float(row[col_map["temperature"]]))
            wind.append(float(row[col_map["wind_speed"]]))
        except (KeyError, ValueError):
            continue

    if len(ghi) < 8760:
        raise ValueError(f"Insufficient data: got {len(ghi)} records, need 8760")

    data = TMYData(
        ghi=np.array(ghi[:8760], dtype=np.float64),
        dni=np.array(dni[:8760], dtype=np.float64),
        dhi=np.array(dhi[:8760], dtype=np.float64),
        temperature=np.array(temp[:8760], dtype=np.float64),
        wind_speed=np.array(wind[:8760], dtype=np.float64),
    )
    data.validate()
    return data
