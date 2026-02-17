"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const CHART_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#a855f7", "#ef4444",
  "#8b5cf6", "#ec4899", "#6366f1",
];

interface ComparisonRow {
  simulation_id: string;
  simulation_name: string;
  dispatch_strategy: string;
  npc: number;
  lcoe: number;
  irr: number | null;
  payback_years: number | null;
  renewable_fraction: number;
  co2_emissions_kg: number;
  cost_breakdown?: Record<string, number>;
}

interface ComparisonChartProps {
  data: ComparisonRow[];
}

export default function ComparisonChart({ data }: ComparisonChartProps) {
  // Radar chart: normalize 5 axes to 0-100, 100 = best
  const radarData = useMemo(() => {
    if (data.length === 0) return [];

    const maxNPC = Math.max(...data.map((d) => d.npc));
    const maxLCOE = Math.max(...data.map((d) => d.lcoe));
    const maxIRR = Math.max(...data.map((d) => d.irr ?? 0), 0.001);
    const maxRE = Math.max(...data.map((d) => d.renewable_fraction), 0.001);
    const maxCO2 = Math.max(...data.map((d) => d.co2_emissions_kg), 1);

    const axes = [
      {
        axis: "Cost Efficiency",
        ...Object.fromEntries(
          data.map((d) => [d.simulation_name, maxNPC > 0 ? ((1 - d.npc / maxNPC) * 100) : 50])
        ),
      },
      {
        axis: "Energy Cost",
        ...Object.fromEntries(
          data.map((d) => [d.simulation_name, maxLCOE > 0 ? ((1 - d.lcoe / maxLCOE) * 100) : 50])
        ),
      },
      {
        axis: "Return",
        ...Object.fromEntries(
          data.map((d) => [d.simulation_name, ((d.irr ?? 0) / maxIRR) * 100])
        ),
      },
      {
        axis: "Renewables",
        ...Object.fromEntries(
          data.map((d) => [d.simulation_name, (d.renewable_fraction / maxRE) * 100])
        ),
      },
      {
        axis: "Low Carbon",
        ...Object.fromEntries(
          data.map((d) => [d.simulation_name, maxCO2 > 0 ? ((1 - d.co2_emissions_kg / maxCO2) * 100) : 50])
        ),
      },
    ];

    return axes;
  }, [data]);

  // Cost breakdown bar chart
  const barData = useMemo(() => {
    const allCategories = new Set<string>();
    for (const row of data) {
      if (row.cost_breakdown) {
        for (const key of Object.keys(row.cost_breakdown)) {
          allCategories.add(key);
        }
      }
    }
    return Array.from(allCategories).map((cat) => {
      const point: Record<string, string | number> = {
        category: cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      };
      for (const row of data) {
        point[row.simulation_name] =
          row.cost_breakdown?.[cat] != null
            ? Math.round(row.cost_breakdown[cat] / 1000)
            : 0;
      }
      return point;
    });
  }, [data]);

  const hasCostData = barData.length > 0;

  return (
    <div className="space-y-6">
      {/* Radar Chart */}
      {radarData.length > 0 && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm">Multi-Axis Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke="hsl(217.2 32.6% 17.5%)" />
                <PolarAngleAxis
                  dataKey="axis"
                  tick={{ fill: "hsl(215 20.2% 65.1%)", fontSize: 11 }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={{ fill: "hsl(215 20.2% 65.1%)", fontSize: 10 }}
                />
                {data.map((row, i) => (
                  <Radar
                    key={row.simulation_id}
                    name={row.simulation_name}
                    dataKey={row.simulation_name}
                    stroke={CHART_COLORS[i % CHART_COLORS.length]}
                    fill={CHART_COLORS[i % CHART_COLORS.length]}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                ))}
                <Legend />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => `${value.toFixed(0)}`}
                />
              </RadarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Cost Breakdown Bar Chart */}
      {hasCostData && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm">Cost Breakdown Comparison ($k)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2 32.6% 17.5%)" />
                <XAxis
                  dataKey="category"
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  angle={-30}
                  textAnchor="end"
                  height={80}
                />
                <YAxis
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  tickFormatter={(v) => `$${v}k`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [`$${value}k`, ""]}
                />
                <Legend />
                {data.map((row, i) => (
                  <Bar
                    key={row.simulation_id}
                    dataKey={row.simulation_name}
                    fill={CHART_COLORS[i % CHART_COLORS.length]}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
