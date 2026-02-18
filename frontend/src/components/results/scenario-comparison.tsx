"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface ScoredScenario {
  simulation_id: string;
  simulation_name: string;
  score: number;
  rank: number;
  normalized: Record<string, number>;
  raw: Record<string, number | null>;
}

interface Props {
  scored: ScoredScenario[];
  weights: Record<string, number>;
  onWeightChange: (metric: string, value: number) => void;
}

const METRIC_LABELS: Record<string, string> = {
  npc: "NPC",
  lcoe: "LCOE",
  irr: "IRR",
  payback_years: "Payback",
  renewable_fraction: "RE Fraction",
  co2_emissions_kg: "CO2",
};

const COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--destructive))",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
];

export default function ScenarioComparison({ scored, weights, onWeightChange }: Props) {
  if (!scored.length) return null;

  const metrics = Object.keys(scored[0]?.normalized || {});

  // Build radar data
  const radarData = metrics.map((m) => {
    const point: Record<string, unknown> = { metric: METRIC_LABELS[m] || m };
    scored.forEach((s, i) => {
      point[s.simulation_name] = s.normalized[m];
    });
    return point;
  });

  return (
    <div className="space-y-6">
      {/* Weight Sliders */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Metric Weights
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {metrics.map((m) => (
              <div key={m} className="space-y-1">
                <label className="text-xs text-muted-foreground">
                  {METRIC_LABELS[m] || m}
                </label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="1"
                  value={weights[m] ?? 5}
                  onChange={(e) => onWeightChange(m, Number(e.target.value))}
                  className="w-full accent-[hsl(var(--primary))]"
                />
                <span className="text-xs font-mono">{weights[m] ?? 5}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Ranking Table */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Scenario Ranking
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-muted-foreground font-medium">Rank</th>
                  <th className="text-left py-3 px-4 font-medium">Scenario</th>
                  <th className="text-right py-3 px-4 font-medium">Score</th>
                  {metrics.map((m) => (
                    <th key={m} className="text-right py-3 px-4 font-medium">
                      {METRIC_LABELS[m] || m}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scored.map((s) => (
                  <tr key={s.simulation_id} className="border-b border-border/50">
                    <td className="py-3 px-4">
                      <Badge
                        variant={s.rank === 1 ? "default" : "secondary"}
                        className={s.rank === 1 ? "bg-emerald-500/20 text-emerald-400" : ""}
                      >
                        #{s.rank}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-medium">{s.simulation_name}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold">
                      {(s.score * 100).toFixed(1)}
                    </td>
                    {metrics.map((m) => (
                      <td key={m} className="py-3 px-4 text-right font-mono text-muted-foreground">
                        {s.normalized[m] !== undefined ? (s.normalized[m] * 100).toFixed(0) : "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Radar Chart */}
      {scored.length >= 2 && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Radar Comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="hsl(var(--border))" />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis domain={[0, 1]} tick={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                {scored.slice(0, 5).map((s, i) => (
                  <Radar
                    key={s.simulation_id}
                    name={s.simulation_name}
                    dataKey={s.simulation_name}
                    stroke={COLORS[i % COLORS.length]}
                    fill={COLORS[i % COLORS.length]}
                    fillOpacity={0.1}
                    strokeWidth={2}
                  />
                ))}
              </RadarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
