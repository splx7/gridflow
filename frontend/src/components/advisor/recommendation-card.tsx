"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { AdvisorRecommendation, GoalWeights } from "@/types";
import { Sun, Battery, Fuel, Plug, Check, Zap } from "lucide-react";

function componentIcon(type: string) {
  switch (type) {
    case "solar_pv":
      return <Sun className="h-3.5 w-3.5 text-yellow-400" />;
    case "battery":
      return <Battery className="h-3.5 w-3.5 text-blue-400" />;
    case "diesel_generator":
      return <Fuel className="h-3.5 w-3.5 text-orange-400" />;
    case "inverter":
      return <Zap className="h-3.5 w-3.5 text-cyan-400" />;
    case "grid_connection":
      return <Plug className="h-3.5 w-3.5 text-green-400" />;
    default:
      return null;
  }
}

function componentSummary(type: string, config: Record<string, unknown>) {
  switch (type) {
    case "solar_pv":
      return `${config.capacity_kwp} kWp`;
    case "battery":
      return `${config.capacity_kwh} kWh`;
    case "diesel_generator":
      return `${config.rated_power_kw} kW`;
    case "inverter":
      return `${config.rated_power_kw} kW ${config.mode === "grid_forming" ? "(GFM)" : "(GFL)"}`;
    case "grid_connection":
      return "Connected";
    default:
      return "";
  }
}

function scoreToColor(score: number): string {
  if (score >= 0.7) return "text-emerald-400";
  if (score >= 0.4) return "text-yellow-400";
  return "text-red-400";
}

function goalMatch(rec: AdvisorRecommendation, goals: GoalWeights): number {
  const w = goals;
  const s = rec.goal_scores;
  const total = w.cost + w.renewables + w.reliability + w.roi;
  if (total === 0) return 0;
  return (
    (s.cost * w.cost +
      s.renewables * w.renewables +
      s.reliability * w.reliability +
      s.roi * w.roi) /
    total
  );
}

interface RecommendationCardProps {
  recommendation: AdvisorRecommendation;
  isRecommended: boolean;
  goals: GoalWeights;
  applying: boolean;
  onApply: () => void;
  applyLabel?: string;
}

export default function RecommendationCard({
  recommendation: rec,
  isRecommended,
  goals,
  applying,
  onApply,
  applyLabel,
}: RecommendationCardProps) {
  const est = rec.estimates;

  return (
    <Card
      variant="glass"
      className={`transition-all ${
        isRecommended ? "ring-2 ring-primary" : ""
      }`}
    >
      <CardContent className="p-5 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h4 className="font-semibold text-base">{rec.name}</h4>
            <p className="text-xs text-muted-foreground mt-0.5">
              {rec.description}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge variant="secondary" className="text-xs">
              {rec.best_for}
            </Badge>
            {isRecommended && (
              <Badge className="bg-primary/20 text-primary border-primary/30 text-xs">
                <Check className="h-3 w-3 mr-1" />
                Recommended
              </Badge>
            )}
          </div>
        </div>

        {/* Components */}
        <div className="flex flex-wrap gap-2">
          {rec.components.map((comp, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 bg-secondary/50 rounded-lg px-2.5 py-1.5"
            >
              {componentIcon(comp.component_type)}
              <span className="text-xs font-medium">{comp.name}</span>
              <span className="text-xs text-muted-foreground">
                {componentSummary(comp.component_type, comp.config)}
              </span>
            </div>
          ))}
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-xs text-muted-foreground">Capital Cost</p>
            <p className="text-sm font-semibold">
              ${est.estimated_capital_cost.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">LCOE</p>
            <p className="text-sm font-semibold">
              ${est.estimated_lcoe.toFixed(3)}/kWh
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">RE Fraction</p>
            <p className="text-sm font-semibold">
              {(est.estimated_renewable_fraction * 100).toFixed(0)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">NPC (25yr)</p>
            <p className="text-sm font-semibold">
              ${est.estimated_npc.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Payback</p>
            <p className="text-sm font-semibold">
              {est.estimated_payback_years != null
                ? `${est.estimated_payback_years} yrs`
                : "N/A"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">CO2 Reduction</p>
            <p className="text-sm font-semibold">
              {est.estimated_co2_reduction_pct.toFixed(0)}%
            </p>
          </div>
        </div>

        {/* Goal scores */}
        <div className="flex gap-3 text-xs">
          {(
            [
              ["Cost", rec.goal_scores.cost],
              ["RE", rec.goal_scores.renewables],
              ["Reliability", rec.goal_scores.reliability],
              ["ROI", rec.goal_scores.roi],
            ] as const
          ).map(([label, score]) => (
            <div key={label} className="flex items-center gap-1">
              <span className="text-muted-foreground">{label}:</span>
              <span className={`font-medium ${scoreToColor(score)}`}>
                {(score * 100).toFixed(0)}
              </span>
            </div>
          ))}
        </div>

        {/* Apply button */}
        <Button
          className="w-full"
          variant={isRecommended ? "default" : "outline"}
          disabled={applying}
          onClick={onApply}
        >
          {applying ? "Applying..." : (applyLabel || "Apply This System")}
        </Button>
      </CardContent>
    </Card>
  );
}

export { goalMatch };
