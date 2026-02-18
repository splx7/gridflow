"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { useProjectStore } from "@/stores/project-store";
import { uploadWeather, uploadLoadProfile, getErrorMessage, getWeatherPreview, getLoadProfilePreview } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as ReTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  CloudSun,
  Upload,
  FileSpreadsheet,
  Loader2,
  PlugZap,
  Home,
  Building2,
  Factory,
  Wheat,
  Zap,
  Tent,
  HeartPulse,
  GraduationCap,
  Radio,
  Store,
  Droplets,
  CheckCircle2,
} from "lucide-react";

interface ScenarioPreset {
  key: string;
  label: string;
  description: string;
  annual_kwh: number;
  icon: React.ReactNode;
  color: string;
}

const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    key: "residential_small",
    label: "Residential (Small)",
    description: "Typical household, morning & evening peaks",
    annual_kwh: 5_000,
    icon: <Home className="h-4 w-4" />,
    color: "text-sky-400",
  },
  {
    key: "residential_large",
    label: "Residential (Large)",
    description: "Large household with HVAC / EV charging",
    annual_kwh: 12_000,
    icon: <Home className="h-4 w-4" />,
    color: "text-blue-400",
  },
  {
    key: "commercial_office",
    label: "Commercial Office",
    description: "9-to-5 weekday pattern, low weekends",
    annual_kwh: 50_000,
    icon: <Building2 className="h-4 w-4" />,
    color: "text-violet-400",
  },
  {
    key: "commercial_retail",
    label: "Commercial Retail",
    description: "Extended hours, moderate weekend load",
    annual_kwh: 80_000,
    icon: <Building2 className="h-4 w-4" />,
    color: "text-purple-400",
  },
  {
    key: "industrial_light",
    label: "Industrial (Light)",
    description: "Single-shift manufacturing, weekdays only",
    annual_kwh: 200_000,
    icon: <Factory className="h-4 w-4" />,
    color: "text-orange-400",
  },
  {
    key: "industrial_heavy",
    label: "Industrial (Heavy)",
    description: "Near-continuous 24/7 high base load",
    annual_kwh: 500_000,
    icon: <Factory className="h-4 w-4" />,
    color: "text-red-400",
  },
  {
    key: "agricultural",
    label: "Agricultural",
    description: "Seasonal irrigation & pumping loads",
    annual_kwh: 30_000,
    icon: <Wheat className="h-4 w-4" />,
    color: "text-emerald-400",
  },
  {
    key: "village_microgrid",
    label: "Village Microgrid",
    description: "50-100 households + small commerce, evening peak",
    annual_kwh: 80_000,
    icon: <Tent className="h-4 w-4" />,
    color: "text-amber-400",
  },
  {
    key: "health_clinic",
    label: "Health Clinic",
    description: "Vaccine refrigeration, lighting, medical equipment 24h",
    annual_kwh: 15_000,
    icon: <HeartPulse className="h-4 w-4" />,
    color: "text-rose-400",
  },
  {
    key: "school_campus",
    label: "School Campus",
    description: "Daytime class hours, minimal weekends",
    annual_kwh: 25_000,
    icon: <GraduationCap className="h-4 w-4" />,
    color: "text-indigo-400",
  },
  {
    key: "telecom_tower",
    label: "Telecom Tower",
    description: "24/7 near-uniform load, slight daytime increase",
    annual_kwh: 18_000,
    icon: <Radio className="h-4 w-4" />,
    color: "text-cyan-400",
  },
  {
    key: "small_enterprise",
    label: "Small Enterprise",
    description: "Workshop / shop, business-hours focused",
    annual_kwh: 22_000,
    icon: <Store className="h-4 w-4" />,
    color: "text-teal-400",
  },
  {
    key: "water_pumping",
    label: "Water Pumping",
    description: "Solar-synchronized daytime pumping, strong seasonality",
    annual_kwh: 35_000,
    icon: <Droplets className="h-4 w-4" />,
    color: "text-blue-500",
  },
];

function formatMWh(kwh: number): string {
  if (kwh >= 1_000_000) return `${(kwh / 1_000_000).toFixed(1)} GWh/yr`;
  if (kwh >= 1_000) return `${(kwh / 1_000).toFixed(0)} MWh/yr`;
  return `${kwh.toLocaleString()} kWh/yr`;
}

interface DataPanelProps {
  projectId: string;
}

