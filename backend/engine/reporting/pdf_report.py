"""Professional PDF report generation for GridFlow simulation results.

Produces an 8–12 page report suitable for engineering feasibility review,
with detailed charts, tables, and auto-generated narrative.
"""
from io import BytesIO
from datetime import datetime
from typing import Any

import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

CHART_DPI = 150
PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]

# Color palette
C_PRIMARY = "#2563eb"
C_DARK = "#1e40af"
C_GREEN = "#059669"
C_ORANGE = "#ea580c"
C_RED = "#dc2626"
C_YELLOW = "#d97706"
C_PURPLE = "#7c3aed"
C_TEAL = "#0d9488"
C_GRAY = "#6b7280"
C_LIGHT_BG = "#f9fafb"
C_GRID = "#e5e7eb"

CHART_COLORS = [
    "#2563eb",  # Blue  - Solar PV
    "#059669",  # Green - Wind
    "#d97706",  # Yellow - Battery
    "#ea580c",  # Orange - Generator
    "#7c3aed",  # Purple - Grid Import
    "#0d9488",  # Teal
    "#dc2626",  # Red
    "#6b7280",  # Gray
]


# ══════════════════════════════════════════════════════════════════════
# Matplotlib setup
# ══════════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 8,
        "axes.titlesize": 10,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "figure.dpi": CHART_DPI,
    })
    return plt


def _fig_to_buf(fig) -> BytesIO:
    """Save matplotlib figure to BytesIO PNG buffer."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=CHART_DPI, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════
# Chart Helper Functions
# ══════════════════════════════════════════════════════════════════════

def _make_pie_chart(
    labels: list[str],
    values: list[float],
    title: str,
    colors_list: list[str] | None = None,
) -> BytesIO:
    """Pie chart for energy mix or cost breakdown."""
    plt = _init_mpl()
    filtered = [(la, v) for la, v in zip(labels, values) if v > 0]
    if not filtered:
        filtered = [("No Data", 1.0)]
    labs, vals = zip(*filtered)
    clrs = (colors_list or CHART_COLORS)[: len(vals)]

    fig, ax = plt.subplots(figsize=(4.5, 3))
    wedges, texts, autotexts = ax.pie(
        vals, labels=labs, colors=clrs, autopct="%1.1f%%",
        startangle=90, pctdistance=0.8, textprops={"fontsize": 7},
    )
    for t in autotexts:
        t.set_fontsize(6)
    ax.set_title(title, fontsize=10, fontweight="bold")
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_stacked_bar_chart(
    months: list[str],
    series: dict[str, list[float]],
    title: str,
    ylabel: str,
    load_line: list[float] | None = None,
) -> BytesIO:
    """Monthly stacked bar chart with optional load overlay line."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(6, 3))
    x = np.arange(len(months))
    bottom = np.zeros(len(months))
    bar_w = 0.6

    for i, (label, vals) in enumerate(series.items()):
        arr = np.array(vals[: len(months)])
        ax.bar(x, arr, bar_w, bottom=bottom, label=label,
               color=CHART_COLORS[i % len(CHART_COLORS)], alpha=0.85)
        bottom += arr

    if load_line:
        ax.plot(x, load_line[: len(months)], "k-o", linewidth=1.5,
                markersize=3, label="Load", zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=30)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.legend(loc="upper right", fontsize=6)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_area_chart(
    hours_24: np.ndarray,
    series: dict[str, np.ndarray],
    load_line: np.ndarray,
    title: str,
) -> BytesIO:
    """24-hour stacked area chart for dispatch profile."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(6, 3))

    labels = []
    data = []
    clrs = []
    color_idx = 0
    for label, vals in series.items():
        if np.any(vals > 0):
            labels.append(label)
            data.append(vals)
            clrs.append(CHART_COLORS[color_idx % len(CHART_COLORS)])
        color_idx += 1

    if data:
        ax.stackplot(hours_24, *data, labels=labels, colors=clrs, alpha=0.7)
    ax.plot(hours_24, load_line, "k-", linewidth=2, label="Load")

    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Power (kW)")
    ax.set_title(title, fontweight="bold")
    ax.set_xlim(0, 23)
    ax.legend(loc="upper right", fontsize=6)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_horizontal_bar_chart(
    labels: list[str],
    low_vals: list[float],
    high_vals: list[float],
    base_val: float,
    title: str,
    xlabel: str,
) -> BytesIO:
    """Horizontal bar chart for tornado diagram."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(6, max(2, len(labels) * 0.4 + 1)))

    y = np.arange(len(labels))
    left = np.array(low_vals) - base_val
    right = np.array(high_vals) - base_val

    ax.barh(y, left, align="center", color="#2563eb", alpha=0.7, label="Low")
    ax.barh(y, right, align="center", color="#dc2626", alpha=0.7, label="High")
    ax.axvline(0, color="black", linewidth=0.8)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontweight="bold")
    ax.legend(fontsize=6)
    ax.grid(True, alpha=0.3, axis="x")
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_duration_curve(
    values: list[float] | np.ndarray,
    title: str,
    ylabel: str,
) -> BytesIO:
    """Duration curve (sorted descending)."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(5, 2.5))

    sorted_vals = np.sort(np.array(values))[::-1]
    hours = np.arange(1, len(sorted_vals) + 1)

    ax.plot(hours, sorted_vals, color=C_PRIMARY, linewidth=0.8)
    ax.fill_between(hours, sorted_vals, alpha=0.2, color=C_PRIMARY)
    ax.set_xlabel("Hours")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_histogram(
    values: list[float] | np.ndarray,
    title: str,
    xlabel: str,
    bins: int = 20,
) -> BytesIO:
    """Histogram chart."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(5, 2.5))

    ax.hist(values, bins=bins, color=C_PRIMARY, alpha=0.7, edgecolor="white")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Hours")
    ax.set_title(title, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_line_chart(
    x_data: list | np.ndarray,
    series: dict[str, list | np.ndarray],
    title: str,
    xlabel: str,
    ylabel: str,
    hlines: list[tuple[float, str, str]] | None = None,
) -> BytesIO:
    """Multi-series line chart with optional horizontal reference lines."""
    plt = _init_mpl()
    fig, ax = plt.subplots(figsize=(6, 3))

    for i, (label, y) in enumerate(series.items()):
        ax.plot(x_data[: len(y)], y, label=label,
                color=CHART_COLORS[i % len(CHART_COLORS)], linewidth=0.8)

    if hlines:
        for val, color, label in hlines:
            ax.axhline(val, color=color, linestyle="--", linewidth=0.8, label=label)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.legend(fontsize=6, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _fig_to_buf(fig)


def _make_system_block_diagram(components: list[dict]) -> BytesIO | None:
    """System block diagram showing component interconnections via AC bus."""
    if not components:
        return None

    plt = _init_mpl()
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    # ── Identify present component types ──
    has: dict[str, dict] = {}
    for c in components:
        ct = c["component_type"]
        cfg = c.get("config", {})
        if ct == "solar_pv":
            cap = cfg.get("capacity_kwp", cfg.get("capacity_kw", "?"))
            has["pv"] = {"label": f"Solar PV\n{cap} kWp", "cfg": cfg}
        elif ct == "battery":
            cap = cfg.get("capacity_kwh", "?")
            has["battery"] = {"label": f"Battery\n{cap} kWh", "cfg": cfg}
        elif ct == "diesel_generator":
            cap = cfg.get("rated_power_kw", "?")
            has["generator"] = {"label": f"Generator\n{cap} kW", "cfg": cfg}
        elif ct == "grid_connection":
            cap = cfg.get("max_import_kw", "?")
            has["grid"] = {"label": f"Grid\n{cap} kW", "cfg": cfg}
        elif ct == "wind_turbine":
            cap = cfg.get("rated_power_kw", "?")
            has["wind"] = {"label": f"Wind\n{cap} kW", "cfg": cfg}
        elif ct == "inverter":
            cap = cfg.get("rated_power_kw", "?")
            has["inverter"] = {"label": f"Inverter\n{cap} kW", "cfg": cfg}

    # Always show load
    has["load"] = {"label": "Load", "cfg": {}}

    # ── AC Bus bar (horizontal, center) ──
    bus_x0, bus_x1, bus_y = 0.28, 0.72, 0.50
    # Shadow line beneath bus bar
    ax.plot([bus_x0, bus_x1], [bus_y - 0.008, bus_y - 0.008],
            color="#1e3a5f", linewidth=10, solid_capstyle="round",
            alpha=0.15, zorder=4)
    ax.plot([bus_x0, bus_x1], [bus_y, bus_y], color="#2563eb",
            linewidth=8, solid_capstyle="round", zorder=5)
    # AC Bus label on white badge
    ax.text((bus_x0 + bus_x1) / 2, bus_y + 0.045, "AC Bus",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
            color="#2563eb", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="#2563eb", linewidth=0.8, alpha=0.95))

    # ── Component box drawing helper ──
    box_w, box_h = 0.16, 0.10
    color_map = {
        "pv": "#b45309", "wind": "#0891b2", "battery": "#16a34a",
        "generator": "#ea580c", "grid": "#7c3aed", "load": "#4b5563",
        "inverter": "#2563eb",
    }

    def _draw_box(cx: float, cy: float, label: str, key: str):
        clr = color_map.get(key, "#9ca3af")
        x0 = cx - box_w / 2
        y0 = cy - box_h / 2
        # Drop shadow
        shadow = FancyBboxPatch(
            (x0 + 0.005, y0 - 0.005), box_w, box_h,
            boxstyle="round,pad=0.012", facecolor="#1f2937",
            edgecolor="none", alpha=0.18, zorder=5,
        )
        ax.add_patch(shadow)
        # Main box
        box = FancyBboxPatch(
            (x0, y0), box_w, box_h,
            boxstyle="round,pad=0.012", facecolor=clr, edgecolor="#1f2937",
            linewidth=0.9, alpha=0.92, zorder=6,
        )
        ax.add_patch(box)
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=7, fontweight="bold", color="white", zorder=7)

    def _connect(x1: float, y1: float, x2: float, y2: float,
                 bidirectional: bool = False):
        # Thin background line for cleaner look
        ax.plot([x1, x2], [y1, y2], color="#d1d5db", linewidth=3,
                solid_capstyle="round", zorder=3)
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle=("<|-|>" if bidirectional else "-|>"),
            color="#374151", linewidth=1.8, mutation_scale=10, zorder=4,
        )
        ax.add_patch(arrow)

    # ── Place components ──
    # Generation sources (left side)
    gen_sources = []
    if "pv" in has:
        gen_sources.append(("pv", has["pv"]["label"]))
    if "wind" in has:
        gen_sources.append(("wind", has["wind"]["label"]))
    if "generator" in has:
        gen_sources.append(("generator", has["generator"]["label"]))

    if len(gen_sources) == 1:
        positions_left = [0.50]
    elif len(gen_sources) == 2:
        positions_left = [0.68, 0.32]
    else:
        positions_left = [0.75, 0.50, 0.25]

    for i, (key, label) in enumerate(gen_sources):
        cy = positions_left[i]
        cx = 0.10
        _draw_box(cx, cy, label, key)
        _connect(cx + box_w / 2, cy, bus_x0, bus_y)

    # Grid (top — tighter spacing)
    if "grid" in has:
        cx, cy = 0.50, 0.83
        _draw_box(cx, cy, has["grid"]["label"], "grid")
        _connect(cx, cy - box_h / 2, cx, bus_y + 0.025, bidirectional=True)

    # Battery (bottom — tighter spacing)
    if "battery" in has:
        cx, cy = 0.50, 0.17
        _draw_box(cx, cy, has["battery"]["label"], "battery")
        _connect(cx, cy + box_h / 2, cx, bus_y - 0.025, bidirectional=True)

    # Load (right side)
    cx, cy = 0.90, 0.50
    _draw_box(cx, cy, has["load"]["label"], "load")
    _connect(bus_x1, bus_y, cx - box_w / 2, cy)

    fig.tight_layout(pad=0.5)
    return _fig_to_buf(fig)


