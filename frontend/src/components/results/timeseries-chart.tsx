"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import type { TimeseriesResult } from "@/types";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface TimeseriesChartProps {
  data: TimeseriesResult;
}

type ViewRange = "year" | "month" | "week" | "day";

export default function TimeseriesChart({ data }: TimeseriesChartProps) {
  const [viewRange, setViewRange] = useState<ViewRange>("week");
  const [startHour, setStartHour] = useState(0);

  const rangeHours: Record<ViewRange, number> = {
    year: 8760,
    month: 730,
    week: 168,
    day: 24,
  };

  const hours = rangeHours[viewRange];
  const endHour = Math.min(startHour + hours, 8760);

  const traces = useMemo(() => {
    const t: Plotly.Data[] = [];
    const x = Array.from({ length: endHour - startHour }, (_, i) => startHour + i);

    if (data.load) {
      t.push({
        x,
        y: data.load.slice(startHour, endHour),
        name: "Load",
        type: "scatter",
        mode: "lines",
        line: { color: "#ef4444", width: 1.5 },
      });
    }
    if (data.pv_output) {
      t.push({
        x,
        y: data.pv_output.slice(startHour, endHour),
        name: "PV Output",
        type: "scatter",
        mode: "lines",
        fill: "tozeroy",
        fillcolor: "rgba(245,158,11,0.2)",
        line: { color: "#f59e0b", width: 1 },
      });
    }
    if (data.wind_output) {
      t.push({
        x,
        y: data.wind_output.slice(startHour, endHour),
        name: "Wind Output",
        type: "scatter",
        mode: "lines",
        fill: "tozeroy",
        fillcolor: "rgba(59,130,246,0.2)",
        line: { color: "#3b82f6", width: 1 },
      });
    }
    if (data.generator_output) {
      t.push({
        x,
        y: data.generator_output.slice(startHour, endHour),
        name: "Generator",
        type: "scatter",
        mode: "lines",
        line: { color: "#a855f7", width: 1 },
      });
    }
    if (data.grid_import) {
      t.push({
        x,
        y: data.grid_import.slice(startHour, endHour),
        name: "Grid Import",
        type: "scatter",
        mode: "lines",
        line: { color: "#8b5cf6", width: 1, dash: "dot" },
      });
    }
    if (data.battery_power) {
      t.push({
        x,
        y: data.battery_power.slice(startHour, endHour),
        name: "Battery Power",
        type: "scatter",
        mode: "lines",
        line: { color: "#10b981", width: 1.5 },
        yaxis: "y2",
      });
    }

    return t;
  }, [data, startHour, endHour]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="flex gap-1">
          {(["day", "week", "month", "year"] as ViewRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setViewRange(range)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                viewRange === range
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {range.charAt(0).toUpperCase() + range.slice(1)}
            </button>
          ))}
        </div>

        {viewRange !== "year" && (
          <input
            type="range"
            min={0}
            max={8760 - hours}
            value={startHour}
            onChange={(e) => setStartHour(parseInt(e.target.value))}
            className="flex-1"
          />
        )}
      </div>

      <Plot
        data={traces}
        layout={{
          height: 500,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#9ca3af" },
          xaxis: {
            title: "Hour",
            gridcolor: "#1f2937",
            zerolinecolor: "#374151",
          },
          yaxis: {
            title: "Power (kW)",
            gridcolor: "#1f2937",
            zerolinecolor: "#374151",
          },
          yaxis2: {
            title: "Battery (kW)",
            overlaying: "y",
            side: "right",
            gridcolor: "#1f2937",
          },
          legend: {
            orientation: "h",
            y: -0.15,
            font: { size: 11 },
          },
          margin: { t: 20, r: 60, b: 60, l: 60 },
        }}
        config={{ responsive: true }}
        className="w-full"
      />

      {/* Battery SOC */}
      {data.battery_soc && (
        <Plot
          data={[
            {
              x: Array.from({ length: endHour - startHour }, (_, i) => startHour + i),
              y: data.battery_soc.slice(startHour, endHour).map((v) => v * 100),
              name: "Battery SOC",
              type: "scatter",
              mode: "lines",
              fill: "tozeroy",
              fillcolor: "rgba(16,185,129,0.15)",
              line: { color: "#10b981", width: 1.5 },
            },
          ]}
          layout={{
            height: 200,
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { color: "#9ca3af" },
            xaxis: { title: "Hour", gridcolor: "#1f2937" },
            yaxis: {
              title: "SOC (%)",
              range: [0, 100],
              gridcolor: "#1f2937",
            },
            margin: { t: 10, r: 20, b: 40, l: 60 },
            showlegend: false,
          }}
          config={{ responsive: true }}
          className="w-full"
        />
      )}
    </div>
  );
}
