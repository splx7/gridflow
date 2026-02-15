"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useProjectStore } from "@/stores/project-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Play, Loader2, AlertTriangle, BarChart3 } from "lucide-react";
import type { DispatchStrategy } from "@/types";

interface SimulationPanelProps {
  projectId: string;
}

const DISPATCH_LABELS: Record<DispatchStrategy, string> = {
  load_following: "Load Following",
  cycle_charging: "Cycle Charging",
  combined: "Combined (LF + CC)",
  optimal: "Optimal (LP)",
};

export default function SimulationPanel({ projectId }: SimulationPanelProps) {
  const router = useRouter();
  const {
    weatherDatasets,
    loadProfiles,
    simulations,
    createSimulation,
    fetchSimulations,
  } = useProjectStore();

  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState<DispatchStrategy>("load_following");
  const [weatherId, setWeatherId] = useState("");
  const [loadId, setLoadId] = useState("");
  const [running, setRunning] = useState(false);

  // Auto-select first available dataset/profile
  useEffect(() => {
    if (weatherDatasets.length > 0 && !weatherId) {
      setWeatherId(weatherDatasets[0].id);
    }
  }, [weatherDatasets, weatherId]);

  useEffect(() => {
    if (loadProfiles.length > 0 && !loadId) {
      setLoadId(loadProfiles[0].id);
    }
  }, [loadProfiles, loadId]);

  // Poll running simulations
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    const runningSimIds = simulations
      .filter((s) => s.status === "pending" || s.status === "running")
      .map((s) => s.id);

    if (runningSimIds.length > 0) {
      pollingRef.current = setInterval(() => {
        fetchSimulations(projectId);
      }, 3000);
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [simulations, projectId, fetchSimulations]);

  const handleRun = async () => {
    if (!weatherId || !loadId || !name) return;
    setRunning(true);
    try {
      await createSimulation(projectId, {
        name,
        dispatch_strategy: strategy,
        weather_dataset_id: weatherId,
        load_profile_id: loadId,
      });
      setName("");
    } finally {
      setRunning(false);
    }
  };

  const canRun = weatherDatasets.length > 0 && loadProfiles.length > 0;

  const statusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="success">completed</Badge>;
      case "failed":
        return <Badge variant="destructive">failed</Badge>;
      case "running":
        return <Badge variant="info">running</Badge>;
      default:
        return <Badge variant="secondary">pending</Badge>;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* New Simulation */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-5 w-5 text-emerald-400" />
            Run Simulation
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!canRun ? (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />
              <p className="text-sm text-amber-300">
                Upload weather data and a load profile before running
                simulations.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <Label>Simulation Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Baseline - Load Following"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>Dispatch Strategy</Label>
                  <Select
                    value={strategy}
                    onValueChange={(v) => setStrategy(v as DispatchStrategy)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(
                        Object.keys(DISPATCH_LABELS) as DispatchStrategy[]
                      ).map((s) => (
                        <SelectItem key={s} value={s}>
                          {DISPATCH_LABELS[s]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Weather Dataset</Label>
                  <Select value={weatherId} onValueChange={setWeatherId}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {weatherDatasets.map((ds) => (
                        <SelectItem key={ds.id} value={ds.id}>
                          {ds.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Load Profile</Label>
                  <Select value={loadId} onValueChange={setLoadId}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {loadProfiles.map((lp) => (
                        <SelectItem key={lp.id} value={lp.id}>
                          {lp.name} ({(lp.annual_kwh / 1000).toFixed(0)}{" "}
                          MWh/yr)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button
                variant="success"
                onClick={handleRun}
                disabled={running || !name}
              >
                {running ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {running ? "Launching..." : "Run Simulation"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Simulation History */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-400" />
            Simulation History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {simulations.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No simulations yet
            </p>
          ) : (
            <div className="space-y-3">
              {simulations.map((sim) => (
                <Card key={sim.id} variant="outlined">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="font-medium text-sm">
                          {sim.name}
                        </span>
                        <Badge variant="secondary">
                          {DISPATCH_LABELS[sim.dispatch_strategy] ||
                            sim.dispatch_strategy}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        {sim.status === "completed" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              router.push(
                                `/projects/${projectId}/results/${sim.id}`
                              )
                            }
                          >
                            View Results
                          </Button>
                        )}
                        {sim.status === "failed" && sim.error_message && (
                          <span
                            className="text-xs text-destructive max-w-[200px] truncate"
                            title={sim.error_message}
                          >
                            {sim.error_message}
                          </span>
                        )}
                        {statusBadge(sim.status)}
                      </div>
                    </div>

                    {(sim.status === "pending" ||
                      sim.status === "running") && (
                      <div className="mt-3 space-y-1">
                        <Progress value={sim.progress} />
                        <p className="text-xs text-muted-foreground text-right">
                          {Math.round(sim.progress)}%
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
