"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { NetworkRecommendation, PowerFlowResult } from "@/types";
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp } from "lucide-react";

interface NetworkRecommendationsBarProps {
  recommendations: NetworkRecommendation[];
  powerFlowResult: PowerFlowResult | null;
}

const LEVEL_CONFIG = {
  error: {
    icon: AlertCircle,
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-400",
    badge: "destructive" as const,
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    text: "text-amber-400",
    badge: "warning" as const,
  },
  info: {
    icon: Info,
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    text: "text-blue-400",
    badge: "info" as const,
  },
};

export default function NetworkRecommendationsBar({
  recommendations,
  powerFlowResult,
}: NetworkRecommendationsBarProps) {
  const [expanded, setExpanded] = useState(false);

  // Combine topology recommendations + PF violations
  const voltageViolations = powerFlowResult?.voltage_violations?.length ?? 0;
  const thermalViolations = powerFlowResult?.thermal_violations?.length ?? 0;
  const errors = recommendations.filter((r) => r.level === "error").length;
  const warnings = recommendations.filter((r) => r.level === "warning").length;

  const hasIssues = errors > 0 || warnings > 0 || voltageViolations > 0 || thermalViolations > 0;

  if (recommendations.length === 0 && !hasIssues) return null;

  return (
    <div className="border-b border-border">
      {/* Summary bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 flex items-center justify-between text-xs hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {voltageViolations > 0 && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
              {voltageViolations} Voltage Violation{voltageViolations > 1 ? "s" : ""}
            </Badge>
          )}
          {thermalViolations > 0 && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
              {thermalViolations} Thermal Overload{thermalViolations > 1 ? "s" : ""}
            </Badge>
          )}
          {errors > 0 && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
              {errors} Error{errors > 1 ? "s" : ""}
            </Badge>
          )}
          {warnings > 0 && (
            <Badge variant="warning" className="text-[10px] px-1.5 py-0">
              {warnings} Warning{warnings > 1 ? "s" : ""}
            </Badge>
          )}
          {!hasIssues && recommendations.length > 0 && (
            <Badge variant="info" className="text-[10px] px-1.5 py-0">
              {recommendations.length} Recommendation{recommendations.length > 1 ? "s" : ""}
            </Badge>
          )}
          <span className="text-muted-foreground">
            {expanded ? "Hide details" : "Show details"}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {/* Expanded recommendation list */}
      {expanded && (
        <div className="px-4 pb-3 space-y-1.5">
          {recommendations.map((rec, i) => {
            const config = LEVEL_CONFIG[rec.level as keyof typeof LEVEL_CONFIG] || LEVEL_CONFIG.info;
            const Icon = config.icon;
            return (
              <div
                key={i}
                className={`flex items-start gap-2 rounded px-3 py-2 text-xs border ${config.bg} ${config.border}`}
              >
                <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${config.text}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {rec.code}
                    </span>
                  </div>
                  <p className="mt-0.5">{rec.message}</p>
                  <p className="text-muted-foreground mt-0.5">{rec.suggestion}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
