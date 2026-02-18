"use client";

import { useState, useMemo, useRef } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import type { TimeseriesResult } from "@/types";
import { ChartExportButton } from "./chart-export-button";

interface TimeseriesChartProps {
  data: TimeseriesResult;
}

type ViewRange = "year" | "month" | "week" | "day";

export default function TimeseriesChart({ data }: TimeseriesChartProps) {
  const powerChartRef = useRef<HTMLDivElement>(null);
  const socChartRef = useRef<HTMLDivElement>(null);
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

  const chartData = useMemo(() => {
    const result = [];
    for (let i = startHour; i < endHour; i++) {
      const point: Record<string, number> = { hour: i };
      if (data.load) point.load = data.load[i];
      if (data.pv_output) point.pv = data.pv_output[i];
      if (data.wind_output) point.wind = data.wind_output[i];
      if (data.generator_output) point.generator = data.generator_output[i];
      if (data.grid_import) point.gridImport = data.grid_import[i];
      if (data.battery_power) point.batteryPower = data.battery_power[i];
      result.push(point);
    }
    return result;
  }, [data, startHour, endHour]);

  const socData = useMemo(() => {
    if (!data.battery_soc) return null;
    const result = [];
    for (let i = startHour; i < endHour; i++) {
      result.push({ hour: i, soc: data.battery_soc[i] * 100 });
    }
    return result;
  }, [data.battery_soc, startHour, endHour]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
        <div className="flex gap-1 shrink-0">
          {(["day", "week", "month", "year"] as ViewRange[]).map((range) => (
            <Button
              key={range}
              variant={viewRange === range ? "default" : "outline"}
              size="sm"
              onClick={() => setViewRange(range)}
            >
              {range.charAt(0).toUpperCase() + range.slice(1)}
            </Button>
          ))}
        </div>

        {viewRange !== "year" && (
          <div className="flex-1 w-full">
            <Slider
              min={0}
              max={8760 - hours}
              step={1}
              value={[startHour]}
              onValueChange={([v]) => setStartHour(v)}
            />
          </div>
        )}
      </div>

      <Card variant="glass">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Power Output (kW)</CardTitle>
          <ChartExportButton chartRef={powerChartRef} filename="power-output" />
        </CardHeader>
        <CardContent ref={powerChartRef}>
          <ResponsiveContainer width="100%" height={450}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2 32.6% 17.5%)" />
              <XAxis
                dataKey="hour"
                stroke="hsl(215 20.2% 65.1%)"
                fontSize={11}
                tickFormatter={(v) => `${v}h`}
              />
              <YAxis stroke="hsl(215 20.2% 65.1%)" fontSize={11} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(222.2 84% 4.9%)",
                  border: "1px solid hsl(217.2 32.6% 17.5%)",
                  borderRadius: "0.75rem",
                  fontSize: "12px",
                }}
                labelFormatter={(v) => `Hour ${v}`}
              />
              <Legend />
              {data.load && (
                <Line
                  type="monotone"
                  dataKey="load"
                  name="Load"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  dot={false}
                />
              )}
              {data.pv_output && (
                <Line
                  type="monotone"
                  dataKey="pv"
                  name="PV Output"
                  stroke="#f59e0b"
                  strokeWidth={1}
                  dot={false}
                />
              )}
              {data.wind_output && (
                <Line
                  type="monotone"
                  dataKey="wind"
                  name="Wind Output"
                  stroke="#3b82f6"
                  strokeWidth={1}
                  dot={false}
                />
              )}
              {data.generator_output && (
                <Line
                  type="monotone"
                  dataKey="generator"
                  name="Generator"
                  stroke="#a855f7"
                  strokeWidth={1}
                  dot={false}
                />
              )}
              {data.grid_import && (
                <Line
                  type="monotone"
                  dataKey="gridImport"
                  name="Grid Import"
                  stroke="#8b5cf6"
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                />
              )}
              {data.battery_power && (
                <Line
                  type="monotone"
                  dataKey="batteryPower"
                  name="Battery Power"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  dot={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Battery SOC */}
      {socData && (
        <Card variant="glass">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Battery State of Charge</CardTitle>
            <ChartExportButton chartRef={socChartRef} filename="battery-soc" />
          </CardHeader>
          <CardContent ref={socChartRef}>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={socData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2 32.6% 17.5%)" />
                <XAxis
                  dataKey="hour"
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  tickFormatter={(v) => `${v}h`}
                />
                <YAxis
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [`${value.toFixed(1)}%`, "SOC"]}
                />
                <defs>
                  <linearGradient id="socGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="soc"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  fill="url(#socGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
