"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import type { GoalWeights } from "@/types";
import {
  DollarSign,
  Leaf,
  Shield,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";

interface Archetype {
  key: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  goals: GoalWeights;
}

const ARCHETYPES: Archetype[] = [
  {
    key: "budget",
    label: "Budget Smart",
    description: "Minimize upfront cost, grid-assisted",
    icon: <DollarSign className="h-5 w-5" />,
    color: "from-emerald-500 to-green-600",
    goals: { cost: 5, renewables: 2, reliability: 2, roi: 4 },
  },
  {
    key: "green",
    label: "Green Champion",
    description: "Maximize renewables, minimize emissions",
    icon: <Leaf className="h-5 w-5" />,
    color: "from-green-500 to-teal-600",
    goals: { cost: 2, renewables: 5, reliability: 3, roi: 3 },
  },
  {
    key: "independent",
    label: "Maximum Independence",
    description: "Full energy autonomy, backup for reliability",
    icon: <Shield className="h-5 w-5" />,
    color: "from-blue-500 to-indigo-600",
    goals: { cost: 1, renewables: 4, reliability: 5, roi: 2 },
  },
];

const GOAL_META = [
  {
    key: "cost" as const,
    label: "Cost Priority",
    description: "Higher = minimize upfront investment",
    icon: <DollarSign className="h-3.5 w-3.5" />,
  },
  {
    key: "renewables" as const,
    label: "Renewables",
    description: "Higher = maximize RE fraction",
    icon: <Leaf className="h-3.5 w-3.5" />,
  },
  {
    key: "reliability" as const,
    label: "Reliability",
    description: "Higher = more backup / autonomy",
    icon: <Shield className="h-3.5 w-3.5" />,
  },
  {
    key: "roi" as const,
    label: "ROI",
    description: "Higher = optimize payback period",
    icon: <TrendingUp className="h-3.5 w-3.5" />,
  },
];

interface GoalSelectorProps {
  goals: GoalWeights;
  gridAvailable: boolean;
  budgetCeiling: number | null;
  activeArchetype: string | null;
  onGoalsChange: (goals: GoalWeights) => void;
  onGridChange: (grid: boolean) => void;
  onBudgetChange: (budget: number | null) => void;
  onArchetypeSelect: (key: string) => void;
  onBack: () => void;
  onNext: () => void;
}

export default function GoalSelector({
  goals,
  gridAvailable,
  budgetCeiling,
  activeArchetype,
  onGoalsChange,
  onGridChange,
  onBudgetChange,
  onArchetypeSelect,
  onBack,
  onNext,
}: GoalSelectorProps) {
  return (
    <div className="space-y-6">
      {/* Archetype presets */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Quick Presets
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {ARCHETYPES.map((arch) => (
            <Card
              key={arch.key}
              variant="glass"
              className={`cursor-pointer transition-all ${
                activeArchetype === arch.key
                  ? "ring-2 ring-primary"
                  : "hover:border-primary/50"
              }`}
              onClick={() => onArchetypeSelect(arch.key)}
            >
              <CardContent className="p-4 text-center">
                <div
                  className={`mx-auto h-10 w-10 rounded-xl bg-gradient-to-br ${arch.color} flex items-center justify-center text-white mb-2`}
                >
                  {arch.icon}
                </div>
                <span className="text-sm font-medium block">{arch.label}</span>
                <p className="text-xs text-muted-foreground mt-1">
                  {arch.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Fine-tune sliders */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Fine-Tune Priorities
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {GOAL_META.map((meta) => (
            <div key={meta.key} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">{meta.icon}</span>
                  <Label className="text-sm">{meta.label}</Label>
                </div>
                <span className="text-xs font-mono text-muted-foreground">
                  {goals[meta.key]}
                </span>
              </div>
              <Slider
                value={[goals[meta.key]]}
                min={1}
                max={5}
                step={1}
                onValueChange={([v]) =>
                  onGoalsChange({ ...goals, [meta.key]: v })
                }
              />
              <p className="text-xs text-muted-foreground">{meta.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Grid toggle + budget */}
      <div className="flex flex-col sm:flex-row gap-4">
        <Card variant="glass" className="flex-1">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <Label className="text-sm">Grid Connection</Label>
              <p className="text-xs text-muted-foreground">
                {gridAvailable ? "Connected to utility grid" : "Off-grid / islanded"}
              </p>
            </div>
            <Switch checked={gridAvailable} onCheckedChange={onGridChange} />
          </CardContent>
        </Card>

        <Card variant="glass" className="flex-1">
          <CardContent className="p-4">
            <Label className="text-sm">Budget Ceiling (optional)</Label>
            <Input
              type="number"
              placeholder="No limit"
              value={budgetCeiling ?? ""}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                onBudgetChange(v > 0 ? v : null);
              }}
              className="mt-1.5"
            />
          </CardContent>
        </Card>
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={onBack}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <Button onClick={onNext}>
          <Sparkles className="h-4 w-4 mr-1" />
          Get Recommendations
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}

export { ARCHETYPES };
