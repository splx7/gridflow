"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage, uploadLoadProfile } from "@/lib/api";
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
import {
  Play,
  Loader2,
  BarChart3,
  Trash2,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Upload,
} from "lucide-react";
import type { DispatchStrategy } from "@/types";

interface SimulationPanelProps {
  projectId: string;
  onNavigate?: (tab: string) => void;
}

const DISPATCH_INFO: Record<
  DispatchStrategy,
  { label: string; desc: string }
> = {
  load_following: {
    label: "Load Following",
    desc: "PV surplus charges battery. Most common strategy for solar-dominant systems.",
  },
  cycle_charging: {
    label: "Cycle Charging",
    desc: "Generator/grid actively charges battery. Best for diesel backup systems.",
  },
  combined: {
    label: "Combined (LF + CC)",
    desc: "Hybrid of both strategies. Switches based on conditions.",
  },
  optimal: {
    label: "Optimal (LP)",
    desc: "Linear programming for optimal dispatch. Most accurate but slower.",
  },
};

export default function SimulationPanel({
  projectId,
  onNavigate,
}: SimulationPanelProps) {
  const router = useRouter();
  const {
    weatherDatasets,
    loadProfiles,
    components,
    simulations,
    createSimulation,
    fetchSimulations,
    fetchLoadProfiles,
    generateLoadProfile,
    removeSimulation,
  } = useProjectStore();

  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState<DispatchStrategy>("load_following");
  const [weatherId, setWeatherId] = useState("");
  const [loadId, setLoadId] = useState("");
  const [running, setRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generatingScenario, setGeneratingScenario] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        fetchSimulations(projectId).catch(() => {});
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
      toast.success("Simulation started");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setRunning(false);
    }
  };

  const handleUploadLoad = async (file: File) => {
    setUploading(true);
    try {
      const profile = await uploadLoadProfile(projectId, file);
      await fetchLoadProfiles(projectId);
      setLoadId(profile.id);
      toast.success(
        `Uploaded "${file.name}" — ${profile.annual_kwh.toLocaleString()} kWh/yr`
      );
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const handleQuickGenerate = async () => {
    if (!generatingScenario) return;
    setGenerating(true);
    try {
      const profile = await generateLoadProfile(projectId, {
        scenario: generatingScenario,
      });
      setLoadId(profile.id);
      toast.success(`Load profile generated: ${profile.name}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const hasWeather = weatherDatasets.length > 0;
  const hasLoad = loadProfiles.length > 0;
  const hasComponents = components.length > 0;
  const canRun = hasWeather && hasLoad && hasComponents;

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
      {/* Prerequisites Checklist */}
      <Card variant="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Ready to Simulate?
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            {hasWeather ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive shrink-0" />
            )}
            <span className="text-sm">
              Weather data{" "}
              {hasWeather ? (
                <span className="text-muted-foreground">
                  ({weatherDatasets[0].name})
                </span>
              ) : (
                <span className="text-muted-foreground">
                  — auto-fetched from PVGIS
                </span>
              )}
            </span>
          </div>

          <div className="flex items-start gap-2">
            {hasLoad ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
            )}
            <div className="space-y-2">
              <span className="text-sm">
                Load profile{" "}
                {hasLoad ? (
                  <span className="text-muted-foreground">
                    ({loadProfiles[0].name})
                  </span>
                ) : (
                  <span className="text-muted-foreground">— not generated yet</span>
                )}
              </span>
              {!hasLoad && (
                <div className="flex items-center gap-2">
                  <Select
                    value={generatingScenario}
                    onValueChange={setGeneratingScenario}
                  >
                    <SelectTrigger className="h-8 w-48 text-xs">
                      <SelectValue placeholder="Select scenario..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="village_microgrid">Village Microgrid</SelectItem>
                      <SelectItem value="health_clinic">Health Clinic</SelectItem>
                      <SelectItem value="school_campus">School Campus</SelectItem>
                      <SelectItem value="commercial_office">Commercial Office</SelectItem>
                      <SelectItem value="residential_small">Residential (Small)</SelectItem>
                      <SelectItem value="residential_large">Residential (Large)</SelectItem>
                      <SelectItem value="industrial_light">Industrial (Light)</SelectItem>
                      <SelectItem value="agricultural">Agricultural</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    className="h-8 text-xs"
                    disabled={!generatingScenario || generating}
                    onClick={handleQuickGenerate}
                  >
                    {generating ? (
                      <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : null}
                    Generate
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {hasComponents ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive shrink-0" />
            )}
            <span className="text-sm">
              System components{" "}
              {hasComponents ? (
                <span className="text-muted-foreground">
                  ({components.length} configured)
                </span>
              ) : onNavigate ? (
                <Button
                  variant="link"
                  className="h-auto p-0 text-sm"
                  onClick={() => onNavigate("advisor")}
                >
                  Go to Advisor
                </Button>
              ) : (
                <span className="text-muted-foreground">
                  — use Advisor first
                </span>
              )}
            </span>
          </div>

          {canRun && (
            <p className="text-xs text-emerald-400 font-medium pt-1">
              All prerequisites met!
            </p>
          )}
        </CardContent>
      </Card>

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
              <Lightbulb className="h-5 w-5 text-amber-400 shrink-0" />
              <p className="text-sm text-amber-300">
                Complete the prerequisites above before running simulations.
                {!hasComponents &&
                  onNavigate &&
                  " Start with the Advisor to get a recommended system."}
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

              {/* Dispatch Strategy with description */}
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
                      Object.keys(DISPATCH_INFO) as DispatchStrategy[]
                    ).map((s) => (
                      <SelectItem key={s} value={s}>
                        {DISPATCH_INFO[s].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">
                  {DISPATCH_INFO[strategy].desc}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
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
                  <div className="flex items-center justify-between">
                    <Label>Load Profile</Label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadLoad(file);
                        e.target.value = "";
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-auto py-0 px-1 text-xs text-muted-foreground"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                    >
                      <Upload className="h-3 w-3 mr-1" />
                      {uploading ? "Uploading..." : "Upload CSV"}
                    </Button>
                  </div>
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
                          {DISPATCH_INFO[sim.dispatch_strategy]?.label ||
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
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => {
                            if (confirm("Delete this simulation?")) {
                              removeSimulation(projectId, sim.id)
                                .then(() => toast.success("Simulation deleted"))
                                .catch((err) =>
                                  toast.error(getErrorMessage(err))
                                );
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
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
