"""PDF report generation for simulation results."""
from io import BytesIO
from datetime import datetime

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


def _make_chart_image(
    x_data: list,
    y_data_dict: dict[str, list],
    title: str,
    xlabel: str,
    ylabel: str,
    width_px: int = 600,
    height_px: int = 250,
) -> BytesIO:
    """Generate a matplotlib chart and return as PNG BytesIO."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=100)
    for label, y_data in y_data_dict.items():
        ax.plot(x_data[: len(y_data)], y_data, label=label, linewidth=0.7)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7)
    if len(y_data_dict) > 1:
        ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    ylabel: str,
    width_px: int = 500,
    height_px: int = 220,
) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=100)
    bar_colors = plt.cm.Set2(np.linspace(0, 1, len(labels)))
    ax.bar(labels, values, color=bar_colors)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7, axis="x", rotation=30)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf_report(
    project_name: str,
    project_location: tuple[float, float],
    simulation_name: str,
    dispatch_strategy: str,
    economics: dict,
    timeseries: dict,
    components: list[dict],
    network_data: dict | None = None,
) -> BytesIO:
    """Generate a PDF report and return as BytesIO buffer."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "Title2",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=8,
        textColor=colors.HexColor("#2563eb"),
    ))
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1e40af"),
        borderWidth=1,
        borderColor=colors.HexColor("#2563eb"),
        borderPadding=(0, 0, 2, 0),
    ))
    styles.add(ParagraphStyle(
        "SmallText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
    ))

    elements = []

    # ── Title Page ──
    elements.append(Spacer(1, 40 * mm))
    elements.append(Paragraph("GridFlow", styles["Title2"]))
    elements.append(Paragraph("Simulation Report", styles["Heading2"]))
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(f"<b>Project:</b> {project_name}", styles["Normal"]))
    elements.append(Paragraph(
        f"<b>Location:</b> {project_location[0]:.4f}, {project_location[1]:.4f}",
        styles["Normal"],
    ))
    elements.append(Paragraph(f"<b>Simulation:</b> {simulation_name}", styles["Normal"]))
    elements.append(Paragraph(
        f"<b>Strategy:</b> {dispatch_strategy.replace('_', ' ').title()}",
        styles["Normal"],
    ))
    elements.append(Paragraph(
        f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["Normal"],
    ))
    elements.append(PageBreak())

    # ── Executive Summary ──
    elements.append(Paragraph("Executive Summary", styles["SectionHeader"]))

    summary_data = [
        ["Metric", "Value"],
        ["Net Present Cost (NPC)", f"${economics.get('npc', 0):,.0f}"],
        ["Levelized Cost of Energy (LCOE)", f"${economics.get('lcoe', 0):.4f}/kWh"],
        ["Internal Rate of Return (IRR)",
         f"{economics['irr'] * 100:.1f}%" if economics.get("irr") else "N/A"],
        ["Simple Payback", f"{economics['payback_years']:.1f} years" if economics.get("payback_years") else "N/A"],
        ["Renewable Fraction", f"{economics.get('renewable_fraction', 0) * 100:.1f}%"],
        ["CO2 Emissions", f"{economics.get('co2_emissions_kg', 0):,.0f} kg/yr"],
    ]

    t = Table(summary_data, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10 * mm))

    # ── System Components ──
    elements.append(Paragraph("System Components", styles["SectionHeader"]))

    comp_data = [["Component", "Type", "Key Parameter"]]
    for comp in components:
        ctype = comp.get("component_type", "Unknown")
        name = comp.get("name", ctype)
        cfg = comp.get("config", {})
        key_param = ""
        if ctype == "solar_pv":
            key_param = f"{cfg.get('capacity_kwp', '?')} kWp"
        elif ctype == "battery":
            key_param = f"{cfg.get('capacity_kwh', '?')} kWh"
        elif ctype == "wind_turbine":
            key_param = f"{cfg.get('rated_power_kw', '?')} kW"
        elif ctype == "diesel_generator":
            key_param = f"{cfg.get('rated_power_kw', '?')} kW"
        elif ctype == "grid_connection":
            key_param = f"Import: {cfg.get('max_import_kw', '?')} kW"
        elif ctype == "inverter":
            key_param = f"{cfg.get('rated_power_kw', '?')} kW"
        comp_data.append([name, ctype.replace("_", " ").title(), key_param])

    if len(comp_data) > 1:
        ct = Table(comp_data, colWidths=[60 * mm, 50 * mm, 60 * mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(ct)

    # ── Cost Breakdown ──
    cost_bd = economics.get("cost_breakdown", {})
    if cost_bd:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Cost Breakdown", styles["SectionHeader"]))

        labels = [k.replace("_", " ").title() for k in cost_bd.keys()]
        values = list(cost_bd.values())
        try:
            chart_img = _make_bar_chart(labels, values, "Cost Breakdown ($)", "USD")
            elements.append(Image(chart_img, width=170 * mm, height=75 * mm))
        except Exception:
            pass

    # ── Energy Production Summary ──
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("Energy Production", styles["SectionHeader"]))

    ts = timeseries
    energy_data = [["Source", "Annual Output (kWh)"]]
    if ts.get("pv_output"):
        energy_data.append(["Solar PV", f"{sum(ts['pv_output']):,.0f}"])
    if ts.get("wind_output"):
        energy_data.append(["Wind", f"{sum(ts['wind_output']):,.0f}"])
    if ts.get("generator_output"):
        energy_data.append(["Generator", f"{sum(ts['generator_output']):,.0f}"])
    if ts.get("grid_import"):
        energy_data.append(["Grid Import", f"{sum(ts['grid_import']):,.0f}"])
    if ts.get("grid_export"):
        energy_data.append(["Grid Export", f"{sum(ts['grid_export']):,.0f}"])
    energy_data.append(["Total Load", f"{sum(ts.get('load', [0])):,.0f}"])
    if ts.get("unmet"):
        energy_data.append(["Unmet Load", f"{sum(ts['unmet']):,.0f}"])

    et = Table(energy_data, colWidths=[90 * mm, 80 * mm])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(et)

    # ── Monthly Energy Chart ──
    elements.append(Spacer(1, 6 * mm))
    try:
        load = ts.get("load", [])
        pv = ts.get("pv_output", [])
        if load and len(load) == 8760:
            load_arr = np.array(load)
            month_hours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            offset = 0
            monthly_load = []
            monthly_pv = []
            for h in month_hours:
                monthly_load.append(load_arr[offset:offset + h].sum())
                if pv and len(pv) == 8760:
                    monthly_pv.append(np.array(pv[offset:offset + h]).sum())
                offset += h

            chart_data = {"Load": monthly_load}
            if monthly_pv:
                chart_data["Solar PV"] = monthly_pv

            chart_img = _make_bar_chart(
                months,
                monthly_load,
                "Monthly Energy Consumption (kWh)",
                "kWh",
            )
            elements.append(Image(chart_img, width=170 * mm, height=70 * mm))
    except Exception:
        pass

    # ── Footer ──
    elements.append(Spacer(1, 15 * mm))
    elements.append(Paragraph(
        "Report generated by GridFlow Power Grid Analysis Platform",
        styles["SmallText"],
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
