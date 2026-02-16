"use client";

import { useProjectStore } from "@/stores/project-store";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Loader2,
  DollarSign,
  Leaf,
  Clock,
  TrendingDown,
  Zap,
  Activity,
} from "lucide-react";

export default function SystemHealthBar() {
  const { advisorResult, appliedRecommendation, systemHealth, healthLoading } =
    useProjectStore();

  // Only show if advisor was used (appliedRecommendation exists)
  if (!appliedRecommendation && !systemHealth) return null;

  const baseline = appliedRecommendation?.estimates;
  const current = systemHealth?.estimates;
  const warnings = systemHealth?.warnings || [];

  const metrics = [
    {
      label: "CapEx",
      value: current?.estimated_capital_cost,
      baseline: baseline?.estimated_capital_cost,
      format: (v: number) => `$${(v / 1000).toFixed(1)}K`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}$${(d / 1000).toFixed(1)}K`,
      invertColor: true, // increase = bad (red)
      icon: DollarSign,
    },
    {
      label: "LCOE",
      value: current?.estimated_lcoe,
      baseline: baseline?.estimated_lcoe,
      format: (v: number) => `$${v.toFixed(3)}`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}${d.toFixed(3)}`,
      invertColor: true,
      icon: TrendingDown,
    },
    {
      label: "RE",
      value: current?.estimated_renewable_fraction,
      baseline: baseline?.estimated_renewable_fraction,
      format: (v: number) => `${(v * 100).toFixed(0)}%`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}${(d * 100).toFixed(0)}%`,
      invertColor: false, // increase = good (green)
      icon: Leaf,
    },
    {
      label: "NPC",
      value: current?.estimated_npc,
      baseline: baseline?.estimated_npc,
      format: (v: number) => `$${(v / 1000).toFixed(1)}K`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}$${(d / 1000).toFixed(1)}K`,
      invertColor: true,
      icon: Zap,
    },
    {
      label: "Payback",
      value: current?.estimated_payback_years,
      baseline: baseline?.estimated_payback_years,
      format: (v: number) => `${v.toFixed(1)} yr`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}${d.toFixed(1)} yr`,
      invertColor: true,
      icon: Clock,
    },
    {
      label: "CO2\u2193",
      value: current?.estimated_co2_reduction_pct,
      baseline: baseline?.estimated_co2_reduction_pct,
      format: (v: number) => `${v.toFixed(0)}%`,
      deltaFormat: (d: number) => `${d > 0 ? "+" : ""}${d.toFixed(0)}%`,
      invertColor: false,
      icon: Activity,
    },
  ];

  const criticals = warnings.filter((w) => w.level === "critical");
  const warningsList = warnings.filter((w) => w.level === "warning");
  const infos = warnings.filter((w) => w.level === "info");

  return (
    <Card variant="glass" className="mx-4 mt-3 mb-1">
      <CardContent className="p-3">
        {/* Metrics row */}
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-muted-foreground mr-2 shrink-0">
            System Health
          </span>
          {healthLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Evaluating...
            </div>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              {metrics.map((m) => {
                if (m.value == null) return null;
                const delta =
                  m.baseline != null ? m.value - m.baseline : null;
                const Icon = m.icon;

                let deltaColor = "text-muted-foreground";
                if (delta != null && Math.abs(delta) > 0.001) {
                  const isNegativeDelta = delta < 0;
                  const isGood = m.invertColor ? isNegativeDelta : !isNegativeDelta;
                  deltaColor = isGood ? "text-emerald-400" : "text-red-400";
                }

                return (
                  <div
                    key={m.label}
                    className="flex flex-col items-center px-2 py-1 rounded-lg bg-secondary/50 min-w-[64px]"
                  >
                    <div className="flex items-center gap-1">
                      <Icon className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs font-semibold">
                        {m.format(m.value)}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      {m.label}
                    </span>
                    {delta != null && Math.abs(delta) > 0.001 && (
                      <span className={`text-[10px] ${deltaColor}`}>
                        {m.deltaFormat(delta)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="mt-2 space-y-1">
            {criticals.map((w) => (
              <div
                key={w.code}
                className="flex items-start gap-2 text-xs p-1.5 rounded bg-red-500/10 border border-red-500/20"
              >
                <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <span className="text-red-300 font-medium">{w.message}</span>
                  <p className="text-red-300/70 text-[10px] mt-0.5">
                    {w.detail}
                  </p>
                </div>
              </div>
            ))}
            {warningsList.map((w) => (
              <div
                key={w.code}
                className="flex items-start gap-2 text-xs p-1.5 rounded bg-amber-500/10 border border-amber-500/20"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="text-amber-300 font-medium">
                    {w.message}
                  </span>
                  <p className="text-amber-300/70 text-[10px] mt-0.5">
                    {w.detail}
                  </p>
                </div>
              </div>
            ))}
            {infos.map((w) => (
              <div
                key={w.code}
                className="flex items-start gap-2 text-xs p-1.5 rounded bg-blue-500/10 border border-blue-500/20"
              >
                <Info className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <span className="text-blue-300 font-medium">{w.message}</span>
                  <p className="text-blue-300/70 text-[10px] mt-0.5">
                    {w.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
