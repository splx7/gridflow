"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import SystemDiagram from "@/components/configure/system-diagram";
import ComponentPanel from "@/components/configure/component-panel";
import DataPanel from "@/components/configure/data-panel";
import SimulationPanel from "@/components/simulation/simulation-panel";

type Tab = "configure" | "data" | "simulate" | "results";

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
    weatherDatasets,
    loadProfiles,
    fetchWeather,
    fetchLoadProfiles,
    simulations,
    fetchSimulations,
  } = useProjectStore();

  const [activeTab, setActiveTab] = useState<Tab>("configure");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

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
  }, [isAuthenticated, projectId, setCurrentProject, fetchComponents, fetchWeather, fetchLoadProfiles, fetchSimulations]);

  if (isLoading || !currentProject) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "configure", label: "System Config" },
    { key: "data", label: "Data" },
    { key: "simulate", label: "Simulate" },
    { key: "results", label: "Results" },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-gray-400 hover:text-white transition-colors text-sm"
            >
              &larr; Projects
            </button>
            <h1 className="text-lg font-semibold">{currentProject.name}</h1>
            <span className="text-xs text-gray-500">
              {currentProject.latitude.toFixed(2)}, {currentProject.longitude.toFixed(2)}
            </span>
          </div>
          <div className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {activeTab === "configure" && (
          <>
            <div className="flex-1 relative">
              <SystemDiagram
                components={components}
                onSelect={setSelectedComponentId}
              />
            </div>
            <div className="w-96 border-l border-gray-800 overflow-y-auto">
              <ComponentPanel
                projectId={projectId}
                selectedId={selectedComponentId}
              />
            </div>
          </>
        )}

        {activeTab === "data" && (
          <div className="flex-1 overflow-y-auto p-6">
            <DataPanel projectId={projectId} />
          </div>
        )}

        {activeTab === "simulate" && (
          <div className="flex-1 overflow-y-auto p-6">
            <SimulationPanel projectId={projectId} />
          </div>
        )}

        {activeTab === "results" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Completed Simulations</h3>
                {simulations.filter((s) => s.status === "completed").length >= 2 && (
                  <button
                    onClick={() => router.push(`/projects/${projectId}/compare`)}
                    className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
                  >
                    Compare Scenarios
                  </button>
                )}
              </div>
              {simulations.filter((s) => s.status === "completed").length === 0 ? (
                <p className="text-gray-500 text-sm">No completed simulations yet.</p>
              ) : (
                <div className="space-y-2">
                  {simulations
                    .filter((s) => s.status === "completed")
                    .map((sim) => (
                      <div
                        key={sim.id}
                        className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center justify-between"
                      >
                        <div>
                          <span className="font-medium text-sm">{sim.name}</span>
                          <span className="text-xs text-gray-500 ml-3">{sim.dispatch_strategy}</span>
                        </div>
                        <button
                          onClick={() => router.push(`/projects/${projectId}/results/${sim.id}`)}
                          className="text-sm text-blue-400 hover:underline"
                        >
                          View Results
                        </button>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
