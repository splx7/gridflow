"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
  ReferenceLine,
  Cell,
} from "recharts";
import { Loader2, Play } from "lucide-react";
import { HelpIcon } from "@/components/ui/help-drawer";
import {
  getErrorMessage,
  getSensitivityResults,
  runSensitivity,
} from "@/lib/api";
import type {
  SensitivityResult,
  SensitivityVariable,
} from "@/types";

const SPIDER_COLORS = [
  "#3b82f6",
  "#ef4444",
  "#10b981",
  "#f59e0b",
  "#a855f7",
  "#ec4899",
  "#6366f1",
  "#14b8a6",
];

type MetricKey = "npc" | "lcoe" | "irr" | "payback_years";

const METRIC_OPTIONS: { value: MetricKey; label: string; format: (v: number | null) => string }[] = [
  { value: "npc", label: "Net Present Cost ($)", format: (v) => v != null ? `$${(v / 1000).toFixed(0)}k` : "N/A" },
  { value: "lcoe", label: "LCOE ($/kWh)", format: (v) => v != null ? `$${v.toFixed(4)}` : "N/A" },
  { value: "irr", label: "IRR (%)", format: (v) => v != null ? `${(v * 100).toFixed(1)}%` : "N/A" },
  { value: "payback_years", label: "Payback (years)", format: (v) => v != null ? `${v.toFixed(1)} yr` : "N/A" },
];

const DEFAULT_VARIABLES: SensitivityVariable[] = [
  { name: "Fuel Price", param_path: "components.diesel_generator.fuel_price", range: [0.50, 2.50], points: 9 },
  { name: "PV Cost", param_path: "components.solar_pv.capital_cost_per_kw", range: [400, 1200], points: 9 },
  { name: "Battery Cost", param_path: "components.battery.capital_cost_per_kwh", range: [100, 500], points: 9 },
  { name: "Discount Rate", param_path: "project.discount_rate", range: [0.04, 0.12], points: 9 },
];

interface SensitivityPanelProps {
  simulationId: string;
  initialData: SensitivityResult | null;
}

