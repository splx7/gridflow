"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import SystemDiagram from "@/components/configure/system-diagram";
import NetworkDiagram from "@/components/configure/network-diagram";
import ComponentPanel from "@/components/configure/component-panel";
import SimulationPanel from "@/components/simulation/simulation-panel";
import AdvisorWizard from "@/components/advisor/advisor-wizard";
import SystemHealthBar from "@/components/configure/system-health-bar";
import {
  ArrowLeft,
  Settings2,
  Play,
  BarChart3,
  MapPin,
  Zap,
  LogOut,
  LogIn,
  Lightbulb,
  CheckCircle2,
  AlertTriangle,
  Network,
} from "lucide-react";

const LocationPicker = dynamic(
  () => import("@/components/configure/location-picker"),
  { ssr: false }
);

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { user, isAuthenticated, isLoading, checkAuth, logout } = useAuthStore();
  const {
    currentProject,
    setCurrentProject,
    updateProject,
    components,
    fetchComponents,
    fetchWeather,
    fetchLoadProfiles,
    loadProfiles,
    simulations,
    fetchSimulations,
    weatherDatasets,
    fetchPVGIS,
    systemHealth,
    fetchBuses,
    fetchBranches,
    autoGenerateNetwork,
    autoGenerateLoading,
    runPowerFlow,
  } = useProjectStore();

  const [activeTab, setActiveTab] = useState<string>("advisor");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(
    null
  );
  const [showSettings, setShowSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    name: "",
    description: "",
    latitude: 0,
    longitude: 0,
    lifetime_years: 25,
    discount_rate: 0.08,
  });
  const [savingSettings, setSavingSettings] = useState(false);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated && projectId) {
      const onErr = (err: unknown) => toast.error(getErrorMessage(err));
      import("@/lib/api").then(({ getProject }) => {
        getProject(projectId).then(setCurrentProject).catch(onErr);
      });
      fetchComponents(projectId).catch(onErr);
      fetchWeather(projectId).catch(onErr);
      fetchLoadProfiles(projectId).catch(onErr);
      fetchSimulations(projectId).catch(onErr);
      fetchBuses(projectId).catch(() => {});
      fetchBranches(projectId).catch(() => {});
    }
  }, [
    isAuthenticated,
    projectId,
    setCurrentProject,
    fetchComponents,
    fetchWeather,
    fetchLoadProfiles,
    fetchSimulations,
    fetchBuses,
    fetchBranches,
  ]);

  // Auto-fetch PVGIS weather data if none exists (fallback for dashboard auto-fetch)
  useEffect(() => {
    if (currentProject && weatherDatasets.length === 0 && isAuthenticated) {
      fetchPVGIS(projectId).catch(() => {
        // Silently ignore — weather auto-fetched on project creation
      });
    }
  }, [currentProject, weatherDatasets.length, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // Default to advisor tab for new projects (no components), configure for existing
  useEffect(() => {
    if (currentProject && components.length > 0 && activeTab === "advisor") {
      setActiveTab("configure");
    }
  }, [currentProject, components.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading || !currentProject) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  const completedSims = simulations.filter((s) => s.status === "completed");
  const advisorDone = components.length > 0;
  const hasWarnings = systemHealth?.warnings?.some((w) => w.level === "critical" || w.level === "warning");
  const simulateReady = weatherDatasets.length > 0 && loadProfiles.length > 0 && components.length > 0;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-lg shrink-0 sticky top-0 z-40">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/dashboard")}
            >
              <ArrowLeft className="h-4 w-4" />
              Projects
            </Button>
            <div className="flex items-center gap-3">
              <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                <Zap className="h-3.5 w-3.5 text-white" />
              </div>
              <h1 className="text-lg font-semibold">{currentProject.name}</h1>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3" />
              {currentProject.latitude.toFixed(2)},{" "}
              {currentProject.longitude.toFixed(2)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSettingsForm({
                  name: currentProject.name,
                  description: currentProject.description || "",
                  latitude: currentProject.latitude,
                  longitude: currentProject.longitude,
                  lifetime_years: currentProject.lifetime_years,
                  discount_rate: currentProject.discount_rate,
                });
                setShowSettings(true);
              }}
            >
              <Settings2 className="h-4 w-4" />
            </Button>
            {user && !user.email.endsWith("@gridflow.local") ? (
              <>
                <span className="text-sm text-muted-foreground">{user.email}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                >
                  <LogOut className="h-4 w-4 mr-1" />
                  Log out
                </Button>
              </>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/")}
              >
                <LogIn className="h-4 w-4 mr-1" />
                Sign In
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Tabs Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <div className="border-b border-border bg-background/50 px-4">
          <TabsList className="bg-transparent h-auto p-0 gap-0">
            <TabsTrigger
              value="advisor"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Lightbulb className="h-4 w-4 mr-2" />
              Advisor
              {advisorDone && (
                <CheckCircle2 className="h-3.5 w-3.5 ml-1.5 text-emerald-400" />
              )}
            </TabsTrigger>
            <TabsTrigger
              value="configure"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Settings2 className="h-4 w-4 mr-2" />
              Configure
              {hasWarnings && (
                <AlertTriangle className="h-3.5 w-3.5 ml-1.5 text-amber-400" />
              )}
            </TabsTrigger>
            <TabsTrigger
              value="simulate"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Play className="h-4 w-4 mr-2" />
              Simulate
              {simulateReady && (
                <CheckCircle2 className="h-3.5 w-3.5 ml-1.5 text-emerald-400" />
              )}
            </TabsTrigger>
            <TabsTrigger
              value="results"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <BarChart3 className="h-4 w-4 mr-2" />
              Results
              {completedSims.length > 0 && (
                <Badge variant="info" className="ml-2">
                  {completedSims.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="advisor" className="flex-1 overflow-y-auto p-6 mt-0">
          <AdvisorWizard
            projectId={projectId}
            onApplied={() => setActiveTab("configure")}
          />
        </TabsContent>

        <TabsContent value="configure" className="flex-1 flex flex-col overflow-hidden mt-0">
          {components.length === 0 ? (
            <div className="flex-1 flex items-center justify-center p-6">
              <Card variant="glass" className="max-w-md w-full">
                <CardContent className="py-12 text-center space-y-4">
                  <Settings2 className="h-10 w-10 text-muted-foreground mx-auto" />
                  <div>
                    <h3 className="text-lg font-semibold">System not configured yet</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Use the Advisor to get a recommended system configuration.
                    </p>
                  </div>
                  <Button onClick={() => setActiveTab("advisor")}>
                    <Lightbulb className="h-4 w-4 mr-2" />
                    Go to Advisor
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : currentProject.network_mode === "multi_bus" ? (
            <>
              <SystemHealthBar />
              <NetworkDiagram
                projectId={projectId}
                components={components}
              />
            </>
          ) : (
            <>
              <SystemHealthBar />
              <div className="flex-1 flex overflow-hidden">
                <div className="flex-1 relative">
                  <SystemDiagram
                    components={components}
                    onSelect={setSelectedComponentId}
                  />
                  {/* Enable Network Mode button — auto-generates SLD */}
                  <div className="absolute bottom-4 left-4 z-10">
                    <Button
                      variant="outline"
                      size="sm"
                      className="bg-background/80 backdrop-blur-sm"
                      disabled={autoGenerateLoading}
                      onClick={async () => {
                        try {
                          const result = await autoGenerateNetwork(projectId);
                          toast.success(
                            `SLD generated: ${result.buses.length} buses, ${result.branches.length} branches`
                          );
                          // Run power flow in background
                          runPowerFlow(projectId).catch(() => {});
                        } catch (err) {
                          toast.error(getErrorMessage(err));
                        }
                      }}
                    >
                      {autoGenerateLoading ? (
                        <>
                          <div className="h-4 w-4 mr-2 animate-spin border-2 border-current border-t-transparent rounded-full" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Network className="h-4 w-4 mr-2" />
                          Enable Network Mode
                        </>
                      )}
                    </Button>
                  </div>
                </div>
                <div className="w-96 border-l border-border overflow-y-auto">
                  <ComponentPanel
                    projectId={projectId}
                    selectedId={selectedComponentId}
                    onSelect={setSelectedComponentId}
                  />
                </div>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="simulate" className="flex-1 overflow-y-auto p-6 mt-0">
          <SimulationPanel projectId={projectId} onNavigate={setActiveTab} />
        </TabsContent>

        <TabsContent value="results" className="flex-1 overflow-y-auto p-6 mt-0">
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Completed Simulations</h3>
              {completedSims.length >= 2 && (
                <Button
                  onClick={() =>
                    router.push(`/projects/${projectId}/compare`)
                  }
                >
                  Compare Scenarios
                </Button>
              )}
            </div>
            {completedSims.length === 0 ? (
              <Card variant="glass">
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground text-sm">
                    No completed simulations yet. Run a simulation first.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {completedSims.map((sim) => (
                  <Card
                    key={sim.id}
                    variant="glass"
                    className="card-lift cursor-pointer"
                    onClick={() =>
                      router.push(
                        `/projects/${projectId}/results/${sim.id}`
                      )
                    }
                  >
                    <CardContent className="p-4 flex items-center justify-between">
                      <div>
                        <span className="font-medium text-sm">
                          {sim.name}
                        </span>
                        <Badge variant="secondary" className="ml-3">
                          {sim.dispatch_strategy.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <Badge variant="success">completed</Badge>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Project Settings Dialog */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Project Settings</DialogTitle>
            <DialogDescription>
              Update project name, location, and economic parameters.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>Project Name</Label>
              <Input
                value={settingsForm.name}
                onChange={(e) =>
                  setSettingsForm((f) => ({ ...f, name: e.target.value }))
                }
              />
            </div>

            <div>
              <Label>Description</Label>
              <Input
                value={settingsForm.description}
                onChange={(e) =>
                  setSettingsForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Optional project description"
              />
            </div>

            <div>
              <Label>Location</Label>
              <LocationPicker
                latitude={settingsForm.latitude}
                longitude={settingsForm.longitude}
                onChange={(lat, lng) =>
                  setSettingsForm((f) => ({ ...f, latitude: lat, longitude: lng }))
                }
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Project Lifetime (years)</Label>
                <Input
                  type="number"
                  value={settingsForm.lifetime_years}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      lifetime_years: parseInt(e.target.value) || 0,
                    }))
                  }
                />
              </div>
              <div>
                <Label>Discount Rate (%)</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={parseFloat((settingsForm.discount_rate * 100).toFixed(2))}
                  onChange={(e) =>
                    setSettingsForm((f) => ({
                      ...f,
                      discount_rate: (parseFloat(e.target.value) || 0) / 100,
                    }))
                  }
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowSettings(false)}>
              Cancel
            </Button>
            <Button
              disabled={!settingsForm.name || savingSettings}
              onClick={async () => {
                setSavingSettings(true);
                try {
                  await updateProject(projectId, {
                    name: settingsForm.name,
                    description: settingsForm.description || undefined,
                    latitude: settingsForm.latitude,
                    longitude: settingsForm.longitude,
                    lifetime_years: settingsForm.lifetime_years,
                    discount_rate: settingsForm.discount_rate,
                  });
                  toast.success("Project updated");
                  setShowSettings(false);
                } catch (err) {
                  toast.error(getErrorMessage(err));
                } finally {
                  setSavingSettings(false);
                }
              }}
            >
              {savingSettings ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
