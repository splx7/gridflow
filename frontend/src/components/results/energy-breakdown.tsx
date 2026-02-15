"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EconomicsResult, TimeseriesResult } from "@/types";

interface EnergyBreakdownProps {
  timeseries: TimeseriesResult;
  economics: EconomicsResult;
}

export default function EnergyBreakdown({
  timeseries,
}: EnergyBreakdownProps) {
  const summary = useMemo(() => {
    const sum = (arr: number[] | null) =>
      arr ? arr.reduce((a, b) => a + b, 0) : 0;

    return {
      totalLoad: sum(timeseries.load),
      pvEnergy: sum(timeseries.pv_output),
      windEnergy: sum(timeseries.wind_output),
      genEnergy: sum(timeseries.generator_output),
      gridImport: sum(timeseries.grid_import),
      gridExport: sum(timeseries.grid_export),
      excess: sum(timeseries.excess),
      unmet: sum(timeseries.unmet),
    };
  }, [timeseries]);

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
      gridImport: Array(12).fill(0),
      load: Array(12).fill(0),
    };

    let hourIdx = 0;
    for (let m = 0; m < 12; m++) {
      const hoursInMonth = daysPerMonth[m] * 24;
      for (let h = 0; h < hoursInMonth && hourIdx < 8760; h++, hourIdx++) {
        if (timeseries.pv_output) monthly.pv[m] += timeseries.pv_output[hourIdx];
        if (timeseries.wind_output) monthly.wind[m] += timeseries.wind_output[hourIdx];
        if (timeseries.generator_output)
          monthly.generator[m] += timeseries.generator_output[hourIdx];
        if (timeseries.grid_import)
          monthly.gridImport[m] += timeseries.grid_import[hourIdx];
        if (timeseries.load) monthly.load[m] += timeseries.load[hourIdx];
      }
    }

    return monthNames.map((name, i) => ({
      month: name,
      pv: monthly.pv[i] / 1000,
      wind: monthly.wind[i] / 1000,
      generator: monthly.generator[i] / 1000,
      gridImport: monthly.gridImport[i] / 1000,
      load: monthly.load[i] / 1000,
    }));
  }, [timeseries]);

  const fmt = (kwh: number) =>
    kwh >= 1e6
      ? `${(kwh / 1e6).toFixed(1)} GWh`
      : `${(kwh / 1000).toFixed(0)} MWh`;

  const items = [
    { label: "Total Load", value: summary.totalLoad, color: "#ef4444" },
    { label: "PV Energy", value: summary.pvEnergy, color: "#f59e0b" },
    { label: "Wind Energy", value: summary.windEnergy, color: "#3b82f6" },
    { label: "Generator", value: summary.genEnergy, color: "#a855f7" },
    { label: "Grid Import", value: summary.gridImport, color: "#8b5cf6" },
    { label: "Grid Export", value: summary.gridExport, color: "#6366f1" },
    { label: "Excess", value: summary.excess, color: "#6b7280" },
    { label: "Unmet Load", value: summary.unmet, color: "#dc2626" },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Annual Energy Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {items.map((item) => (
          <Card key={item.label} variant="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-xs text-muted-foreground">
                  {item.label}
                </span>
              </div>
              <p className="text-lg font-bold mt-1">{fmt(item.value)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Monthly Stacked Bar */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle>Monthly Energy Production</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2 32.6% 17.5%)" />
              <XAxis
                dataKey="month"
                stroke="hsl(215 20.2% 65.1%)"
                fontSize={11}
              />
              <YAxis
                stroke="hsl(215 20.2% 65.1%)"
                fontSize={11}
                label={{
                  value: "Energy (MWh)",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "hsl(215 20.2% 65.1%)", fontSize: 11 },
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(222.2 84% 4.9%)",
                  border: "1px solid hsl(217.2 32.6% 17.5%)",
                  borderRadius: "0.75rem",
                  fontSize: "12px",
                }}
                formatter={(value: number) => `${value.toFixed(1)} MWh`}
              />
              <Legend />
              <Bar dataKey="pv" name="Solar PV" stackId="a" fill="#f59e0b" radius={[0, 0, 0, 0]} />
              <Bar dataKey="wind" name="Wind" stackId="a" fill="#3b82f6" />
              <Bar dataKey="generator" name="Generator" stackId="a" fill="#a855f7" />
              <Bar dataKey="gridImport" name="Grid Import" stackId="a" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              <Line
                type="monotone"
                dataKey="load"
                name="Load"
                stroke="#ef4444"
                strokeWidth={2}
                dot={{ r: 3, fill: "#ef4444" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
