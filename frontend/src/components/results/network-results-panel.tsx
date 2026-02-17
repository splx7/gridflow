"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { NetworkResultsData } from "@/types";

const LINE_COLORS = [
  "#3b82f6", "#f59e0b", "#10b981", "#a855f7", "#ef4444",
  "#8b5cf6", "#ec4899", "#6366f1", "#14b8a6", "#f97316",
];

interface NetworkResultsPanelProps {
  data: NetworkResultsData;
}

function voltageBadge(v: number) {
  if (v < 0.9 || v > 1.1) return { text: `${v.toFixed(3)} pu`, variant: "destructive" as const };
  if (v < 0.95 || v > 1.05) return { text: `${v.toFixed(3)} pu`, variant: "secondary" as const };
  return { text: `${v.toFixed(3)} pu`, variant: "default" as const };
}

function loadingBadge(pct: number) {
  if (pct > 100) return { text: `${pct.toFixed(1)}%`, variant: "destructive" as const };
  if (pct > 80) return { text: `${pct.toFixed(1)}%`, variant: "secondary" as const };
  return { text: `${pct.toFixed(1)}%`, variant: "default" as const };
}

export default function NetworkResultsPanel({ data }: NetworkResultsPanelProps) {
  const [showShortCircuit, setShowShortCircuit] = useState(false);
  const s = data.power_flow_summary;

  // Bus voltage chart data
  const busNames = Object.keys(data.ts_bus_voltages);
  const voltageChartData = useMemo(() => {
    if (busNames.length === 0) return [];
    const len = data.ts_bus_voltages[busNames[0]]?.length ?? 0;
    const result = [];
    for (let i = 0; i < len; i++) {
      const point: Record<string, number> = { hour: i };
      for (const bus of busNames) {
        point[bus] = data.ts_bus_voltages[bus][i];
      }
      result.push(point);
    }
    return result;
  }, [data.ts_bus_voltages, busNames]);

  // Peak-hour branch flows (find the snapshot with highest total loading)
  const peakSnapshot = useMemo(() => {
    if (!s.branch_flows || s.branch_flows.length === 0) return null;
    let best = s.branch_flows[0];
    let bestMax = 0;
    for (const snap of s.branch_flows) {
      const maxLoad = Math.max(...snap.flows.map((f) => f.loading_pct), 0);
      if (maxLoad > bestMax) {
        bestMax = maxLoad;
        best = snap;
      }
    }
    return best;
  }, [s.branch_flows]);

  const scEntries = s.short_circuit ? Object.entries(s.short_circuit) : [];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Section 1: Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Min Voltage</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.min_voltage_pu.toFixed(3)}</span>
              <Badge variant={voltageBadge(s.min_voltage_pu).variant}>
                {s.min_voltage_pu < 0.95 ? "Low" : "OK"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">at {s.worst_voltage_bus}</p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Max Voltage</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.max_voltage_pu.toFixed(3)}</span>
              <Badge variant={voltageBadge(s.max_voltage_pu).variant}>
                {s.max_voltage_pu > 1.05 ? "High" : "OK"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Max Branch Loading</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.max_branch_loading_pct.toFixed(1)}%</span>
              <Badge variant={loadingBadge(s.max_branch_loading_pct).variant}>
                {s.max_branch_loading_pct > 100 ? "Overloaded" : s.max_branch_loading_pct > 80 ? "High" : "OK"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Losses</p>
            <p className="text-2xl font-bold mt-1">
              {s.total_losses_pct.toFixed(2)}%
              <span className="text-sm font-normal text-muted-foreground ml-2">
                ({s.total_losses_kw.toFixed(1)} kW)
              </span>
            </p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Voltage Violations</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.voltage_violations_count}</span>
              {s.voltage_violations_count > 0 && (
                <Badge variant="destructive">!</Badge>
              )}
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Thermal Violations</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.thermal_violations_count}</span>
              {s.thermal_violations_count > 0 && (
                <Badge variant="destructive">!</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Section 2: Bus Voltage Chart */}
      {voltageChartData.length > 0 && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Bus Voltages (per-unit)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={voltageChartData}>
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
                  domain={["auto", "auto"]}
                  tickFormatter={(v) => v.toFixed(2)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  labelFormatter={(v) => `Hour ${v}`}
                  formatter={(value: number) => [value.toFixed(4), ""]}
                />
                <Legend />
                <ReferenceLine y={0.95} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "0.95", fill: "#ef4444", fontSize: 10 }} />
                <ReferenceLine y={1.05} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "1.05", fill: "#ef4444", fontSize: 10 }} />
                {busNames.map((bus, i) => (
                  <Line
                    key={bus}
                    type="monotone"
                    dataKey={bus}
                    name={bus}
                    stroke={LINE_COLORS[i % LINE_COLORS.length]}
                    strokeWidth={1.5}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Section 3: Branch Flows Table */}
      {peakSnapshot && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm">
              Branch Flows — Peak Hour {peakSnapshot.hour}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">Branch</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Power (kW)</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Losses (kW)</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Loading (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {peakSnapshot.flows.map((flow) => {
                    const lb = loadingBadge(flow.loading_pct);
                    return (
                      <tr key={flow.branch_name} className="border-b border-border/50">
                        <td className="py-2 px-3">{flow.branch_name}</td>
                        <td className="py-2 px-3 text-right font-mono">{flow.from_p_kw.toFixed(1)}</td>
                        <td className="py-2 px-3 text-right font-mono">{flow.loss_kw.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right">
                          <Badge variant={lb.variant}>{lb.text}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Section 4: Short Circuit (collapsible) */}
      {scEntries.length > 0 && (
        <Card variant="glass">
          <CardContent className="p-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowShortCircuit(!showShortCircuit)}
              className="w-full justify-start text-sm font-medium"
            >
              {showShortCircuit ? (
                <ChevronDown className="h-4 w-4 mr-2" />
              ) : (
                <ChevronRight className="h-4 w-4 mr-2" />
              )}
              Short Circuit Analysis ({scEntries.length} buses)
            </Button>
            {showShortCircuit && (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Bus</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">I_sc (kA)</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">S_sc (MVA)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scEntries.map(([bus, sc]) => (
                      <tr key={bus} className="border-b border-border/50">
                        <td className="py-2 px-3">{bus}</td>
                        <td className="py-2 px-3 text-right font-mono">{sc.i_sc_ka.toFixed(3)}</td>
                        <td className="py-2 px-3 text-right font-mono">{sc.s_sc_mva.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
