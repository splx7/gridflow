"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { compareSimulations } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, GitCompare, Loader2, CheckCircle2 } from "lucide-react";

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
      router.replace("/");
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
      setComparison(data.comparisons as unknown as ComparisonRow[]);
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const fmt = (v: number, decimals = 1) =>
    v >= 1e6
      ? `${(v / 1e6).toFixed(decimals)}M`
      : v >= 1e3
      ? `${(v / 1e3).toFixed(decimals)}k`
      : v.toFixed(decimals);

  const metrics = [
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
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-background/50 backdrop-blur shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}`)}
          >
            <ArrowLeft className="h-4 w-4" />
            Project
          </Button>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <GitCompare className="h-5 w-5 text-primary" />
            Compare Simulations
          </h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto w-full space-y-6">
        {/* Selection */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Select simulations to compare
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {completedSims.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No completed simulations available.
              </p>
            ) : (
              <div className="space-y-2">
                {completedSims.map((sim) => (
                  <label
                    key={sim.id}
                    className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                      selected.includes(sim.id)
                        ? "border-primary bg-primary/10"
                        : "border-border bg-background/50 hover:border-muted-foreground/30"
                    }`}
                  >
                    <div
                      className={`h-5 w-5 rounded-md border-2 flex items-center justify-center transition-colors ${
                        selected.includes(sim.id)
                          ? "border-primary bg-primary"
                          : "border-muted-foreground/30"
                      }`}
                    >
                      {selected.includes(sim.id) && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-primary-foreground" />
                      )}
                    </div>
                    <input
                      type="checkbox"
                      checked={selected.includes(sim.id)}
                      onChange={() => toggleSelect(sim.id)}
                      className="sr-only"
                    />
                    <span className="text-sm font-medium">{sim.name}</span>
                    <Badge variant="secondary">
                      {sim.dispatch_strategy}
                    </Badge>
                  </label>
                ))}
              </div>
            )}

            <Button
              onClick={handleCompare}
              disabled={selected.length < 2 || loading}
              className="mt-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <GitCompare className="h-4 w-4" />
              )}
              {loading
                ? "Comparing..."
                : `Compare (${selected.length} selected)`}
            </Button>
          </CardContent>
        </Card>

        {/* Results Table */}
        {comparison && (
          <Card variant="glass">
            <CardHeader>
              <CardTitle>Comparison Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-3 px-4 text-muted-foreground font-medium">
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
                    {metrics.map((metric) => {
                      const values = comparison.map((r) => metric.get(r));
                      return (
                        <tr
                          key={metric.label}
                          className="border-b border-border/50"
                        >
                          <td className="py-3 px-4 text-muted-foreground">
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
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
