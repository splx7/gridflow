"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { compareSimulations } from "@/lib/api";

interface ComparisonRow {
  simulation_id: string;
  simulation_name: string;
  dispatch_strategy: string;
  npc: number;
  lcoe: number;
  irr: number | null;
  payback_years: number | null;
  renewable_fraction: number;
  co2_emissions_kg: number;
}

export default function ComparePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const { simulations, fetchSimulations } = useProjectStore();

  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ComparisonRow[] | null>(null);
  const [loading, setLoading] = useState(false);

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
      fetchSimulations(projectId);
    }
  }, [isAuthenticated, projectId, fetchSimulations]);

  const completedSims = simulations.filter((s) => s.status === "completed");

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleCompare = async () => {
    if (selected.length < 2) return;
    setLoading(true);
    try {
      const data = await compareSimulations(selected);
      setComparison(data.comparisons);
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const fmt = (v: number, decimals = 1) =>
    v >= 1e6
      ? `${(v / 1e6).toFixed(decimals)}M`
      : v >= 1e3
      ? `${(v / 1e3).toFixed(decimals)}k`
      : v.toFixed(decimals);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center gap-4">
          <button
            onClick={() => router.push(`/projects/${projectId}`)}
            className="text-gray-400 hover:text-white transition-colors text-sm"
          >
            &larr; Project
          </button>
          <h1 className="text-lg font-semibold">Compare Simulations</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto w-full space-y-6">
        {/* Selection */}
        <section>
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
            Select simulations to compare
          </h3>
          {completedSims.length === 0 ? (
            <p className="text-gray-500 text-sm">
              No completed simulations available.
            </p>
          ) : (
            <div className="space-y-2">
              {completedSims.map((sim) => (
                <label
                  key={sim.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selected.includes(sim.id)
                      ? "border-blue-500 bg-blue-900/20"
                      : "border-gray-800 bg-gray-900 hover:border-gray-700"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(sim.id)}
                    onChange={() => toggleSelect(sim.id)}
                    className="rounded"
                  />
                  <span className="text-sm font-medium">{sim.name}</span>
                  <span className="text-xs text-gray-500">
                    {sim.dispatch_strategy}
                  </span>
                </label>
              ))}
            </div>
          )}

          <button
            onClick={handleCompare}
            disabled={selected.length < 2 || loading}
            className="mt-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-6 py-2 text-sm font-medium transition-colors"
          >
            {loading ? "Comparing..." : `Compare (${selected.length} selected)`}
          </button>
        </section>

        {/* Results Table */}
        {comparison && (
          <section>
            <h3 className="text-lg font-semibold mb-4">Comparison Results</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="text-left py-3 px-4 text-gray-400 font-medium">
                      Metric
                    </th>
                    {comparison.map((row) => (
                      <th
                        key={row.simulation_id}
                        className="text-right py-3 px-4 font-medium"
                      >
                        {row.simulation_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      label: "Dispatch Strategy",
                      get: (r: ComparisonRow) => r.dispatch_strategy,
                    },
                    {
                      label: "NPC",
                      get: (r: ComparisonRow) => `$${fmt(r.npc)}`,
                    },
                    {
                      label: "LCOE ($/kWh)",
                      get: (r: ComparisonRow) => `$${r.lcoe.toFixed(3)}`,
                    },
                    {
                      label: "IRR",
                      get: (r: ComparisonRow) =>
                        r.irr != null ? `${(r.irr * 100).toFixed(1)}%` : "N/A",
                    },
                    {
                      label: "Payback",
                      get: (r: ComparisonRow) =>
                        r.payback_years != null
                          ? `${r.payback_years.toFixed(1)} yr`
                          : "N/A",
                    },
                    {
                      label: "RE Fraction",
                      get: (r: ComparisonRow) =>
                        `${(r.renewable_fraction * 100).toFixed(1)}%`,
                    },
                    {
                      label: "CO2 (t/yr)",
                      get: (r: ComparisonRow) =>
                        `${(r.co2_emissions_kg / 1000).toFixed(1)}`,
                    },
                  ].map((metric) => {
                    // Highlight best NPC/LCOE (lowest)
                    const values = comparison.map((r) => metric.get(r));
                    return (
                      <tr
                        key={metric.label}
                        className="border-b border-gray-800/50"
                      >
                        <td className="py-3 px-4 text-gray-400">
                          {metric.label}
                        </td>
                        {comparison.map((row, i) => (
                          <td
                            key={row.simulation_id}
                            className="py-3 px-4 text-right font-mono"
                          >
                            {values[i]}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
