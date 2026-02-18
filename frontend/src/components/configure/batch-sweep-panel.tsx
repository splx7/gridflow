"use client";

import { useState } from "react";
import { toast } from "sonner";
import { createBatch, getErrorMessage } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Trash2, Layers } from "lucide-react";

interface SweepParam {
  name: string;
  param_path: string;
  start: number;
  end: number;
  step: number;
}

interface Props {
  projectId: string;
  weatherDatasetId: string;
  loadProfileId: string;
  onBatchCreated?: () => void;
}

const PRESET_PARAMS = [
  { label: "PV Capacity (kW)", path: "solar_pv.capacity_kw", start: 5, end: 50, step: 5 },
  { label: "Battery Capacity (kWh)", path: "battery.capacity_kwh", start: 10, end: 100, step: 10 },
  { label: "Diesel Size (kW)", path: "diesel_generator.rated_power_kw", start: 5, end: 50, step: 5 },
  { label: "PV Tilt (deg)", path: "solar_pv.tilt_deg", start: 0, end: 45, step: 5 },
];

export default function BatchSweepPanel({ projectId, weatherDatasetId, loadProfileId, onBatchCreated }: Props) {
  const [name, setName] = useState("Parametric Sweep");
  const [strategy, setStrategy] = useState("load_following");
  const [params, setParams] = useState<SweepParam[]>([
    { name: "PV Capacity (kW)", param_path: "solar_pv.capacity_kw", start: 5, end: 30, step: 5 },
  ]);
  const [loading, setLoading] = useState(false);

  const addParam = () => {
    if (params.length >= 3) {
      toast.error("Maximum 3 sweep parameters");
      return;
    }
    const unused = PRESET_PARAMS.find((p) => !params.some((s) => s.param_path === p.path));
    if (unused) {
      setParams([...params, { name: unused.label, param_path: unused.path, start: unused.start, end: unused.end, step: unused.step }]);
    }
  };

  const removeParam = (idx: number) => {
    setParams(params.filter((_, i) => i !== idx));
  };

  const updateParam = (idx: number, field: keyof SweepParam, value: string | number) => {
    const updated = [...params];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    setParams(updated);
  };

  // Compute grid size
  const gridSize = params.reduce((acc, p) => {
    const steps = Math.max(1, Math.floor((p.end - p.start) / p.step) + 1);
    return acc * steps;
  }, 1);

  const handleCreate = async () => {
    if (!weatherDatasetId || !loadProfileId) {
      toast.error("Weather data and load profile required");
      return;
    }
    if (params.length === 0) {
      toast.error("Add at least one sweep parameter");
      return;
    }
    if (gridSize > 100) {
      toast.error(`Grid too large (${gridSize} runs). Maximum is 100.`);
      return;
    }

    setLoading(true);
    try {
      await createBatch(projectId, {
        name,
        dispatch_strategy: strategy,
        weather_dataset_id: weatherDatasetId,
        load_profile_id: loadProfileId,
        sweep_params: params,
      });
      toast.success(`Batch created: ${gridSize} simulations`);
      onBatchCreated?.();
    } catch (err) {
      toast.error("Batch creation failed: " + getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card variant="glass">
      <CardHeader>
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Layers className="h-4 w-4" />
          Parametric Sweep
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label className="text-xs">Batch Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Dispatch Strategy</Label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm"
            >
              <option value="load_following">Load Following</option>
              <option value="cycle_charging">Cycle Charging</option>
              <option value="combined">Combined</option>
              <option value="optimal">Optimal (LP)</option>
            </select>
          </div>
        </div>

        {/* Sweep Parameters */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Sweep Parameters</Label>
            <Button variant="ghost" size="sm" onClick={addParam} disabled={params.length >= 3}>
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add
            </Button>
          </div>
          {params.map((p, idx) => (
            <div key={idx} className="flex items-end gap-2 p-3 rounded-lg border border-border/50 bg-background/30">
              <div className="flex-1 space-y-1">
                <Label className="text-xs">Parameter</Label>
                <select
                  value={p.param_path}
                  onChange={(e) => {
                    const preset = PRESET_PARAMS.find((pr) => pr.path === e.target.value);
                    if (preset) {
                      updateParam(idx, "param_path", preset.path);
                      updateParam(idx, "name", preset.label);
                    }
                  }}
                  className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm"
                >
                  {PRESET_PARAMS.map((pr) => (
                    <option key={pr.path} value={pr.path}>{pr.label}</option>
                  ))}
                </select>
              </div>
              <div className="w-20 space-y-1">
                <Label className="text-xs">Start</Label>
                <Input type="number" value={p.start} onChange={(e) => updateParam(idx, "start", Number(e.target.value))} />
              </div>
              <div className="w-20 space-y-1">
                <Label className="text-xs">End</Label>
                <Input type="number" value={p.end} onChange={(e) => updateParam(idx, "end", Number(e.target.value))} />
              </div>
              <div className="w-20 space-y-1">
                <Label className="text-xs">Step</Label>
                <Input type="number" value={p.step} onChange={(e) => updateParam(idx, "step", Number(e.target.value))} />
              </div>
              <Button variant="ghost" size="sm" className="h-9 w-9 p-0" onClick={() => removeParam(idx)}>
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              </Button>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2">
          <Badge variant="secondary">
            {gridSize} simulation{gridSize !== 1 ? "s" : ""}
          </Badge>
          <Button onClick={handleCreate} disabled={loading || params.length === 0 || gridSize > 100}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Layers className="h-4 w-4 mr-1.5" />}
            {loading ? "Creating..." : "Launch Sweep"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
