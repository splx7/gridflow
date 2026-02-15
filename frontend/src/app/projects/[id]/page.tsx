"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import SystemDiagram from "@/components/configure/system-diagram";
import ComponentPanel from "@/components/configure/component-panel";
import DataPanel from "@/components/configure/data-panel";
import SimulationPanel from "@/components/simulation/simulation-panel";
import {
  ArrowLeft,
  Settings2,
  Database,
  Play,
  BarChart3,
  MapPin,
  Zap,
} from "lucide-react";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const {
    currentProject,
    setCurrentProject,
    components,
    fetchComponents,
    fetchWeather,
    fetchLoadProfiles,
    simulations,
    fetchSimulations,
  } = useProjectStore();

  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(
    null
  );

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated && projectId) {
      import("@/lib/api").then(({ getProject }) => {
        getProject(projectId).then(setCurrentProject);
      });
      fetchComponents(projectId);
      fetchWeather(projectId);
      fetchLoadProfiles(projectId);
      fetchSimulations(projectId);
    }
  }, [
    isAuthenticated,
    projectId,
    setCurrentProject,
    fetchComponents,
    fetchWeather,
    fetchLoadProfiles,
    fetchSimulations,
  ]);

  if (isLoading || !currentProject) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  const completedSims = simulations.filter((s) => s.status === "completed");

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
        </div>
      </header>

      {/* Tabs Content */}
      <Tabs defaultValue="configure" className="flex-1 flex flex-col">
        <div className="border-b border-border bg-background/50 px-4">
          <TabsList className="bg-transparent h-auto p-0 gap-0">
            <TabsTrigger
              value="configure"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Settings2 className="h-4 w-4 mr-2" />
              System Config
            </TabsTrigger>
            <TabsTrigger
              value="data"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Database className="h-4 w-4 mr-2" />
              Data
            </TabsTrigger>
            <TabsTrigger
              value="simulate"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none px-4 py-3"
            >
              <Play className="h-4 w-4 mr-2" />
              Simulate
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

        <TabsContent value="configure" className="flex-1 flex overflow-hidden mt-0">
          <div className="flex-1 relative">
            <SystemDiagram
              components={components}
              onSelect={setSelectedComponentId}
            />
          </div>
          <div className="w-96 border-l border-border overflow-y-auto">
            <ComponentPanel
              projectId={projectId}
              selectedId={selectedComponentId}
              onSelect={setSelectedComponentId}
            />
          </div>
        </TabsContent>

        <TabsContent value="data" className="flex-1 overflow-y-auto p-6 mt-0">
          <DataPanel projectId={projectId} />
        </TabsContent>

        <TabsContent value="simulate" className="flex-1 overflow-y-auto p-6 mt-0">
          <SimulationPanel projectId={projectId} />
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
    </div>
  );
}
