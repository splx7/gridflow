"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { getEconomics, getErrorMessage, getTimeseries } from "@/lib/api";
import type { EconomicsResult, TimeseriesResult } from "@/types";
import TimeseriesChart from "@/components/results/timeseries-chart";
import EconomicsPanel from "@/components/results/economics-panel";
import EnergyBreakdown from "@/components/results/energy-breakdown";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Activity, DollarSign, BarChart3, Loader2 } from "lucide-react";

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const simId = params.simId as string;
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

  const [economics, setEconomics] = useState<EconomicsResult | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (isAuthenticated && simId) {
      setLoading(true);
      const fetchData = async () => {
        const [econResult, tsResult] = await Promise.allSettled([
          getEconomics(simId),
          getTimeseries(simId),
        ]);
        if (econResult.status === "fulfilled") setEconomics(econResult.value);
        else toast.error("Failed to load economics: " + getErrorMessage(econResult.reason));
        if (tsResult.status === "fulfilled") setTimeseries(tsResult.value);
        else toast.error("Failed to load timeseries: " + getErrorMessage(tsResult.reason));
        setLoading(false);
      };
      fetchData();
    }
  }, [isAuthenticated, simId]);

  if (isLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-background/50 backdrop-blur shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push(`/projects/${projectId}`)}
            >
              <ArrowLeft className="h-4 w-4" />
              Project
            </Button>
            <h1 className="text-lg font-semibold">Simulation Results</h1>
          </div>
        </div>
      </header>

      <Tabs defaultValue="timeseries" className="flex-1 flex flex-col">
        <div className="border-b border-border bg-background/30 backdrop-blur px-4">
          <TabsList className="bg-transparent h-auto p-0 gap-1">
            <TabsTrigger
              value="timeseries"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg px-4 py-1.5 text-sm"
            >
              <Activity className="h-4 w-4 mr-1.5" />
              Time Series
            </TabsTrigger>
            <TabsTrigger
              value="economics"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg px-4 py-1.5 text-sm"
            >
              <DollarSign className="h-4 w-4 mr-1.5" />
              Economics
            </TabsTrigger>
            <TabsTrigger
              value="breakdown"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg px-4 py-1.5 text-sm"
            >
              <BarChart3 className="h-4 w-4 mr-1.5" />
              Energy Breakdown
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <TabsContent value="timeseries" className="mt-0">
            {timeseries && <TimeseriesChart data={timeseries} />}
          </TabsContent>
          <TabsContent value="economics" className="mt-0">
            {economics && <EconomicsPanel data={economics} />}
          </TabsContent>
          <TabsContent value="breakdown" className="mt-0">
            {timeseries && economics && (
              <EnergyBreakdown timeseries={timeseries} economics={economics} />
            )}
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