def _make_sld_diagram(
    buses: list[dict],
    branches: list[dict],
    network_data: dict | None = None,
) -> BytesIO | None:
    """IEEE-style single-line diagram showing buses and branch connections."""
    if not buses:
        return None

    plt = _init_mpl()

    fig, ax = plt.subplots(figsize=(8, max(4, len(buses) * 1.2 + 1)))
    ax.axis("off")
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    # ── Layout: use stored positions or auto-layout vertically ──
    bus_positions: dict[str, tuple[float, float]] = {}
    bus_id_to_name: dict[str, str] = {}
    bus_voltages: dict[str, float] = {}
    bus_types: dict[str, str] = {}

    has_positions = all(
        b.get("x_position") is not None and b.get("y_position") is not None
        for b in buses
    )

    if has_positions:
        xs = [b["x_position"] for b in buses]
        ys = [b["y_position"] for b in buses]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_range = max(x_max - x_min, 1)
        y_range = max(y_max - y_min, 1)
        for b in buses:
            nx = 0.15 + 0.70 * (b["x_position"] - x_min) / x_range
            ny = 0.85 - 0.75 * (b["y_position"] - y_min) / y_range
            bus_positions[b["name"]] = (nx, ny)
            bus_id_to_name[b.get("id", b["name"])] = b["name"]
            bus_voltages[b["name"]] = b.get("nominal_voltage_kv", 0.4)
            bus_types[b["name"]] = b.get("bus_type", "pq")
    else:
        for i, b in enumerate(buses):
            nx = 0.50
            ny = 0.85 - i * (0.75 / max(len(buses) - 1, 1))
            bus_positions[b["name"]] = (nx, ny)
            bus_id_to_name[b.get("id", b["name"])] = b["name"]
            bus_voltages[b["name"]] = b.get("nominal_voltage_kv", 0.4)
            bus_types[b["name"]] = b.get("bus_type", "pq")

    # ── Build branch flow lookup from network_data ──
    flow_lookup: dict[str, dict] = {}
    if network_data:
        for snapshot in network_data.get("branch_flows", []):
            for f in snapshot.get("flows", []):
                name = f.get("name", "")
                existing = flow_lookup.get(name)
                if not existing or f.get("loading_pct", 0) > existing.get(
                    "loading_pct", 0
                ):
                    flow_lookup[name] = f

    # ── Draw buses (thick horizontal lines, color-coded by voltage) ──
    bus_bar_half = 0.14
    for name, (bx, by) in bus_positions.items():
        vkv = bus_voltages.get(name, 0.4)
        bt = bus_types.get(name, "pq")
        # Color-code by voltage level
        bar_color = "#991b1b" if vkv >= 1.0 else "#1e40af"

        ax.plot(
            [bx - bus_bar_half, bx + bus_bar_half], [by, by],
            color=bar_color, linewidth=5, solid_capstyle="butt", zorder=5,
        )

        # Bus name with colored dot for type (right of name)
        ax.text(
            bx, by + 0.05, name,
            ha="center", va="bottom", fontsize=7, fontweight="bold",
            color="#1e3a5f",
        )
        # Type indicator dot
        dot_colors = {"slack": "#dc2626", "pv": "#d97706"}
        if bt in dot_colors:
            # Place dot to the right of the name
            ax.plot(
                bx + bus_bar_half + 0.02, by + 0.06,
                "o", color=dot_colors[bt], markersize=5, zorder=6,
            )
            ax.text(
                bx + bus_bar_half + 0.04, by + 0.06,
                bt.upper(), fontsize=5, color=dot_colors[bt],
                va="center", ha="left", fontweight="bold",
            )

        # Voltage label with more clearance
        ax.text(
            bx, by - 0.05, f"{vkv} kV",
            ha="center", va="top", fontsize=6, color="#6b7280",
        )

        # Ground symbol for slack bus
        if bt == "slack":
            gx = bx - bus_bar_half - 0.02
            gy = by
            for j, hw in enumerate([0.025, 0.017, 0.009]):
                gy_line = gy - 0.012 * (j + 1)
                ax.plot(
                    [gx - hw, gx + hw], [gy_line, gy_line],
                    color="#374151", linewidth=1.2, zorder=5,
                )
            ax.plot(
                [gx, gx], [by, by - 0.012],
                color="#374151", linewidth=1.2, zorder=5,
            )

    # ── Draw branches ──
    for br_idx, br in enumerate(branches):
        from_name = br.get("from_bus", "")
        to_name = br.get("to_bus", "")
        if from_name not in bus_positions or to_name not in bus_positions:
            continue

        fx, fy = bus_positions[from_name]
        tx, ty = bus_positions[to_name]
        br_type = br.get("branch_type", "cable")
        br_name = br.get("name", "")

        mid_x = (fx + tx) / 2
        mid_y = (fy + ty) / 2

        if br_type == "transformer":
            # IEC transformer symbol: two overlapping circles (larger)
            r = 0.035
            offset = r * 0.7
            ax.plot([fx, mid_x], [fy, mid_y + offset], color="#374151",
                    linewidth=1.2, zorder=3)
            ax.plot([mid_x, tx], [mid_y - offset, ty], color="#374151",
                    linewidth=1.2, zorder=3)
            circle1 = plt.Circle((mid_x, mid_y + offset), r,
                                 fill=False, edgecolor="#374151",
                                 linewidth=1.5, zorder=4)
            circle2 = plt.Circle((mid_x, mid_y - offset), r,
                                 fill=False, edgecolor="#374151",
                                 linewidth=1.5, zorder=4)
            ax.add_patch(circle1)
            ax.add_patch(circle2)
        else:
            # Cable/line: dashed to distinguish from transformer
            ax.plot([fx, tx], [fy, ty], color="#374151",
                    linewidth=1.2, linestyle="--", zorder=3)

        # Branch label — alternate sides to prevent overlap
        label_parts = [br_name]
        flow = flow_lookup.get(br_name)
        if flow:
            p_kw = flow.get("power_kw", 0)
            loading = flow.get("loading_pct", 0)
            label_parts.append(f"{p_kw:.0f} kW ({loading:.0f}%)")

        label_text = "\n".join(label_parts)
        # Even-index → right, odd-index → left
        if br_idx % 2 == 0:
            label_offset_x = 0.06
            ha = "left"
        else:
            label_offset_x = -0.06
            ha = "right"
        ax.text(mid_x + label_offset_x, mid_y, label_text, fontsize=5.5,
                color="#6b7280", va="center", ha=ha,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="#e5e7eb", alpha=0.9),
                zorder=6)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout(pad=0.5)
    return _fig_to_buf(fig)


