"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import type { EconomicsResult, TimeseriesResult } from "@/types";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface EnergyBreakdownProps {
  timeseries: TimeseriesResult;
  economics: EconomicsResult;
}

export default function EnergyBreakdown({
  timeseries,
  economics,
}: EnergyBreakdownProps) {
  const summary = useMemo(() => {
    const sum = (arr: number[] | null) =>
      arr ? arr.reduce((a, b) => a + b, 0) : 0;

    const totalLoad = sum(timeseries.load);
    const pvEnergy = sum(timeseries.pv_output);
    const windEnergy = sum(timeseries.wind_output);
    const genEnergy = sum(timeseries.generator_output);
    const gridImport = sum(timeseries.grid_import);
    const gridExport = sum(timeseries.grid_export);
    const excess = sum(timeseries.excess);
    const unmet = sum(timeseries.unmet);

    return {
      totalLoad,
      pvEnergy,
      windEnergy,
      genEnergy,
      gridImport,
      gridExport,
      excess,
      unmet,
    };
  }, [timeseries]);

  // Monthly aggregation for bar chart
  const monthlyData = useMemo(() => {
    const monthNames = [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];
    const daysPerMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

    const monthly: Record<string, number[]> = {
      pv: Array(12).fill(0),
      wind: Array(12).fill(0),
      generator: Array(12).fill(0),
      grid_import: Array(12).fill(0),
      load: Array(12).fill(0),
    };

    let hourIdx = 0;
    for (let m = 0; m < 12; m++) {
      const hoursInMonth = daysPerMonth[m] * 24;
      for (let h = 0; h < hoursInMonth && hourIdx < 8760; h++, hourIdx++) {
        if (timeseries.pv_output) monthly.pv[m] += timeseries.pv_output[hourIdx];
        if (timeseries.wind_output) monthly.wind[m] += timeseries.wind_output[hourIdx];
        if (timeseries.generator_output) monthly.generator[m] += timeseries.generator_output[hourIdx];
        if (timeseries.grid_import) monthly.grid_import[m] += timeseries.grid_import[hourIdx];
        if (timeseries.load) monthly.load[m] += timeseries.load[hourIdx];
      }
    }

    // Convert to MWh
    for (const key of Object.keys(monthly)) {
      monthly[key] = monthly[key].map((v) => v / 1000);
    }

    return { monthNames, monthly };
  }, [timeseries]);

  const fmt = (kwh: number) =>
    kwh >= 1e6 ? `${(kwh / 1e6).toFixed(1)} GWh` : `${(kwh / 1000).toFixed(0)} MWh`;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Annual Energy Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Load", value: summary.totalLoad, color: "#ef4444" },
          { label: "PV Energy", value: summary.pvEnergy, color: "#f59e0b" },
          { label: "Wind Energy", value: summary.windEnergy, color: "#3b82f6" },
          { label: "Generator", value: summary.genEnergy, color: "#a855f7" },
          { label: "Grid Import", value: summary.gridImport, color: "#8b5cf6" },
          { label: "Grid Export", value: summary.gridExport, color: "#6366f1" },
          { label: "Excess", value: summary.excess, color: "#6b7280" },
          { label: "Unmet Load", value: summary.unmet, color: "#dc2626" },
        ].map((item) => (
          <div
            key={item.label}
            className="bg-gray-900 border border-gray-800 rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-xs text-gray-500">{item.label}</span>
            </div>
            <p className="text-lg font-bold mt-1">{fmt(item.value)}</p>
          </div>
        ))}
      </div>

      {/* Monthly Stacked Bar */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Monthly Energy Production</h3>
        <Plot
          data={[
            {
              x: monthlyData.monthNames,
              y: monthlyData.monthly.pv,
              name: "Solar PV",
              type: "bar",
              marker: { color: "#f59e0b" },
            },
            {
              x: monthlyData.monthNames,
              y: monthlyData.monthly.wind,
              name: "Wind",
              type: "bar",
              marker: { color: "#3b82f6" },
            },
            {
              x: monthlyData.monthNames,
              y: monthlyData.monthly.generator,
              name: "Generator",
              type: "bar",
              marker: { color: "#a855f7" },
            },
            {
              x: monthlyData.monthNames,
              y: monthlyData.monthly.grid_import,
              name: "Grid Import",
              type: "bar",
              marker: { color: "#8b5cf6" },
            },
            {
              x: monthlyData.monthNames,
              y: monthlyData.monthly.load,
              name: "Load",
              type: "scatter",
              mode: "lines+markers",
              line: { color: "#ef4444", width: 2 },
              marker: { size: 6 },
            },
          ]}
          layout={{
            barmode: "stack",
            height: 400,
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { color: "#9ca3af" },
            xaxis: { gridcolor: "#1f2937" },
            yaxis: { title: "Energy (MWh)", gridcolor: "#1f2937" },
            legend: { orientation: "h", y: -0.15, font: { size: 11 } },
            margin: { t: 20, r: 20, b: 60, l: 60 },
          }}
          config={{ responsive: true }}
          className="w-full"
        />
      </section>
    </div>
  );
}
