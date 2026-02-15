"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { getEconomics, getTimeseries } from "@/lib/api";
import type { EconomicsResult, TimeseriesResult } from "@/types";
import TimeseriesChart from "@/components/results/timeseries-chart";
import EconomicsPanel from "@/components/results/economics-panel";
import EnergyBreakdown from "@/components/results/energy-breakdown";

type ResultTab = "timeseries" | "economics" | "breakdown";

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const simId = params.simId as string;
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

  const [economics, setEconomics] = useState<EconomicsResult | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesResult | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>("timeseries");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (isAuthenticated && simId) {
      setLoading(true);
      Promise.all([getEconomics(simId), getTimeseries(simId)])
        .then(([econ, ts]) => {
          setEconomics(econ);
          setTimeseries(ts);
        })
        .finally(() => setLoading(false));
    }
  }, [isAuthenticated, simId]);

  if (isLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const tabs: { key: ResultTab; label: string }[] = [
    { key: "timeseries", label: "Time Series" },
    { key: "economics", label: "Economics" },
    { key: "breakdown", label: "Energy Breakdown" },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push(`/projects/${projectId}`)}
              className="text-gray-400 hover:text-white transition-colors text-sm"
            >
              &larr; Project
            </button>
            <h1 className="text-lg font-semibold">Simulation Results</h1>
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

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "timeseries" && timeseries && (
          <TimeseriesChart data={timeseries} />
        )}
        {activeTab === "economics" && economics && (
          <EconomicsPanel data={economics} />
        )}
        {activeTab === "breakdown" && timeseries && economics && (
          <EnergyBreakdown timeseries={timeseries} economics={economics} />
        )}
      </div>
    </div>
  );
}