# ══════════════════════════════════════════════════════════════════════
# Canvas Callbacks (header / footer / page numbers)
# ══════════════════════════════════════════════════════════════════════

def _on_first_page(canvas, doc):
    """Cover page: subtle footer only."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor(C_GRAY))
    canvas.drawCentredString(
        PAGE_W / 2, 10 * mm,
        "Generated by GridFlow Power Grid Analysis Platform",
    )
    canvas.restoreState()


def _on_later_pages(canvas, doc):
    """Pages 2+: header line + page number."""
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(colors.HexColor(C_PRIMARY))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - 14 * mm, PAGE_W - MARGIN, PAGE_H - 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor(C_GRAY))
    canvas.drawString(MARGIN, PAGE_H - 12 * mm, "GridFlow Simulation Report")
    # Page number
    canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════
# Styles & Table Helpers
# ══════════════════════════════════════════════════════════════════════

def _get_styles():
    """Return configured paragraph styles."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=26, spaceAfter=6, textColor=colors.HexColor(C_PRIMARY),
    ))
    styles.add(ParagraphStyle(
        "Subtitle", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor(C_DARK), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"],
        fontSize=13, spaceBefore=14, spaceAfter=6,
        textColor=colors.HexColor(C_DARK),
        borderWidth=1, borderColor=colors.HexColor(C_PRIMARY),
        borderPadding=(0, 0, 3, 0),
    ))
    styles.add(ParagraphStyle(
        "SubSection", parent=styles["Heading3"],
        fontSize=10, spaceBefore=8, spaceAfter=4,
        textColor=colors.HexColor(C_GRAY),
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=9, leading=13, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SmallGray", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor(C_GRAY),
    ))
    styles.add(ParagraphStyle(
        "CoverInfo", parent=styles["Normal"],
        fontSize=11, leading=16, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "BulletItem", parent=styles["Normal"],
        fontSize=9, leading=13, leftIndent=12, bulletIndent=0, spaceAfter=2,
    ))
    return styles


