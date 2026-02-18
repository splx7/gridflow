"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import {
  getEconomics,
  getErrorMessage,
  getNetworkResults,
  getSensitivityResults,
  getTimeseries,
  listSimulations,
} from "@/lib/api";
import type {
  EconomicsResult,
  NetworkResultsData,
  SensitivityResult,
  Simulation,
  TimeseriesResult,
} from "@/types";
import TimeseriesChart from "@/components/results/timeseries-chart";
import EconomicsPanel from "@/components/results/economics-panel";
import EnergyBreakdown from "@/components/results/energy-breakdown";
import ResultsSummary from "@/components/results/results-summary";
import NetworkResultsPanel from "@/components/results/network-results-panel";
import SensitivityPanel from "@/components/results/sensitivity-panel";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ArrowLeft,
  Activity,
  DollarSign,
  BarChart3,
  Network,
  Download,
  Loader2,
  SlidersHorizontal,
  FileText,
} from "lucide-react";
import { HelpDrawer } from "@/components/ui/help-drawer";
import { ResultsSkeleton } from "@/components/ui/skeleton";
import {
  exportTimeseriesCSV,
  exportEconomicsCSV,
  exportNetworkCSV,
  exportSensitivityCSV,
} from "@/lib/export";
import { downloadPdfReport, getErrorMessage as getErrMsg } from "@/lib/api";

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const simId = params.simId as string;
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

  const [economics, setEconomics] = useState<EconomicsResult | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesResult | null>(null);
  const [networkData, setNetworkData] = useState<NetworkResultsData | null>(null);
  const [sensitivityData, setSensitivityData] = useState<SensitivityResult | null>(null);
  const [simMeta, setSimMeta] = useState<Simulation | null>(null);
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
        const [econResult, tsResult, netResult, sensResult, simsResult] = await Promise.allSettled([
          getEconomics(simId),
          getTimeseries(simId),
          getNetworkResults(simId),
          getSensitivityResults(simId),
          listSimulations(projectId),
        ]);

        if (econResult.status === "fulfilled") setEconomics(econResult.value);
        else toast.error("Failed to load economics: " + getErrorMessage(econResult.reason));

        if (tsResult.status === "fulfilled") setTimeseries(tsResult.value);
        else toast.error("Failed to load timeseries: " + getErrorMessage(tsResult.reason));

        if (netResult.status === "fulfilled") {
          setNetworkData(netResult.value as NetworkResultsData);
        }
        // 404 is expected for single_bus — silently ignore

        if (sensResult.status === "fulfilled") {
          setSensitivityData(sensResult.value);
        }
        // 404 is expected when sensitivity hasn't been run yet

        if (simsResult.status === "fulfilled") {
          const match = simsResult.value.find((s) => s.id === simId);
          if (match) setSimMeta(match);
        }

        setLoading(false);
      };
      fetchData();
    }
  }, [isAuthenticated, simId, projectId]);

  if (isLoading || loading) {
    return <ResultsSkeleton />;
  }

  const strategyLabel = simMeta?.dispatch_strategy
    ?.replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
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
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold">
                {simMeta?.name || "Simulation Results"}
              </h1>
              {strategyLabel && (
                <Badge variant="secondary" className="text-xs">
                  {strategyLabel}
                </Badge>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
          <HelpDrawer />
          {/* Export Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-1.5" />
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={async () => {
                  try {
                    const blob = await downloadPdfReport(simId);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `report_${simId}.pdf`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    toast.error("PDF generation failed: " + getErrMsg(err));
                  }
                }}
              >
                <FileText className="h-4 w-4 mr-2" />
                PDF Report
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => timeseries && exportTimeseriesCSV(timeseries, simId)}
                disabled={!timeseries}
              >
                Timeseries CSV
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => economics && exportEconomicsCSV(economics, simId)}
                disabled={!economics}
              >
                Economics CSV
              </DropdownMenuItem>
              {networkData && (
                <DropdownMenuItem
                  onClick={() => exportNetworkCSV(networkData, simId)}
                >
                  Network CSV
                </DropdownMenuItem>
              )}
              {sensitivityData && (
                <DropdownMenuItem
                  onClick={() => exportSensitivityCSV(sensitivityData, simId)}
                >
                  Sensitivity CSV
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Summary Header */}
      {economics && timeseries && (
        <ResultsSummary
          economics={economics}
          timeseries={timeseries}
          networkData={networkData}
        />
      )}

      {/* Tabs */}
      <Tabs defaultValue="timeseries" className="flex-1 flex flex-col">
        <div className="border-b border-border bg-background/30 backdrop-blur px-4 overflow-x-auto">
          <TabsList className="bg-transparent h-auto p-0 gap-1 w-max min-w-full">
            <TabsTrigger
              value="timeseries"
              className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-4 py-2.5 text-sm"
            >
              <Activity className="h-4 w-4 mr-1.5" />
              Time Series
            </TabsTrigger>
            <TabsTrigger
              value="economics"
              className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-4 py-2.5 text-sm"
            >
              <DollarSign className="h-4 w-4 mr-1.5" />
              Economics
            </TabsTrigger>
            <TabsTrigger
              value="breakdown"
              className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-4 py-2.5 text-sm"
            >
              <BarChart3 className="h-4 w-4 mr-1.5" />
              Energy Breakdown
            </TabsTrigger>
            {networkData && (
              <TabsTrigger
                value="network"
                className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-4 py-2.5 text-sm"
              >
                <Network className="h-4 w-4 mr-1.5" />
                Network
              </TabsTrigger>
            )}
            <TabsTrigger
              value="sensitivity"
              className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none rounded-none px-4 py-2.5 text-sm"
            >
              <SlidersHorizontal className="h-4 w-4 mr-1.5" />
              Sensitivity
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
          {networkData && (
            <TabsContent value="network" className="mt-0">
              <NetworkResultsPanel data={networkData} projectId={projectId} />
            </TabsContent>
          )}
          <TabsContent value="sensitivity" className="mt-0">
            <SensitivityPanel
              simulationId={simId}
              initialData={sensitivityData}
            />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
