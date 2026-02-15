"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useProjectStore } from "@/stores/project-store";
import { getSimulationStatus } from "@/lib/api";
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

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* New Simulation */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Run Simulation</h3>

        {!canRun ? (
          <div className="bg-yellow-900/20 border border-yellow-800 rounded-lg p-4 text-sm text-yellow-300">
            Upload weather data and a load profile before running simulations.
          </div>
        ) : (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Simulation Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Baseline - Load Following"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Dispatch Strategy</label>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value as DispatchStrategy)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {(Object.keys(DISPATCH_LABELS) as DispatchStrategy[]).map((s) => (
                    <option key={s} value={s}>
                      {DISPATCH_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Weather Dataset</label>
                <select
                  value={weatherId}
                  onChange={(e) => setWeatherId(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {weatherDatasets.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Load Profile</label>
                <select
                  value={loadId}
                  onChange={(e) => setLoadId(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {loadProfiles.map((lp) => (
                    <option key={lp.id} value={lp.id}>
                      {lp.name} ({(lp.annual_kwh / 1000).toFixed(0)} MWh/yr)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={handleRun}
              disabled={running || !name}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg px-6 py-2 text-sm font-medium transition-colors"
            >
              {running ? "Launching..." : "Run Simulation"}
            </button>
          </div>
        )}
      </section>

      {/* Simulation History */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Simulation History</h3>
        {simulations.length === 0 ? (
          <p className="text-gray-500 text-sm">No simulations yet</p>
        ) : (
          <div className="space-y-2">
            {simulations.map((sim) => (
              <div
                key={sim.id}
                className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center justify-between"
              >
                <div>
                  <span className="font-medium text-sm">{sim.name}</span>
                  <span className="text-xs text-gray-500 ml-3">
                    {DISPATCH_LABELS[sim.dispatch_strategy] || sim.dispatch_strategy}
                  </span>
                </div>

                <div className="flex items-center gap-4">
                  {(sim.status === "pending" || sim.status === "running") && (
                    <div className="flex items-center gap-2">
                      <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                      <span className="text-sm text-blue-400">
                        {Math.round(sim.progress)}%
                      </span>
                    </div>
                  )}
                  {sim.status === "completed" && (
                    <button
                      onClick={() => router.push(`/projects/${projectId}/results/${sim.id}`)}
                      className="text-sm text-blue-400 hover:underline"
                    >
                      View Results
                    </button>
                  )}
                  {sim.status === "failed" && (
                    <span className="text-sm text-red-400" title={sim.error_message || ""}>
                      Failed
                    </span>
                  )}
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      sim.status === "completed"
                        ? "bg-green-900/30 text-green-400"
                        : sim.status === "failed"
                        ? "bg-red-900/30 text-red-400"
                        : "bg-blue-900/30 text-blue-400"
                    }`}
                  >
                    {sim.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