export default function SensitivityPanel({
  simulationId,
  initialData,
}: SensitivityPanelProps) {
  const [data, setData] = useState<SensitivityResult | null>(initialData);
  const [running, setRunning] = useState(false);
  const [metric, setMetric] = useState<MetricKey>("npc");

  const handleRun = async () => {
    setRunning(true);
    try {
      await runSensitivity(simulationId, DEFAULT_VARIABLES);
      toast.info("Sensitivity analysis started. This may take a few minutes...");

      // Poll for results
      const poll = async (attempts: number): Promise<SensitivityResult | null> => {
        if (attempts <= 0) return null;
        await new Promise((r) => setTimeout(r, 5000));
        try {
          return await getSensitivityResults(simulationId);
        } catch {
          return poll(attempts - 1);
        }
      };

      const result = await poll(60); // Poll up to 5 minutes
      if (result) {
        setData(result);
        toast.success("Sensitivity analysis complete");
      } else {
        toast.error("Sensitivity analysis timed out. Check back later.");
      }
    } catch (err) {
      toast.error("Failed to start sensitivity: " + getErrorMessage(err));
    } finally {
      setRunning(false);
    }
  };

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sensitivity Analysis</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 py-12">
          <p className="text-muted-foreground text-sm text-center max-w-md">
            Run a one-at-a-time sensitivity analysis to understand how key parameters
            affect your system economics. This sweeps 4 variables (fuel price, PV cost,
            battery cost, discount rate) across their plausible ranges.
          </p>
          <Button onClick={handleRun} disabled={running} size="lg">
            {running ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Running Analysis...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Sensitivity Analysis
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const metricOption = METRIC_OPTIONS.find((m) => m.value === metric)!;

  // ----- Tornado data -----
  const tornadoEntries = Object.entries(data.tornado)
    .map(([name, t]) => {
      const low = t[`low_${metric}` as keyof typeof t] as number | null;
      const high = t[`high_${metric}` as keyof typeof t] as number | null;
      const base = t[`base_${metric}` as keyof typeof t] as number | null;
      if (low == null || high == null || base == null) return null;
      return {
        name,
        low,
        high,
        base,
        lowDelta: low - base,
        highDelta: high - base,
        spread: Math.abs(high - low),
      };
    })
    .filter((e): e is NonNullable<typeof e> => e != null)
    .sort((a, b) => b.spread - a.spread);

  // ----- Spider data -----
  const spiderVarNames = Object.keys(data.spider);
  const baseVal = data.base_results[metric];

  // Build spider plot data: each point = one sweep value, normalized as % change from base
  const spiderLines: { name: string; data: { pctChange: number; value: number }[] }[] = [];
  for (const varName of spiderVarNames) {
    const points = data.spider[varName];
    if (!points || points.length === 0) continue;

    // Find the base value index (closest to midpoint)
    const midIdx = Math.floor(points.length / 2);
    const baseParamVal = points[midIdx].value;

    const lineData = points.map((pt) => {
      const metricVal = pt[metric] as number | null;
      const pctChange = baseParamVal !== 0
        ? ((pt.value - baseParamVal) / Math.abs(baseParamVal)) * 100
        : 0;
      return {
        pctChange: Math.round(pctChange * 10) / 10,
        value: metricVal ?? 0,
      };
    });

    spiderLines.push({ name: varName, data: lineData });
  }

  // Merge spider lines into a unified dataset for recharts
  // X-axis = pctChange values from all lines (we use the first line's pctChange as reference)
  const spiderChartData: Record<string, number>[] = [];
  if (spiderLines.length > 0) {
    const refLine = spiderLines[0];
    for (let i = 0; i < refLine.data.length; i++) {
      const entry: Record<string, number> = {
        pctChange: refLine.data[i].pctChange,
      };
      for (const line of spiderLines) {
        if (i < line.data.length) {
          entry[line.name] = line.data[i].value;
        }
      }
      spiderChartData.push(entry);
    }
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-muted-foreground">Metric:</label>
          <Select value={metric} onValueChange={(v) => setMetric(v as MetricKey)}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRIC_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" size="sm" onClick={handleRun} disabled={running}>
          {running ? (
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          ) : (
            <Play className="h-4 w-4 mr-1.5" />
          )}
          Re-run
        </Button>
      </div>

      {/* Tornado Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-1.5">
            <CardTitle className="text-base">
              Tornado Diagram — {metricOption.label}
            </CardTitle>
            <HelpIcon helpKey="sensitivity.tornado" />
          </div>
        </CardHeader>
        <CardContent>
          {tornadoEntries.length > 0 ? (
            <ResponsiveContainer width="100%" height={40 + tornadoEntries.length * 50}>
              <BarChart
                data={tornadoEntries}
                layout="vertical"
                margin={{ left: 100, right: 30, top: 10, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  tickFormatter={(v: number) => metricOption.format(v)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={90}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  formatter={(v: number) => metricOption.format(v)}
                  labelFormatter={(name: string) => name}
                />
                <ReferenceLine x={tornadoEntries[0]?.base ?? 0} stroke="#666" strokeDasharray="3 3" />
                <Bar dataKey="low" name="Low" stackId="a" fill="transparent">
                  {tornadoEntries.map((_, i) => (
                    <Cell key={i} fill="#3b82f6" />
                  ))}
                </Bar>
                <Bar dataKey="high" name="High" stackId="b" fill="transparent">
                  {tornadoEntries.map((_, i) => (
                    <Cell key={i} fill="#ef4444" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-8 text-center">
              No tornado data available for this metric
            </p>
          )}
        </CardContent>
      </Card>

      {/* Spider Plot */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-1.5">
            <CardTitle className="text-base">
              Spider Plot — {metricOption.label}
            </CardTitle>
            <HelpIcon helpKey="sensitivity.spider" />
          </div>
        </CardHeader>
        <CardContent>
          {spiderChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart
                data={spiderChartData}
                margin={{ left: 20, right: 30, top: 10, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="pctChange"
                  label={{ value: "% Change from Base", position: "insideBottom", offset: -5 }}
                  tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}%`}
                />
                <YAxis
                  tickFormatter={(v: number) => metricOption.format(v)}
                />
                <Tooltip
                  formatter={(v: number, name: string) => [metricOption.format(v), name]}
                  labelFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}% from base`}
                />
                <Legend />
                {baseVal != null && (
                  <ReferenceLine y={baseVal} stroke="#666" strokeDasharray="3 3" label="Base" />
                )}
                {spiderLines.map((line, i) => (
                  <Line
                    key={line.name}
                    type="monotone"
                    dataKey={line.name}
                    stroke={SPIDER_COLORS[i % SPIDER_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-8 text-center">
              No spider data available for this metric
            </p>
          )}
        </CardContent>
      </Card>

      {/* Base Results Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Base Case Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {METRIC_OPTIONS.map((opt) => (
              <div key={opt.value} className="text-center">
                <p className="text-xs text-muted-foreground">{opt.label}</p>
                <p className="text-lg font-semibold">
                  {opt.format(data.base_results[opt.value])}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
