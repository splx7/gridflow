"use client";

import { Badge } from "@/components/ui/badge";
import type { EconomicsResult, TimeseriesResult, NetworkResultsData } from "@/types";
import { AlertTriangle } from "lucide-react";

interface ResultsSummaryProps {
  economics: EconomicsResult;
  timeseries: TimeseriesResult;
  networkData?: NetworkResultsData | null;
}

function MetricCard({
  label,
  value,
  badge,
}: {
  label: string;
  value: string;
  badge?: { text: string; variant: "default" | "secondary" | "destructive" | "outline" };
}) {
  return (
    <div className="rounded-xl border border-border bg-background/40 backdrop-blur px-4 py-3">
      <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-xl font-bold">{value}</span>
        {badge && (
          <Badge variant={badge.variant} className="text-[10px] px-1.5 py-0">
            {badge.text}
          </Badge>
        )}
      </div>
    </div>
  );
}

export default function ResultsSummary({
  economics,
  timeseries,
  networkData,
}: ResultsSummaryProps) {
  const lcoeBadge =
    economics.lcoe < 0.15
      ? { text: "Good", variant: "default" as const }
      : { text: "High", variant: "secondary" as const };

  const reFrac = economics.renewable_fraction * 100;
  const reBadge =
    reFrac > 80
      ? { text: "High RE", variant: "default" as const }
      : undefined;

  const paybackBadge =
    economics.payback_years != null && economics.payback_years < 10
      ? { text: "< 10yr", variant: "default" as const }
      : undefined;

  // Unmet load ratio
  const totalUnmet = timeseries.unmet
    ? timeseries.unmet.reduce((s, v) => s + v, 0)
    : 0;
  const totalLoad = timeseries.load.reduce((s, v) => s + v, 0);
  const unmetPct = totalLoad > 0 ? (totalUnmet / totalLoad) * 100 : 0;
  const unmetBadge =
    unmetPct > 1
      ? { text: `${unmetPct.toFixed(1)}%`, variant: "destructive" as const }
      : { text: `${unmetPct.toFixed(2)}%`, variant: "default" as const };

  // Network violations
  const violations = networkData
    ? (networkData.power_flow_summary.voltage_violations_count ?? 0) +
      (networkData.power_flow_summary.thermal_violations_count ?? 0)
    : 0;

  return (
    <div className="border-b border-border bg-background/30 backdrop-blur px-6 py-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard
          label="LCOE"
          value={`$${economics.lcoe.toFixed(3)}/kWh`}
          badge={lcoeBadge}
        />
        <MetricCard
          label="Net Present Cost"
          value={`$${(economics.npc / 1000).toFixed(0)}k`}
        />
        <MetricCard
          label="RE Fraction"
          value={`${reFrac.toFixed(1)}%`}
          badge={reBadge}
        />
        <MetricCard
          label="Payback"
          value={
            economics.payback_years != null
              ? `${economics.payback_years.toFixed(1)} yr`
              : "N/A"
          }
          badge={paybackBadge}
        />
        <MetricCard
          label="CO₂ Emissions"
          value={`${(economics.co2_emissions_kg / 1000).toFixed(1)} t/yr`}
        />
        <MetricCard
          label="Unmet Load"
          value={`${totalUnmet.toFixed(0)} kWh`}
          badge={unmetBadge}
        />
      </div>
      {violations > 0 && (
        <div className="mt-3 flex items-center gap-2 text-amber-500 text-xs">
          <AlertTriangle className="h-3.5 w-3.5" />
          <span>{violations} network violation{violations !== 1 ? "s" : ""} detected</span>
        </div>
      )}
    </div>
  );
}
