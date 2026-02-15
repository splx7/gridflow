"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { EconomicsResult } from "@/types";

interface EconomicsPanelProps {
  data: EconomicsResult;
}

const PIE_COLORS = [
  "#3b82f6",
  "#f59e0b",
  "#10b981",
  "#a855f7",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#6366f1",
];

export default function EconomicsPanel({ data }: EconomicsPanelProps) {
  const metrics = [
    {
      label: "Net Present Cost",
      value: `$${(data.npc / 1000).toFixed(0)}k`,
      description: "Total lifecycle cost discounted to present",
    },
    {
      label: "LCOE",
      value: `$${data.lcoe.toFixed(3)}/kWh`,
      description: "Levelized cost of energy",
    },
    {
      label: "IRR",
      value: data.irr != null ? `${(data.irr * 100).toFixed(1)}%` : "N/A",
      description: "Internal rate of return vs grid-only",
    },
    {
      label: "Payback",
      value:
        data.payback_years != null
          ? `${data.payback_years.toFixed(1)} years`
          : "N/A",
      description: "Simple payback period",
    },
    {
      label: "Renewable Fraction",
      value: `${(data.renewable_fraction * 100).toFixed(1)}%`,
      description: "Energy served from renewables",
    },
    {
      label: "CO2 Emissions",
      value: `${(data.co2_emissions_kg / 1000).toFixed(1)} t/yr`,
      description: "Annual CO2 emissions",
    },
  ];

  const costItems = Object.entries(data.cost_breakdown).sort(
    ([, a], [, b]) => (b as number) - (a as number)
  );
  const totalCost = costItems.reduce((sum, [, v]) => sum + (v as number), 0);

  const pieData = costItems.map(([key, value]) => ({
    name: key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase()),
    value: value as number,
  }));

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {metrics.map((m) => (
          <Card key={m.label} variant="glass">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                {m.label}
              </p>
              <p className="text-2xl font-bold mt-1">{m.value}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {m.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Cost Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card variant="glass">
          <CardHeader>
            <CardTitle>Cost Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {costItems.map(([key, value]) => {
              const pct =
                totalCost > 0
                  ? ((value as number) / totalCost) * 100
                  : 0;
              return (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">
                      {key
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <span className="font-medium">
                      ${((value as number) / 1000).toFixed(1)}k
                    </span>
                  </div>
                  <Progress value={pct} className="h-2" />
                </div>
              );
            })}
            <div className="mt-4 pt-4 border-t border-border flex justify-between text-sm font-semibold">
              <span>Total NPC</span>
              <span>${(data.npc / 1000).toFixed(0)}k</span>
            </div>
          </CardContent>
        </Card>

        {/* Pie Chart */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle>Cost Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {pieData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) =>
                    `$${(value / 1000).toFixed(1)}k`
                  }
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {pieData.map((item, i) => (
                <div key={item.name} className="flex items-center gap-2 text-xs">
                  <div
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{
                      backgroundColor: PIE_COLORS[i % PIE_COLORS.length],
                    }}
                  />
                  <span className="text-muted-foreground truncate">
                    {item.name}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