export default function DataPanel({ projectId }: DataPanelProps) {
  const {
    weatherDatasets,
    loadProfiles,
    fetchPVGIS,
    fetchWeather,
    fetchLoadProfiles,
    generateLoadProfile,
  } = useProjectStore();

  const weatherFileRef = useRef<HTMLInputElement>(null);
  const loadFileRef = useRef<HTMLInputElement>(null);
  const [fetchingPVGIS, setFetchingPVGIS] = useState(false);
  const [weatherDrag, setWeatherDrag] = useState(false);
  const [loadDrag, setLoadDrag] = useState(false);
  const [generatingScenario, setGeneratingScenario] = useState<string | null>(null);

  // Preview data
  const [weatherPreview, setWeatherPreview] = useState<{
    months: string[];
    ghi_avg: number[];
    temp_avg: number[];
    annual_ghi_kwh_m2: number;
  } | null>(null);
  const [loadPreview, setLoadPreview] = useState<{
    hours: number[];
    avg_kw: number[];
    peak_kw: number;
    min_kw: number;
  } | null>(null);

  // Fetch weather preview when datasets change
  useEffect(() => {
    if (weatherDatasets.length > 0) {
      getWeatherPreview(projectId, weatherDatasets[0].id)
        .then(setWeatherPreview)
        .catch(() => {});
    }
  }, [weatherDatasets, projectId]);

  // Fetch load preview when profiles change
  useEffect(() => {
    if (loadProfiles.length > 0) {
      getLoadProfilePreview(projectId, loadProfiles[0].id)
        .then(setLoadPreview)
        .catch(() => {});
    }
  }, [loadProfiles, projectId]);

  const handleFetchPVGIS = async () => {
    setFetchingPVGIS(true);
    try {
      await fetchPVGIS(projectId);
      toast.success("PVGIS weather data loaded");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setFetchingPVGIS(false);
    }
  };

  const handleUploadWeather = async (file: File) => {
    try {
      await uploadWeather(projectId, file);
      await fetchWeather(projectId);
      toast.success("Weather data uploaded");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleUploadLoad = async (file: File) => {
    try {
      await uploadLoadProfile(projectId, file);
      await fetchLoadProfiles(projectId);
      toast.success("Load profile uploaded");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleGenerateScenario = async (scenario: ScenarioPreset) => {
    setGeneratingScenario(scenario.key);
    try {
      await generateLoadProfile(projectId, {
        scenario: scenario.key,
      });
      toast.success(`${scenario.label} profile generated`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setGeneratingScenario(null);
    }
  };

  const onWeatherFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUploadWeather(file);
  };

  const onLoadFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUploadLoad(file);
  };

  const handleDrop = useCallback(
    (type: "weather" | "load") => (e: React.DragEvent) => {
      e.preventDefault();
      type === "weather" ? setWeatherDrag(false) : setLoadDrag(false);
      const file = e.dataTransfer.files?.[0];
      if (file) {
        type === "weather" ? handleUploadWeather(file) : handleUploadLoad(file);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId]
  );

  const hasWeather = weatherDatasets.length > 0;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Weather Data */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudSun className="h-5 w-5 text-amber-400" />
            Weather Data
            {hasWeather && (
              <Badge variant="success" className="ml-2 text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Auto-loaded
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {hasWeather && (
            <p className="text-xs text-muted-foreground">
              Weather data was automatically fetched from PVGIS when the project was created.
              You can add additional datasets below.
            </p>
          )}

          {/* Weather Preview Chart */}
          {weatherPreview && (
            <div className="rounded-lg border border-border p-3 bg-background/50">
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Monthly Average GHI (W/m²)
              </p>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart
                  data={weatherPreview.months.map((m, i) => ({
                    month: m,
                    ghi: weatherPreview.ghi_avg[i],
                  }))}
                  margin={{ top: 4, right: 4, bottom: 0, left: -20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                  <ReTooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(v: number) => [`${v} W/m²`, "GHI"]}
                  />
                  <Bar dataKey="ghi" fill="hsl(var(--chart-1))" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-muted-foreground mt-1 text-right">
                Annual: ~{weatherPreview.annual_ghi_kwh_m2.toLocaleString()} kWh/m²
              </p>
            </div>
          )}

          <div className="flex gap-3">
            <Button onClick={handleFetchPVGIS} disabled={fetchingPVGIS}>
              {fetchingPVGIS ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CloudSun className="h-4 w-4" />
              )}
              Fetch from PVGIS
            </Button>
            <Button
              variant="outline"
              onClick={() => weatherFileRef.current?.click()}
            >
              <Upload className="h-4 w-4" />
              Upload TMY CSV
            </Button>
            <input
              ref={weatherFileRef}
              type="file"
              accept=".csv"
              onChange={onWeatherFileChange}
              className="hidden"
            />
          </div>

          {/* Drop Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setWeatherDrag(true);
            }}
            onDragLeave={() => setWeatherDrag(false)}
            onDrop={handleDrop("weather")}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
              weatherDrag
                ? "border-primary bg-primary/5"
                : "border-border"
            }`}
          >
            <FileSpreadsheet className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              Drag & drop a weather CSV file here
            </p>
          </div>

          <Separator />

          {weatherDatasets.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No weather datasets yet
            </p>
          ) : (
            <div className="space-y-2">
              {weatherDatasets.map((ds) => (
                <div
                  key={ds.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background/50"
                >
                  <div className="flex items-center gap-3">
                    <CloudSun className="h-4 w-4 text-amber-400" />
                    <span className="text-sm font-medium">{ds.name}</span>
                    <Badge variant="secondary">{ds.source}</Badge>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Load Profiles */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PlugZap className="h-5 w-5 text-violet-400" />
            Load Profiles
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Load Preview Chart */}
          {loadPreview && (
            <div className="rounded-lg border border-border p-3 bg-background/50">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-muted-foreground">
                  Average Daily Load Shape
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Peak: {loadPreview.peak_kw} kW
                </p>
              </div>
              <ResponsiveContainer width="100%" height={120}>
                <LineChart
                  data={loadPreview.hours.map((h, i) => ({
                    hour: `${h}:00`,
                    kw: loadPreview.avg_kw[i],
                  }))}
                  margin={{ top: 4, right: 4, bottom: 0, left: -20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 10 }}
                    stroke="hsl(var(--muted-foreground))"
                    interval={5}
                  />
                  <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                  <ReTooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(v: number) => [`${v} kW`, "Avg Load"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="kw"
                    stroke="hsl(var(--chart-2))"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Scenario Presets */}
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
              <Zap className="h-3.5 w-3.5" />
              Quick Start &mdash; Choose a Scenario
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {SCENARIO_PRESETS.map((scenario) => {
                const isGenerating = generatingScenario === scenario.key;
                return (
                  <button
                    key={scenario.key}
                    disabled={generatingScenario !== null}
                    onClick={() => handleGenerateScenario(scenario)}
                    className="group relative text-left p-3 rounded-xl border border-border bg-background/50 hover:border-primary/50 hover:bg-primary/5 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={scenario.color}>
                        {isGenerating ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          scenario.icon
                        )}
                      </span>
                      <span className="text-sm font-medium">{scenario.label}</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {scenario.description}
                    </p>
                    <div className="mt-1.5">
                      <Badge variant="secondary" className="text-[10px]">
                        {formatMWh(scenario.annual_kwh)}
                      </Badge>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="relative">
            <Separator />
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-3 text-xs text-muted-foreground">
              or upload your own
            </span>
          </div>

          {/* Manual Upload */}
          <div className="space-y-3">
            <Button
              variant="outline"
              onClick={() => loadFileRef.current?.click()}
            >
              <Upload className="h-4 w-4" />
              Upload Load CSV (8760 hourly kW)
            </Button>
            <input
              ref={loadFileRef}
              type="file"
              accept=".csv"
              onChange={onLoadFileChange}
              className="hidden"
            />

            {/* Drop Zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setLoadDrag(true);
              }}
              onDragLeave={() => setLoadDrag(false)}
              onDrop={handleDrop("load")}
              className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                loadDrag
                  ? "border-primary bg-primary/5"
                  : "border-border"
              }`}
            >
              <FileSpreadsheet className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                Drag & drop a load profile CSV here
              </p>
            </div>
          </div>

          <Separator />

          {/* Existing profiles list */}
          {loadProfiles.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No load profiles yet
            </p>
          ) : (
            <div className="space-y-2">
              {loadProfiles.map((lp) => (
                <div
                  key={lp.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background/50"
                >
                  <div className="flex items-center gap-3">
                    <PlugZap className="h-4 w-4 text-violet-400" />
                    <span className="text-sm font-medium">{lp.name}</span>
                    <Badge variant="secondary">{lp.profile_type}</Badge>
                  </div>
                  <span className="text-sm font-medium">
                    {formatMWh(lp.annual_kwh)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