def _styled_table(
    data: list[list],
    col_widths: list,
    header_color: str = C_DARK,
    row_bg_alt: str = C_LIGHT_BG,
) -> Table:
    """Create a consistently styled table."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(C_GRID)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor(row_bg_alt)]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _fmt(
    v: float | None, fmt_str: str = ",.0f",
    prefix: str = "", suffix: str = "",
) -> str:
    """Safe number formatting."""
    if v is None:
        return "N/A"
    try:
        return f"{prefix}{v:{fmt_str}}{suffix}"
    except (ValueError, TypeError):
        return "N/A"


# ══════════════════════════════════════════════════════════════════════
# Section 1: Cover Page
# ══════════════════════════════════════════════════════════════════════

def _build_cover(styles, **kw) -> list:
    elems: list = []
    elems.append(Spacer(1, 50 * mm))
    elems.append(Paragraph("GridFlow", styles["ReportTitle"]))
    elems.append(Paragraph("Simulation Report", styles["Subtitle"]))
    elems.append(Spacer(1, 15 * mm))

    info = [
        f"<b>Project:</b> {kw.get('project_name', '')}",
    ]
    desc = kw.get("project_description")
    if desc:
        info.append(f"<b>Description:</b> {str(desc)[:200]}")
    lat, lon = kw.get("project_location", (0, 0))
    info.append(f"<b>Location:</b> {lat:.4f}\u00b0, {lon:.4f}\u00b0")
    info.append(f"<b>Simulation:</b> {kw.get('simulation_name', '')}")
    info.append(
        f"<b>Strategy:</b> "
        f"{kw.get('dispatch_strategy', '').replace('_', ' ').title()}"
    )
    lt = kw.get("lifetime_years", 25)
    dr = kw.get("discount_rate", 0.08)
    info.append(f"<b>Analysis Period:</b> {lt} years @ {dr * 100:.1f}% discount rate")
    info.append(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for line in info:
        elems.append(Paragraph(line, styles["CoverInfo"]))
    elems.append(PageBreak())
    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 2: Executive Summary
# ══════════════════════════════════════════════════════════════════════

def _build_executive_summary(
    styles, economics: dict, summary: dict, discount_rate: float,
) -> list:
    elems: list = []
    elems.append(Paragraph("Executive Summary", styles["SectionHeader"]))

    re_frac = economics.get("renewable_fraction", 0)
    annual_load = summary.get("annual_load_kwh", 0)
    unmet = summary.get("annual_unmet_kwh", 0)
    unmet_pct = (unmet / annual_load * 100) if annual_load > 0 else 0

    # Key metrics table
    irr_val = economics.get("irr")
    data = [
        ["Metric", "Value"],
        ["Net Present Cost (NPC)", _fmt(economics.get("npc"), ",.0f", "$")],
        ["Levelized Cost of Energy",
         _fmt(economics.get("lcoe"), ".4f", "$", "/kWh")],
        ["Internal Rate of Return",
         _fmt(irr_val * 100 if irr_val is not None else None, ".1f", "", "%")],
        ["Simple Payback Period",
         _fmt(economics.get("payback_years"), ".1f", "", " years")],
        ["Renewable Fraction", f"{re_frac * 100:.1f}%"],
        ["\u200bCO\u2082 Emissions",
         _fmt(economics.get("co2_emissions_kg"), ",.0f", "", " kg/yr")],
        ["Peak Load", _fmt(summary.get("peak_load_kw"), ",.1f", "", " kW")],
        ["Annual Energy Served", _fmt(annual_load, ",.0f", "", " kWh")],
        ["Unmet Load", f"{unmet_pct:.2f}% ({_fmt(unmet, ',.0f')} kWh)"],
        ["Curtailed Energy",
         _fmt(summary.get("annual_curtailed_kwh"), ",.0f", "", " kWh")],
    ]

    t = _styled_table(data, [100 * mm, 70 * mm], header_color=C_PRIMARY)
    t.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT")]))
    elems.append(t)
    elems.append(Spacer(1, 6 * mm))

    # Key Findings
    elems.append(Paragraph("Key Findings", styles["SubSection"]))

    irr = economics.get("irr")
    payback = economics.get("payback_years")
    npc = economics.get("npc", 0)

    # Economic
    if irr is not None:
        if irr > discount_rate:
            etxt = (
                f"The system achieves an IRR of {irr * 100:.1f}%, exceeding the "
                f"{discount_rate * 100:.1f}% discount rate, indicating economic "
                f"viability."
            )
        else:
            etxt = (
                f"The system IRR of {irr * 100:.1f}% is below the "
                f"{discount_rate * 100:.1f}% discount rate. Additional revenue "
                f"streams or cost reductions may be needed."
            )
    else:
        etxt = f"The Net Present Cost is ${npc:,.0f} over the analysis period."
    if payback and payback < float("inf"):
        etxt += f" Simple payback is achieved in {payback:.1f} years."
    elems.append(Paragraph(f"<b>Economic Assessment:</b> {etxt}", styles["BodyText2"]))

    # Renewable
    if re_frac >= 0.80:
        rtxt = f"High renewable fraction of {re_frac * 100:.1f}%."
    elif re_frac >= 0.50:
        rtxt = f"Moderate renewable fraction of {re_frac * 100:.1f}%."
    else:
        rtxt = (
            f"Renewable fraction is {re_frac * 100:.1f}%. Increasing RE "
            f"capacity could improve economics."
        )
    co2 = economics.get("co2_emissions_kg", 0)
    if co2 > 0:
        rtxt += f" Annual CO\u2082 emissions are {co2:,.0f} kg."
    elems.append(
        Paragraph(f"<b>Renewable Performance:</b> {rtxt}", styles["BodyText2"])
    )

    # Reliability
    if unmet_pct < 0.1:
        reltxt = "Virtually all load demand is met with negligible unmet energy."
    elif unmet_pct < 1.0:
        reltxt = (
            f"Unmet load is {unmet_pct:.2f}% of annual demand, within "
            f"acceptable limits."
        )
    else:
        reltxt = (
            f"Unmet load is {unmet_pct:.1f}% \u2014 the system may be "
            f"undersized for the load."
        )
    elems.append(Paragraph(f"<b>Reliability:</b> {reltxt}", styles["BodyText2"]))

    # Battery / generator highlights
    parts = []
    bc = summary.get("battery_equiv_cycles")
    if bc is not None:
        parts.append(
            f"Battery: {bc:.0f} equivalent cycles/yr "
            f"({summary.get('battery_throughput_kwh', 0):,.0f} kWh throughput)."
        )
    gh = summary.get("gen_running_hours")
    if gh:
        parts.append(
            f"Generator: {gh:,} hours/yr at "
            f"{summary.get('gen_avg_loading_pct', 0):.0f}% avg loading."
        )
    if parts:
        elems.append(Paragraph(
            f"<b>System Highlights:</b> {' '.join(parts)}",
            styles["BodyText2"],
        ))

    elems.append(PageBreak())
    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 3: System Configuration
# ══════════════════════════════════════════════════════════════════════

def _build_system_config(styles, components: list[dict]) -> list:
    elems: list = []
    elems.append(Paragraph("System Configuration", styles["SectionHeader"]))

    # System block diagram (always shown if components exist)
    try:
        block_buf = _make_system_block_diagram(components)
        if block_buf:
            elems.append(Paragraph("System Block Diagram", styles["SubSection"]))
            elems.append(Image(block_buf, width=170 * mm, height=97 * mm))
            elems.append(Spacer(1, 4 * mm))
    except Exception:
        pass

    type_order = [
        "solar_pv", "battery", "diesel_generator",
        "grid_connection", "inverter", "wind_turbine",
    ]
    grouped: dict[str, list[dict]] = {}
    for c in components:
        grouped.setdefault(c["component_type"], []).append(c)

    for ct in type_order:
        comps = grouped.pop(ct, [])
        if not comps:
            continue
        for comp in comps:
            cfg = comp.get("config", {})
            name = comp.get("name", ct.replace("_", " ").title())
            elems.append(Paragraph(name, styles["SubSection"]))

            rows: list[list[str]] = [["Parameter", "Value"]]

            if ct == "solar_pv":
                cap = cfg.get("capacity_kwp", cfg.get("capacity_kw", "?"))
                rows.append(["Capacity", f"{cap} kWp"])
                if cfg.get("tilt") is not None:
                    rows.append(["Tilt / Azimuth",
                                 f"{cfg.get('tilt', 0)}\u00b0 / "
                                 f"{cfg.get('azimuth', 0)}\u00b0"])
                if cfg.get("derating_factor"):
                    rows.append(["Derating Factor",
                                 f"{cfg['derating_factor'] * 100:.1f}%"])
                if cfg.get("capital_cost_per_kw"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost_per_kw']:,.0f}/kW"])
                elif cfg.get("capital_cost"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost']:,.0f}"])
                if cfg.get("om_cost_per_kw_year"):
                    rows.append(["O&M Cost",
                                 f"${cfg['om_cost_per_kw_year']:,.0f}/kW/yr"])

            elif ct == "battery":
                rows.append(["Energy Capacity",
                             f"{cfg.get('capacity_kwh', '?')} kWh"])
                if cfg.get("max_charge_rate_kw"):
                    rows.append(["Max Charge Rate",
                                 f"{cfg['max_charge_rate_kw']} kW"])
                if cfg.get("max_discharge_rate_kw"):
                    rows.append(["Max Discharge Rate",
                                 f"{cfg['max_discharge_rate_kw']} kW"])
                if cfg.get("round_trip_efficiency"):
                    rows.append(["Round-trip Efficiency",
                                 f"{cfg['round_trip_efficiency'] * 100:.1f}%"])
                if cfg.get("cycle_life"):
                    rows.append(["Cycle Life",
                                 f"{cfg['cycle_life']:,.0f} cycles"])
                if cfg.get("capital_cost_per_kwh"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost_per_kwh']:,.0f}/kWh"])
                elif cfg.get("capital_cost"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost']:,.0f}"])

            elif ct == "diesel_generator":
                rows.append(["Rated Power",
                             f"{cfg.get('rated_power_kw', '?')} kW"])
                if cfg.get("min_load_ratio") is not None:
                    rows.append(["Min Load Ratio",
                                 f"{cfg['min_load_ratio'] * 100:.0f}%"])
                if cfg.get("fuel_price"):
                    rows.append(["Fuel Price",
                                 f"${cfg['fuel_price']:.2f}/L"])
                if cfg.get("capital_cost_per_kw"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost_per_kw']:,.0f}/kW"])
                elif cfg.get("capital_cost"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost']:,.0f}"])

            elif ct == "grid_connection":
                if cfg.get("max_import_kw"):
                    rows.append(["Max Import",
                                 f"{cfg['max_import_kw']} kW"])
                if cfg.get("max_export_kw"):
                    rows.append(["Max Export",
                                 f"{cfg['max_export_kw']} kW"])
                buy = cfg.get("buy_rate", cfg.get("tariff_buy_rate"))
                if buy is not None:
                    rows.append(["Buy Rate", f"${buy:.4f}/kWh"])
                sell = cfg.get("sell_rate", cfg.get("tariff_sell_rate"))
                if sell is not None:
                    rows.append(["Sell Rate", f"${sell:.4f}/kWh"])

            elif ct == "inverter":
                rows.append(["Rated Power",
                             f"{cfg.get('rated_power_kw', '?')} kW"])
                if cfg.get("efficiency"):
                    rows.append(["Efficiency",
                                 f"{cfg['efficiency'] * 100:.1f}%"])
                if cfg.get("mode"):
                    rows.append(["Mode", cfg["mode"]])

            elif ct == "wind_turbine":
                rows.append(["Rated Power",
                             f"{cfg.get('rated_power_kw', '?')} kW"])
                if cfg.get("hub_height"):
                    rows.append(["Hub Height", f"{cfg['hub_height']} m"])
                if cfg.get("capital_cost_per_kw"):
                    rows.append(["Capital Cost",
                                 f"${cfg['capital_cost_per_kw']:,.0f}/kW"])

            if len(rows) > 1:
                elems.append(_styled_table(rows, [85 * mm, 85 * mm]))
                elems.append(Spacer(1, 3 * mm))

    # Remaining unknown types
    for ct, comps in grouped.items():
        for comp in comps:
            cfg = comp.get("config", {})
            name = comp.get("name", ct.replace("_", " ").title())
            elems.append(Paragraph(f"{name} ({ct})", styles["SubSection"]))
            rows = [["Parameter", "Value"]]
            for k, v in list(cfg.items())[:8]:
                rows.append([k.replace("_", " ").title(), str(v)])
            if len(rows) > 1:
                elems.append(_styled_table(rows, [85 * mm, 85 * mm]))

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 4: Energy Balance
# ══════════════════════════════════════════════════════════════════════

def _build_energy_balance(styles, summary: dict) -> list:
    elems: list = []
    elems.append(Paragraph("Energy Balance", styles["SectionHeader"]))

    annual_load = summary.get("annual_load_kwh", 0)

    sources = [
        ("Solar PV", summary.get("annual_pv_kwh", 0)),
        ("Wind", summary.get("annual_wind_kwh", 0)),
        ("Generator", summary.get("annual_gen_kwh", 0)),
        ("Grid Import", summary.get("annual_grid_import_kwh", 0)),
    ]

    data: list[list[str]] = [["Source", "Annual kWh", "% of Load"]]
    for name, val in sources:
        if val > 0:
            pct = (val / annual_load * 100) if annual_load > 0 else 0
            data.append([name, f"{val:,.0f}", f"{pct:.1f}%"])
    data.append(["Total Load", f"{annual_load:,.0f}", "100.0%"])

    unmet = summary.get("annual_unmet_kwh", 0)
    if unmet > 0:
        pct = (unmet / annual_load * 100) if annual_load > 0 else 0
        data.append(["Unmet Load", f"{unmet:,.0f}", f"{pct:.2f}%"])
    curtailed = summary.get("annual_curtailed_kwh", 0)
    if curtailed > 0:
        data.append(["Curtailed Energy", f"{curtailed:,.0f}", "\u2014"])
    export = summary.get("annual_grid_export_kwh", 0)
    if export > 0:
        data.append(["Grid Export", f"{export:,.0f}", "\u2014"])

    t = _styled_table(data, [60 * mm, 55 * mm, 55 * mm], header_color=C_GREEN)
    t.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    elems.append(t)
    elems.append(Spacer(1, 6 * mm))

    # Energy mix pie chart
    pie_labels = [s[0] for s in sources if s[1] > 0]
    pie_values = [s[1] for s in sources if s[1] > 0]
    if pie_values:
        try:
            buf = _make_pie_chart(pie_labels, pie_values, "Energy Supply Mix")
            elems.append(Image(buf, width=140 * mm, height=93 * mm))
        except Exception:
            pass

    elems.append(Spacer(1, 4 * mm))

    # Monthly stacked bar chart
    monthly_series: dict[str, list[float]] = {}
    for key, label in [
        ("monthly_pv", "Solar PV"), ("monthly_wind", "Wind"),
        ("monthly_gen", "Generator"), ("monthly_grid_import", "Grid Import"),
    ]:
        vals = summary.get(key, [])
        if vals and any(v > 0 for v in vals):
            monthly_series[label] = vals

    if monthly_series:
        try:
            buf = _make_stacked_bar_chart(
                MONTH_NAMES, monthly_series,
                "Monthly Energy Production (kWh)", "kWh",
                load_line=summary.get("monthly_load"),
            )
            elems.append(Image(buf, width=170 * mm, height=85 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 5: Dispatch Profile
# ══════════════════════════════════════════════════════════════════════

def _build_dispatch_profile(styles, timeseries: dict) -> list:
    load = timeseries.get("load")
    if not load or len(load) != 8760:
        return []

    elems: list = []
    elems.append(Paragraph("Dispatch Profile", styles["SectionHeader"]))

    load_arr = np.array(load)
    hours_24 = np.arange(24)

    def _ts(key: str) -> np.ndarray:
        arr = timeseries.get(key)
        if arr and len(arr) == 8760:
            return np.array(arr)
        return np.zeros(8760)

    pv = _ts("pv_output")
    wind = _ts("wind_output")
    gen = _ts("generator_output")
    grid_imp = _ts("grid_import")
    batt_power = _ts("battery_power")
    batt_discharge = np.maximum(batt_power, 0)  # positive = discharge

    # Peak day
    daily_load = load_arr.reshape(365, 24).sum(axis=1)
    peak_day = int(np.argmax(daily_load))
    s, e = peak_day * 24, peak_day * 24 + 24

    peak_series: dict[str, np.ndarray] = {}
    if np.any(pv[s:e] > 0):
        peak_series["Solar PV"] = pv[s:e]
    if np.any(wind[s:e] > 0):
        peak_series["Wind"] = wind[s:e]
    if np.any(batt_discharge[s:e] > 0):
        peak_series["Battery"] = batt_discharge[s:e]
    if np.any(gen[s:e] > 0):
        peak_series["Generator"] = gen[s:e]
    if np.any(grid_imp[s:e] > 0):
        peak_series["Grid Import"] = grid_imp[s:e]

    if peak_series:
        try:
            buf = _make_area_chart(
                hours_24, peak_series, load_arr[s:e],
                f"Peak Load Day (Day {peak_day + 1})",
            )
            elems.append(Image(buf, width=170 * mm, height=85 * mm))
        except Exception:
            pass

    elems.append(Spacer(1, 4 * mm))

    # Average day
    avg_load = load_arr.reshape(365, 24).mean(axis=0)
    avg_series: dict[str, np.ndarray] = {}
    if np.any(pv > 0):
        avg_series["Solar PV"] = pv.reshape(365, 24).mean(axis=0)
    if np.any(wind > 0):
        avg_series["Wind"] = wind.reshape(365, 24).mean(axis=0)
    if np.any(batt_discharge > 0):
        avg_series["Battery"] = batt_discharge.reshape(365, 24).mean(axis=0)
    if np.any(gen > 0):
        avg_series["Generator"] = gen.reshape(365, 24).mean(axis=0)
    if np.any(grid_imp > 0):
        avg_series["Grid Import"] = grid_imp.reshape(365, 24).mean(axis=0)

    if avg_series:
        try:
            buf = _make_area_chart(
                hours_24, avg_series, avg_load, "Average Daily Profile",
            )
            elems.append(Image(buf, width=170 * mm, height=85 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 6: Battery Performance (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_battery_performance(
    styles, summary: dict, timeseries: dict, components: list[dict],
) -> list:
    batt_cap = 0.0
    for c in components:
        if c["component_type"] == "battery":
            batt_cap = c.get("config", {}).get("capacity_kwh", 0)
            break

    soc = timeseries.get("battery_soc")
    if not batt_cap or not soc or len(soc) != 8760:
        return []

    elems: list = []
    elems.append(Paragraph("Battery Performance", styles["SectionHeader"]))

    soc_arr = np.array(soc)
    soc_pct = soc_arr / batt_cap * 100 if batt_cap > 0 else soc_arr

    data = [
        ["Parameter", "Value"],
        ["Energy Capacity", f"{batt_cap:,.0f} kWh"],
        ["Annual Throughput",
         _fmt(summary.get("battery_throughput_kwh"), ",.0f", "", " kWh")],
        ["Equivalent Cycles",
         _fmt(summary.get("battery_equiv_cycles"), ",.0f", "", "/yr")],
        ["Average SOC", f"{float(np.mean(soc_pct)):.1f}%"],
        ["Minimum SOC", f"{float(np.min(soc_pct)):.1f}%"],
        ["Hours Below 20% SOC",
         f"{summary.get('battery_hours_below_20pct', 0):,}"],
    ]
    elems.append(_styled_table(data, [85 * mm, 85 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # SOC duration curve
    try:
        buf = _make_duration_curve(
            soc_pct.tolist(), "Battery SOC Duration Curve", "SOC (%)",
        )
        elems.append(Image(buf, width=150 * mm, height=75 * mm))
    except Exception:
        pass

    elems.append(Spacer(1, 4 * mm))

    # Monthly throughput
    batt_power = timeseries.get("battery_power")
    if batt_power and len(batt_power) == 8760:
        bp = np.array(batt_power)
        charge = np.maximum(-bp, 0)
        discharge = np.maximum(bp, 0)

        monthly_charge: list[float] = []
        monthly_discharge: list[float] = []
        offset = 0
        for h in MONTH_HOURS:
            monthly_charge.append(float(charge[offset:offset + h].sum()))
            monthly_discharge.append(float(discharge[offset:offset + h].sum()))
            offset += h

        try:
            buf = _make_stacked_bar_chart(
                MONTH_NAMES,
                {"Charging": monthly_charge, "Discharging": monthly_discharge},
                "Monthly Battery Throughput (kWh)", "kWh",
            )
            elems.append(Image(buf, width=170 * mm, height=80 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 7: Generator Performance (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_generator_performance(
    styles, summary: dict, timeseries: dict, components: list[dict],
) -> list:
    gen_output = timeseries.get("generator_output")
    if not gen_output or len(gen_output) != 8760:
        return []

    gen_arr = np.array(gen_output)
    if float(np.sum(gen_arr)) < 1.0:
        return []

    rated_power = 0.0
    for c in components:
        if c["component_type"] == "diesel_generator":
            rated_power = c.get("config", {}).get("rated_power_kw", 0)
            break

    elems: list = []
    elems.append(Paragraph("Generator Performance", styles["SectionHeader"]))

    running_hours = summary.get("gen_running_hours", 0)
    cf = (running_hours / 8760 * 100) if running_hours > 0 else 0

    data = [
        ["Parameter", "Value"],
        ["Rated Power", f"{rated_power:,.0f} kW"],
        ["Running Hours", f"{running_hours:,}/yr"],
        ["Capacity Factor", f"{cf:.1f}%"],
        ["Starts", f"{summary.get('gen_starts', 0):,}/yr"],
        ["Avg Loading", f"{summary.get('gen_avg_loading_pct', 0):.1f}%"],
        ["Total Fuel",
         _fmt(summary.get("gen_total_fuel_l"), ",.0f", "", " L/yr")],
        ["Fuel Cost",
         _fmt(summary.get("gen_fuel_cost"), ",.0f", "$", "/yr")],
    ]
    elems.append(_styled_table(data, [85 * mm, 85 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Monthly output
    monthly_gen: list[float] = []
    offset = 0
    for h in MONTH_HOURS:
        monthly_gen.append(float(gen_arr[offset:offset + h].sum()))
        offset += h

    try:
        buf = _make_stacked_bar_chart(
            MONTH_NAMES, {"Generator Output": monthly_gen},
            "Monthly Generator Output (kWh)", "kWh",
        )
        elems.append(Image(buf, width=170 * mm, height=80 * mm))
    except Exception:
        pass

    elems.append(Spacer(1, 4 * mm))

    # Loading histogram
    if rated_power > 0:
        running_mask = gen_arr > 0.01
        if np.any(running_mask):
            loading_pct = gen_arr[running_mask] / rated_power * 100
            try:
                buf = _make_histogram(
                    loading_pct.tolist(),
                    "Generator Loading Distribution",
                    "Loading (%)", bins=15,
                )
                elems.append(Image(buf, width=150 * mm, height=75 * mm))
            except Exception:
                pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 8: Grid Interaction (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_grid_interaction(styles, summary: dict, timeseries: dict) -> list:
    grid_import = timeseries.get("grid_import")
    grid_export = timeseries.get("grid_export")

    has_imp = (grid_import and len(grid_import) == 8760
               and sum(grid_import) > 0)
    has_exp = (grid_export and len(grid_export) == 8760
               and sum(grid_export) > 0)
    if not has_imp and not has_exp:
        return []

    elems: list = []
    elems.append(Paragraph("Grid Interaction", styles["SectionHeader"]))

    imp_total = summary.get("annual_grid_import_kwh", 0)
    exp_total = summary.get("annual_grid_export_kwh", 0)

    data = [
        ["Parameter", "Value"],
        ["Annual Import", f"{imp_total:,.0f} kWh"],
        ["Annual Export", f"{exp_total:,.0f} kWh"],
        ["Net Import", f"{imp_total - exp_total:,.0f} kWh"],
        ["Import Cost",
         _fmt(summary.get("grid_import_cost"), ",.0f", "$", "/yr")],
        ["Export Revenue",
         _fmt(summary.get("grid_export_revenue"), ",.0f", "$", "/yr")],
        ["Net Grid Cost",
         _fmt(summary.get("grid_net_cost"), ",.0f", "$", "/yr")],
    ]
    elems.append(_styled_table(data, [85 * mm, 85 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Monthly import/export chart
    monthly_imp = summary.get("monthly_grid_import", [0] * 12)
    monthly_exp = summary.get("monthly_grid_export", [0] * 12)

    try:
        plt = _init_mpl()
        fig, ax = plt.subplots(figsize=(6, 3))
        x = np.arange(12)

        ax.bar(x - 0.15, monthly_imp, 0.3, label="Import",
               color=C_PRIMARY, alpha=0.8)
        ax.bar(x + 0.15, [-v for v in monthly_exp], 0.3, label="Export",
               color=C_GREEN, alpha=0.8)
        ax.axhline(0, color="black", linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels(MONTH_NAMES, rotation=30)
        ax.set_ylabel("kWh")
        ax.set_title("Monthly Grid Import / Export", fontweight="bold")
        ax.legend(fontsize=6)
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()

        buf = _fig_to_buf(fig)
        elems.append(Image(buf, width=170 * mm, height=85 * mm))
    except Exception:
        pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 9: Cost Analysis
# ══════════════════════════════════════════════════════════════════════

def _build_cost_analysis(styles, economics: dict) -> list:
    elems: list = []
    elems.append(Paragraph("Cost Analysis", styles["SectionHeader"]))

    cost_bd = economics.get("cost_breakdown", {})
    npc = economics.get("npc", 0)

    data: list[list[str]] = [["Category", "NPV ($)", "% of NPC"]]
    positive_items: list[tuple[str, float]] = []

    for key, val in cost_bd.items():
        if key.startswith("_") or val == 0:
            continue
        label = key.replace("_", " ").title()
        pct = (abs(val) / abs(npc) * 100) if npc != 0 else 0
        data.append([label, f"${val:,.0f}", f"{pct:.1f}%"])
        if val > 0:
            positive_items.append((label, val))

    if len(data) > 1:
        data.append(["Total NPC", f"${npc:,.0f}", "100.0%"])
        t = _styled_table(data, [70 * mm, 50 * mm, 50 * mm])
        t.setStyle(TableStyle([
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 6 * mm))

    if positive_items:
        try:
            labels, values = zip(*positive_items)
            buf = _make_pie_chart(
                list(labels), list(values), "Cost Breakdown (NPV)",
            )
            elems.append(Image(buf, width=140 * mm, height=93 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 10: Network Analysis (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_network_analysis(
    styles,
    network_data: dict | None,
    ts_bus_voltages: dict | None,
    buses: list[dict] | None = None,
    branches: list[dict] | None = None,
) -> list:
    if not network_data:
        return []

    elems: list = []
    elems.append(Paragraph("Network Analysis", styles["SectionHeader"]))

    # Single-line diagram (conditional on buses/branches existing)
    if buses and branches:
        try:
            sld_buf = _make_sld_diagram(buses, branches, network_data)
            if sld_buf:
                elems.append(
                    Paragraph("Single Line Diagram", styles["SubSection"])
                )
                img_h = max(100, len(buses) * 30 + 25)
                elems.append(Image(
                    sld_buf, width=170 * mm, height=min(img_h, 160) * mm,
                ))
                elems.append(Spacer(1, 4 * mm))
        except Exception:
            pass

    hrs = network_data.get("hours_analyzed", 0)
    data = [
        ["Parameter", "Value"],
        ["Analysis Mode", str(network_data.get("mode", "N/A"))],
        ["Hours Analyzed", str(hrs)],
        ["Converged",
         f"{network_data.get('converged_count', 0)} / {hrs}"],
        ["Min Voltage",
         f"{network_data.get('min_voltage_pu', 0):.4f} p.u."],
        ["Max Voltage",
         f"{network_data.get('max_voltage_pu', 0):.4f} p.u."],
        ["Worst Voltage Bus",
         str(network_data.get("worst_voltage_bus", "N/A"))],
        ["Max Branch Loading",
         f"{network_data.get('max_branch_loading_pct', 0):.1f}%"],
        ["Total Losses",
         f"{network_data.get('total_losses_kw', 0):.2f} kW "
         f"({network_data.get('total_losses_pct', 0):.2f}%)"],
        ["Voltage Violations",
         str(network_data.get("voltage_violations_count", 0))],
        ["Thermal Violations",
         str(network_data.get("thermal_violations_count", 0))],
    ]
    elems.append(_styled_table(data, [85 * mm, 85 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Short circuit table
    sc = network_data.get("short_circuit")
    if sc and isinstance(sc, list) and len(sc) > 0:
        elems.append(Paragraph("Short Circuit Results", styles["SubSection"]))
        sc_data: list[list[str]] = [
            ["Bus", "Fault Current (kA)", "Fault Level (MVA)"],
        ]
        for entry in sc[:20]:
            sc_data.append([
                str(entry.get("bus", "")),
                f"{entry.get('fault_current_ka', 0):.2f}",
                f"{entry.get('fault_level_mva', 0):.2f}",
            ])
        elems.append(_styled_table(sc_data, [60 * mm, 55 * mm, 55 * mm]))
        elems.append(Spacer(1, 4 * mm))

    # Branch flow table (worst-case snapshot)
    branch_flows = network_data.get("branch_flows", [])
    if branch_flows:
        elems.append(
            Paragraph("Branch Loading Summary", styles["SubSection"])
        )
        worst = max(
            branch_flows,
            key=lambda snap: max(
                (f.get("loading_pct", 0) for f in snap.get("flows", [])),
                default=0,
            ),
        )
        flows = worst.get("flows", [])
        if flows:
            bf_data: list[list[str]] = [
                ["Branch", "Power (kW)", "Losses (kW)", "Loading (%)"],
            ]
            for f in flows[:15]:
                bf_data.append([
                    str(f.get("name", "")),
                    f"{f.get('power_kw', 0):.1f}",
                    f"{f.get('losses_kw', 0):.2f}",
                    f"{f.get('loading_pct', 0):.1f}",
                ])
            elems.append(
                _styled_table(bf_data, [50 * mm, 40 * mm, 40 * mm, 40 * mm])
            )
            elems.append(Spacer(1, 4 * mm))

    # Bus voltage time-series chart
    if (ts_bus_voltages and isinstance(ts_bus_voltages, dict)
            and len(ts_bus_voltages) > 0):
        try:
            series = {
                name: vals
                for name, vals in ts_bus_voltages.items()
                if isinstance(vals, list) and len(vals) > 1
            }
            if series:
                first_key = next(iter(series))
                x_data = list(range(len(series[first_key])))
                buf = _make_line_chart(
                    x_data, series,
                    "Bus Voltages Over Time", "Hour", "Voltage (p.u.)",
                    hlines=[
                        (0.95, "red", "0.95 p.u."),
                        (1.05, "red", "1.05 p.u."),
                    ],
                )
                elems.append(Image(buf, width=170 * mm, height=85 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 11: Sensitivity Analysis (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_sensitivity_analysis(
    styles, sensitivity_results: dict | None,
) -> list:
    if not sensitivity_results:
        return []

    tornado = sensitivity_results.get("tornado", {})
    spider = sensitivity_results.get("spider", {})
    base_results = sensitivity_results.get("base_results", {})

    if not tornado and not spider:
        return []

    elems: list = []
    elems.append(Paragraph("Sensitivity Analysis", styles["SectionHeader"]))

    # Base case table
    if base_results:
        data: list[list[str]] = [["Metric", "Base Case Value"]]
        if base_results.get("npc") is not None:
            data.append(["NPC", f"${base_results['npc']:,.0f}"])
        if base_results.get("lcoe") is not None:
            data.append(["LCOE", f"${base_results['lcoe']:.4f}/kWh"])
        if base_results.get("irr") is not None:
            data.append(["IRR", f"{base_results['irr'] * 100:.1f}%"])
        if len(data) > 1:
            elems.append(_styled_table(data, [85 * mm, 85 * mm]))
            elems.append(Spacer(1, 4 * mm))

    # Tornado chart for NPC
    if tornado:
        sorted_vars = sorted(
            tornado.items(),
            key=lambda x: x[1].get("npc_spread", 0),
            reverse=True,
        )
        labels: list[str] = []
        low_vals: list[float] = []
        high_vals: list[float] = []
        base_npc = (
            sorted_vars[0][1].get("base_npc", 0) if sorted_vars else 0
        )

        for name, td in sorted_vars[:10]:
            labels.append(name)
            low_vals.append(td.get("low_npc", base_npc) or base_npc)
            high_vals.append(td.get("high_npc", base_npc) or base_npc)

        if labels:
            try:
                buf = _make_horizontal_bar_chart(
                    labels, low_vals, high_vals, base_npc,
                    "NPC Sensitivity (Tornado)", "\u0394 NPC ($)",
                )
                elems.append(Image(
                    buf,
                    width=170 * mm,
                    height=max(60, len(labels) * 12) * mm,
                ))
            except Exception:
                pass
            elems.append(Spacer(1, 4 * mm))

    # Spider chart for LCOE
    if spider:
        try:
            plt = _init_mpl()
            fig, ax = plt.subplots(figsize=(6, 3.5))

            for i, (name, points) in enumerate(spider.items()):
                x_vals = [p.get("value", 0) for p in points]
                y_vals = [
                    p.get("lcoe", 0)
                    for p in points
                    if p.get("lcoe") is not None
                ]
                if len(y_vals) == len(x_vals) and x_vals:
                    mid = x_vals[len(x_vals) // 2]
                    if mid != 0:
                        x_pct = [(v / mid - 1) * 100 for v in x_vals]
                    else:
                        x_pct = list(range(len(x_vals)))
                    ax.plot(
                        x_pct, y_vals, "-o", label=name, markersize=3,
                        color=CHART_COLORS[i % len(CHART_COLORS)],
                        linewidth=1,
                    )

            ax.set_xlabel("Parameter Change (%)")
            ax.set_ylabel("LCOE ($/kWh)")
            ax.set_title(
                "LCOE Sensitivity (Spider Plot)", fontweight="bold",
            )
            ax.legend(fontsize=6, loc="best")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            buf = _fig_to_buf(fig)
            elems.append(Image(buf, width=170 * mm, height=100 * mm))
        except Exception:
            pass

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 12: FREF Analysis (conditional)
# ══════════════════════════════════════════════════════════════════════

def _build_fref_section(styles, fref_metadata: dict | None) -> list:
    """Build the FREF (Fiji Rural Electrification Fund) analysis section.

    Only rendered when fref_metadata is provided (i.e. FREF mode).
    """
    if not fref_metadata:
        return []

    elems: list = []
    elems.append(PageBreak())
    elems.append(Paragraph("FREF Analysis", styles["SectionHeader"]))
    elems.append(Paragraph(
        "Analysis specific to the Fiji Rural Electrification Fund programme, "
        "including per-household costs, battery autonomy, diesel displacement, "
        "and cyclone resilience.",
        styles["BodyText2"],
    ))
    elems.append(Spacer(1, 4 * mm))

    # Cost per Household table
    cost_per_hh = fref_metadata.get("cost_per_household", {})
    num_hh = fref_metadata.get("num_households", 0)
    elems.append(Paragraph("Cost per Household", styles["SubSection"]))
    cost_data = [
        ["Metric", "Value"],
        ["Number of Households", f"{num_hh}"],
        ["Cost per Household (USD)",
         _fmt(cost_per_hh.get("usd"), ",.0f", "$")],
        ["Cost per Household (FJD)",
         _fmt(cost_per_hh.get("fjd"), ",.0f", "FJ$")],
        ["Monthly Cost per HH (USD, 20yr)",
         _fmt(cost_per_hh.get("monthly_usd"), ",.0f", "$")],
    ]
    elems.append(_styled_table(cost_data, [100 * mm, 70 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Autonomy Analysis
    autonomy = fref_metadata.get("autonomy", {})
    elems.append(Paragraph("Autonomy Analysis", styles["SubSection"]))
    auto_data = [
        ["Parameter", "Value"],
        ["Required Autonomy",
         f"{autonomy.get('days_required', 3)} days"],
        ["Battery Capacity",
         _fmt(autonomy.get("battery_kwh"), ",.0f", "", " kWh")],
        ["Daily Load",
         _fmt(autonomy.get("daily_load_kwh"), ",.0f", "", " kWh")],
        ["Actual Autonomy",
         _fmt(autonomy.get("actual_days"), ".1f", "", " days")],
        ["Meets FREF Requirement",
         "Yes" if autonomy.get("meets_requirement", False) else "No"],
    ]
    elems.append(_styled_table(auto_data, [100 * mm, 70 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Diesel Displacement
    displacement = fref_metadata.get("diesel_displacement", {})
    elems.append(Paragraph("Diesel Displacement", styles["SubSection"]))
    disp_data = [
        ["Parameter", "Value"],
        ["Diesel Displaced",
         _fmt(displacement.get("pct"), ".1f", "", "%")],
        ["Diesel Saved (L/yr)",
         _fmt(displacement.get("litres_saved"), ",.0f", "", " L")],
        ["Fuel Cost Saved (USD/yr)",
         _fmt(displacement.get("cost_saved_usd"), ",.0f", "$")],
        ["CO\u2082 Avoided (kg/yr)",
         _fmt(displacement.get("co2_avoided_kg"), ",.0f", "", " kg")],
    ]
    elems.append(_styled_table(disp_data, [100 * mm, 70 * mm]))
    elems.append(Spacer(1, 4 * mm))

    # Cyclone Resilience
    cyclone = fref_metadata.get("cyclone", {})
    if cyclone:
        elems.append(Paragraph("Cyclone Resilience", styles["SubSection"]))
        cyc_data = [
            ["Parameter", "Value"],
            ["Cyclone Zone",
             "Yes" if cyclone.get("in_zone", False) else "No"],
            ["Annual Derating Applied",
             _fmt(cyclone.get("derating_pct"), ".1f", "", "%")],
            ["Energy Impact (kWh/yr)",
             _fmt(cyclone.get("energy_loss_kwh"), ",.0f", "", " kWh")],
        ]
        elems.append(_styled_table(cyc_data, [100 * mm, 70 * mm]))
        elems.append(Spacer(1, 4 * mm))

    # Community Benefit Summary
    elems.append(Paragraph("Community Benefit Summary", styles["SubSection"]))
    tariff_fjd = fref_metadata.get("fea_tariff_comparison_fjd", 0)
    system_lcoe_fjd = fref_metadata.get("system_lcoe_fjd", 0)
    smart_meter = fref_metadata.get("smart_metering", {})
    benefit_data = [
        ["Metric", "Value"],
        ["FEA Grid Tariff",
         _fmt(tariff_fjd, ".4f", "FJ$", "/kWh")],
        ["System LCOE (FJD)",
         _fmt(system_lcoe_fjd, ".4f", "FJ$", "/kWh")],
        ["Tariff Savings",
         f"{'Yes' if system_lcoe_fjd and system_lcoe_fjd < tariff_fjd else 'No'} "
         f"({_fmt(abs(tariff_fjd - system_lcoe_fjd) if tariff_fjd and system_lcoe_fjd else 0, '.4f', 'FJ$', '/kWh')})"],
        ["Smart Metering",
         f"{'Included' if smart_meter.get('included', False) else 'Not included'} "
         f"({_fmt(smart_meter.get('total_cost_usd'), ',.0f', '$')})"],
    ]
    elems.append(_styled_table(benefit_data, [100 * mm, 70 * mm]))

    return elems


# ══════════════════════════════════════════════════════════════════════
# Section 13: Conclusions & Recommendations
# ══════════════════════════════════════════════════════════════════════

def _build_conclusions(
    styles,
    economics: dict,
    summary: dict,
    network_data: dict | None,
    components: list[dict],
    discount_rate: float,
) -> list:
    elems: list = []
    elems.append(PageBreak())
    elems.append(
        Paragraph("Conclusions & Recommendations", styles["SectionHeader"])
    )

    irr = economics.get("irr")
    payback = economics.get("payback_years")
    re_frac = economics.get("renewable_fraction", 0)
    annual_load = summary.get("annual_load_kwh", 0)
    unmet = summary.get("annual_unmet_kwh", 0)
    unmet_pct = (unmet / annual_load * 100) if annual_load > 0 else 0

    # Economic
    elems.append(Paragraph("<b>Economic Conclusion</b>", styles["BodyText2"]))
    if irr is not None and irr > discount_rate:
        txt = (
            f"The proposed system is economically viable with an IRR of "
            f"{irr * 100:.1f}%"
        )
        if payback and payback < float("inf"):
            txt += f" and a payback period of {payback:.1f} years."
        else:
            txt += "."
    elif irr is not None:
        txt = (
            f"The system IRR of {irr * 100:.1f}% is below the required "
            f"return. Cost optimization or additional revenue may be necessary."
        )
    else:
        txt = (
            f"The total Net Present Cost is "
            f"${economics.get('npc', 0):,.0f} over the analysis period."
        )
    elems.append(Paragraph(txt, styles["BodyText2"]))

    # Performance
    elems.append(Paragraph("<b>Performance</b>", styles["BodyText2"]))
    if re_frac >= 0.80:
        ptxt = (
            f"High renewable energy fraction of {re_frac * 100:.1f}%, "
            f"significantly reducing fossil fuel dependency."
        )
    elif re_frac >= 0.50:
        ptxt = (
            f"Moderate renewable fraction of {re_frac * 100:.1f}%. "
            f"Additional RE capacity could further reduce emissions."
        )
    else:
        ptxt = (
            f"Renewable fraction of {re_frac * 100:.1f}% suggests "
            f"significant reliance on conventional generation."
        )
    elems.append(Paragraph(ptxt, styles["BodyText2"]))

    # Reliability
    elems.append(Paragraph("<b>Reliability</b>", styles["BodyText2"]))
    if unmet_pct < 0.1:
        rtxt = "System reliability is excellent with virtually zero unmet load."
    elif unmet_pct < 1.0:
        rtxt = (
            f"Unmet load of {unmet_pct:.2f}% is within acceptable limits "
            f"for most applications."
        )
    else:
        rtxt = (
            f"Unmet load of {unmet_pct:.1f}% indicates the system may be "
            f"undersized. Additional capacity is recommended."
        )
    elems.append(Paragraph(rtxt, styles["BodyText2"]))

    # Network
    if network_data:
        v_viol = network_data.get("voltage_violations_count", 0)
        t_viol = network_data.get("thermal_violations_count", 0)
        if v_viol + t_viol == 0:
            elems.append(Paragraph(
                "<b>Network:</b> Power flow analysis shows no voltage or "
                "thermal violations.",
                styles["BodyText2"],
            ))
        else:
            elems.append(Paragraph(
                f"<b>Network:</b> {v_viol} voltage and {t_viol} thermal "
                f"violations detected. Network reinforcement may be required.",
                styles["BodyText2"],
            ))

    # Recommendations
    elems.append(Spacer(1, 4 * mm))
    elems.append(Paragraph("<b>Recommendations</b>", styles["BodyText2"]))

    recs: list[str] = []

    curtailed = summary.get("annual_curtailed_kwh", 0)
    re_total = (summary.get("annual_pv_kwh", 0)
                + summary.get("annual_wind_kwh", 0))
    if re_total > 0 and curtailed > 0.05 * re_total:
        recs.append(
            "Significant energy curtailment detected. Consider adding storage "
            "capacity to capture excess renewable energy."
        )

    gen_hours = summary.get("gen_running_hours", 0)
    if gen_hours > 4000:
        recs.append(
            f"Generator runs {gen_hours:,} hours/year. Increasing renewable "
            f"capacity or storage could reduce fuel costs and emissions."
        )

    batt_cycles = summary.get("battery_equiv_cycles")
    if batt_cycles and batt_cycles > 350:
        recs.append(
            f"Battery performs {batt_cycles:.0f} equivalent cycles/year. "
            f"Verify battery warranty covers this usage level."
        )

    if unmet_pct > 1.0:
        recs.append(
            "System is undersized for the load. Add generation or storage "
            "capacity to improve reliability."
        )

    if network_data:
        if network_data.get("voltage_violations_count", 0) > 0:
            recs.append(
                "Voltage violations detected. Review cable sizing and "
                "consider adding voltage regulation equipment."
            )
        if network_data.get("thermal_violations_count", 0) > 0:
            recs.append(
                "Thermal overloading on branches. Upgrade conductor sizing "
                "or redistribute loads across buses."
            )

    if not recs:
        recs.append(
            "System design meets all technical and economic criteria. "
            "Proceed to detailed engineering design phase."
        )

    for rec in recs:
        elems.append(Paragraph(f"\u2022 {rec}", styles["BulletItem"]))

    # Disclaimer
    elems.append(Spacer(1, 10 * mm))
    elems.append(Paragraph(
        "<i>Disclaimer: This report is based on modeled simulation results "
        "and typical meteorological year data. Actual performance may vary "
        "due to equipment specifications, installation quality, weather "
        "variability, and other factors. Professional engineering review is "
        "recommended before final investment decisions.</i>",
        styles["SmallGray"],
    ))

    return elems


# ══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════════════

def generate_pdf_report(
    project_name: str,
    project_description: str | None = None,
    project_location: tuple[float, float] = (0, 0),
    simulation_name: str = "",
    dispatch_strategy: str = "",
    lifetime_years: int = 25,
    discount_rate: float = 0.08,
    economics: dict | None = None,
    timeseries: dict | None = None,
    components: list[dict] | None = None,
    summary: dict | None = None,
    network_data: dict | None = None,
    ts_bus_voltages: dict | None = None,
    sensitivity_results: dict | None = None,
    buses: list[dict] | None = None,
    branches: list[dict] | None = None,
    fref_metadata: dict | None = None,
) -> BytesIO:
    """Generate a professional PDF report and return as BytesIO buffer.

    Parameters
    ----------
    fref_metadata : dict or None
        If provided, adds a Fiji FREF analysis section with per-household
        costs, autonomy analysis, diesel displacement, and cyclone resilience.
        Only rendered when this parameter is not None.
    """
    economics = economics or {}
    timeseries = timeseries or {}
    components = components or []
    summary = summary or {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    styles = _get_styles()
    elements: list = []

    # 1. Cover page
    elements.extend(_build_cover(
        styles,
        project_name=project_name,
        project_description=project_description,
        project_location=project_location,
        simulation_name=simulation_name,
        dispatch_strategy=dispatch_strategy,
        lifetime_years=lifetime_years,
        discount_rate=discount_rate,
    ))

    # 2. Executive Summary
    elements.extend(
        _build_executive_summary(styles, economics, summary, discount_rate)
    )

    # 3. System Configuration
    elements.extend(_build_system_config(styles, components))

    # 4. Energy Balance
    elements.extend(_build_energy_balance(styles, summary))

    # 5. Dispatch Profile
    elements.extend(_build_dispatch_profile(styles, timeseries))

    # 6. Battery Performance (conditional)
    elements.extend(
        _build_battery_performance(styles, summary, timeseries, components)
    )

    # 7. Generator Performance (conditional)
    elements.extend(
        _build_generator_performance(styles, summary, timeseries, components)
    )

    # 8. Grid Interaction (conditional)
    elements.extend(_build_grid_interaction(styles, summary, timeseries))

    # 9. Cost Analysis
    elements.extend(_build_cost_analysis(styles, economics))

    # 10. Network Analysis (conditional)
    elements.extend(
        _build_network_analysis(
            styles, network_data, ts_bus_voltages,
            buses=buses, branches=branches,
        )
    )

    # 11. Sensitivity Analysis (conditional)
    elements.extend(_build_sensitivity_analysis(styles, sensitivity_results))

    # 12. FREF Analysis (conditional — only for Fiji FREF projects)
    elements.extend(_build_fref_section(styles, fref_metadata))

    # 13. Conclusions & Recommendations
    elements.extend(_build_conclusions(
        styles, economics, summary, network_data, components, discount_rate,
    ))

    doc.build(elements, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
    buffer.seek(0)
    return buffer
