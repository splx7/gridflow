"use client";

import { useState, useRef } from "react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import type { LoadProfile } from "@/types";
import {
  Home,
  Building2,
  Factory,
  Wheat,
  Check,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Tent,
  HeartPulse,
  GraduationCap,
  Radio,
  Store,
  Droplets,
  Upload,
  FileSpreadsheet,
  Square,
  CheckSquare,
} from "lucide-react";

interface ScenarioPreset {
  key: string;
  label: string;
  description: string;
  annual_kwh: number;
  peak_kw: number;
  daytime_fraction: number;
  icon: React.ReactNode;
  color: string;
  category: "standard" | "developing";
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  // Standard scenarios
  {
    key: "residential_small",
    label: "Residential (Small)",
    description: "Typical household, morning & evening peaks",
    annual_kwh: 5_000,
    peak_kw: 2.1,
    daytime_fraction: 0.35,
    icon: <Home className="h-4 w-4" />,
    color: "text-sky-400",
    category: "standard",
  },
  {
    key: "residential_large",
    label: "Residential (Large)",
    description: "Large household with HVAC / EV charging",
    annual_kwh: 12_000,
    peak_kw: 5.0,
    daytime_fraction: 0.40,
    icon: <Home className="h-4 w-4" />,
    color: "text-blue-400",
    category: "standard",
  },
  {
    key: "commercial_office",
    label: "Commercial Office",
    description: "9-to-5 weekday pattern, low weekends",
    annual_kwh: 50_000,
    peak_kw: 20.0,
    daytime_fraction: 0.70,
    icon: <Building2 className="h-4 w-4" />,
    color: "text-violet-400",
    category: "standard",
  },
  {
    key: "commercial_retail",
    label: "Commercial Retail",
    description: "Extended hours, moderate weekend load",
    annual_kwh: 80_000,
    peak_kw: 30.0,
    daytime_fraction: 0.60,
    icon: <Building2 className="h-4 w-4" />,
    color: "text-purple-400",
    category: "standard",
  },
  {
    key: "industrial_light",
    label: "Industrial (Light)",
    description: "Single-shift manufacturing, weekdays only",
    annual_kwh: 200_000,
    peak_kw: 80.0,
    daytime_fraction: 0.65,
    icon: <Factory className="h-4 w-4" />,
    color: "text-orange-400",
    category: "standard",
  },
  {
    key: "industrial_heavy",
    label: "Industrial (Heavy)",
    description: "Near-continuous 24/7 high base load",
    annual_kwh: 500_000,
    peak_kw: 180.0,
    daytime_fraction: 0.55,
    icon: <Factory className="h-4 w-4" />,
    color: "text-red-400",
    category: "standard",
  },
  {
    key: "agricultural",
    label: "Agricultural",
    description: "Seasonal irrigation & pumping loads",
    annual_kwh: 30_000,
    peak_kw: 15.0,
    daytime_fraction: 0.75,
    icon: <Wheat className="h-4 w-4" />,
    color: "text-emerald-400",
    category: "standard",
  },
  // Developing-country scenarios
  {
    key: "village_microgrid",
    label: "Village Microgrid",
    description: "50-100 households + small commerce, evening peak",
    annual_kwh: 80_000,
    peak_kw: 25.0,
    daytime_fraction: 0.55,
    icon: <Tent className="h-4 w-4" />,
    color: "text-amber-400",
    category: "developing",
  },
  {
    key: "health_clinic",
    label: "Health Clinic",
    description: "Vaccine refrigeration, lighting, medical equipment 24h",
    annual_kwh: 15_000,
    peak_kw: 5.0,
    daytime_fraction: 0.60,
    icon: <HeartPulse className="h-4 w-4" />,
    color: "text-rose-400",
    category: "developing",
  },
  {
    key: "school_campus",
    label: "School Campus",
    description: "Daytime class hours, minimal weekends",
    annual_kwh: 25_000,
    peak_kw: 12.0,
    daytime_fraction: 0.80,
    icon: <GraduationCap className="h-4 w-4" />,
    color: "text-indigo-400",
    category: "developing",
  },
  {
    key: "telecom_tower",
    label: "Telecom Tower",
    description: "24/7 near-uniform load, slight daytime increase",
    annual_kwh: 18_000,
    peak_kw: 2.5,
    daytime_fraction: 0.50,
    icon: <Radio className="h-4 w-4" />,
    color: "text-cyan-400",
    category: "developing",
  },
  {
    key: "small_enterprise",
    label: "Small Enterprise",
    description: "Workshop / shop, business-hours focused",
    annual_kwh: 22_000,
    peak_kw: 8.0,
    daytime_fraction: 0.70,
    icon: <Store className="h-4 w-4" />,
    color: "text-teal-400",
    category: "developing",
  },
  {
    key: "water_pumping",
    label: "Water Pumping",
    description: "Solar-synchronized daytime pumping, strong seasonality",
    annual_kwh: 35_000,
    peak_kw: 18.0,
    daytime_fraction: 0.85,
    icon: <Droplets className="h-4 w-4" />,
    color: "text-blue-500",
    category: "developing",
  },
];

interface LoadStepProps {
  loadProfiles: LoadProfile[];
  selectedLoadProfileId: string | null;
  selectedScenario: string | null;
  selectedCompositeScenarios: string[];
  annualKwhOverride: number | null;
  peakKwOverride: number | null;
  daytimeFractionOverride: number | null;
  onSelectLoadProfile: (id: string) => void;
  onSelectScenario: (key: string, defaultKwh: number) => void;
  onToggleCompositeScenario: (key: string) => void;
  onAnnualKwhChange: (kwh: number | null) => void;
  onPeakKwChange: (kw: number | null) => void;
  onDaytimeFractionChange: (frac: number | null) => void;
  onCsvUploaded: (profile: LoadProfile) => void;
  onNext: () => void;
  projectId: string;
}

const DIVERSITY_FACTOR = 0.8;

export default function LoadStep({
  loadProfiles,
  selectedLoadProfileId,
  selectedScenario,
  selectedCompositeScenarios,
  annualKwhOverride,
  peakKwOverride,
  daytimeFractionOverride,
  onSelectLoadProfile,
  onSelectScenario,
  onToggleCompositeScenario,
  onAnnualKwhChange,
  onPeakKwChange,
  onDaytimeFractionChange,
  onCsvUploaded,
  onNext,
  projectId,
}: LoadStepProps) {
  const [showCustomize, setShowCustomize] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isComposite = selectedCompositeScenarios.length > 0;
  const isSingleScenario = selectedScenario && !isComposite;
  const hasSelection = selectedLoadProfileId || selectedScenario || isComposite;

  // Compute effective values based on selection mode
  const selectedPreset = SCENARIO_PRESETS.find((p) => p.key === selectedScenario);
  const compositePresets = selectedCompositeScenarios
    .map((k) => SCENARIO_PRESETS.find((p) => p.key === k))
    .filter(Boolean) as ScenarioPreset[];

  // For composite: compute combined values
  const combinedAnnualKwh = compositePresets.reduce((sum, p) => sum + p.annual_kwh, 0);
  const combinedRawPeak = compositePresets.reduce((sum, p) => sum + p.peak_kw, 0);
  const combinedPeakKw = combinedRawPeak * DIVERSITY_FACTOR;
  const combinedDaytime = combinedAnnualKwh > 0
    ? compositePresets.reduce((sum, p) => sum + p.annual_kwh * p.daytime_fraction, 0) / combinedAnnualKwh
    : 0.5;

  // Effective values: composite or single
  const baseKwh = isComposite ? combinedAnnualKwh : selectedPreset?.annual_kwh ?? null;
  const basePeak = isComposite ? combinedPeakKw : selectedPreset?.peak_kw ?? null;
  const baseDaytime = isComposite ? combinedDaytime : selectedPreset?.daytime_fraction ?? null;

  const effectiveKwh = annualKwhOverride ?? baseKwh;
  const effectivePeakKw = peakKwOverride ?? basePeak;
  const effectiveDaytime = daytimeFractionOverride ?? baseDaytime;

  const standardPresets = SCENARIO_PRESETS.filter((p) => p.category === "standard");
  const developingPresets = SCENARIO_PRESETS.filter((p) => p.category === "developing");

  const handleReset = () => {
    onAnnualKwhChange(null);
    onPeakKwChange(null);
    onDaytimeFractionChange(null);
  };

  const hasOverrides =
    annualKwhOverride !== null ||
    peakKwOverride !== null ||
    daytimeFractionOverride !== null;

  const handleCsvUpload = async (file: File) => {
    setUploading(true);
    try {
      const { uploadLoadProfile } = await import("@/lib/api");
      const profile = await uploadLoadProfile(projectId, file);
      onCsvUploaded(profile);
      toast.success(`Uploaded "${file.name}" — ${profile.annual_kwh.toLocaleString()} kWh/yr`);
    } catch (err) {
      const { getErrorMessage } = await import("@/lib/api");
      toast.error(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Existing load profiles */}
      {loadProfiles.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
            Existing Load Profiles
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {loadProfiles.map((lp) => (
              <Card
                key={lp.id}
                variant="glass"
                className={`cursor-pointer transition-all ${
                  selectedLoadProfileId === lp.id
                    ? "ring-2 ring-primary"
                    : "hover:border-primary/50"
                }`}
                onClick={() => onSelectLoadProfile(lp.id)}
              >
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium">{lp.name}</span>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {lp.annual_kwh.toLocaleString()} kWh/yr
                    </p>
                  </div>
                  {selectedLoadProfileId === lp.id && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Standard scenario presets (radio selection) */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          {loadProfiles.length > 0
            ? "Or Choose a Scenario Preset"
            : "Choose a Load Scenario"}
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {standardPresets.map((preset) => (
            <Card
              key={preset.key}
              variant="glass"
              className={`cursor-pointer transition-all ${
                selectedScenario === preset.key && !isComposite
                  ? "ring-2 ring-primary"
                  : "hover:border-primary/50"
              }`}
              onClick={() => onSelectScenario(preset.key, preset.annual_kwh)}
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className={preset.color}>{preset.icon}</span>
                  <span className="text-sm font-medium">{preset.label}</span>
                  {selectedScenario === preset.key && !isComposite && (
                    <Check className="h-3.5 w-3.5 text-primary ml-auto" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {preset.description}
                </p>
                <Badge variant="secondary" className="mt-2 text-xs">
                  {preset.annual_kwh.toLocaleString()} kWh/yr
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Developing-country scenario presets (multi-select) */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
            Off-Grid / Developing Regions
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            Select multiple to create a composite microgrid load profile
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {developingPresets.map((preset) => {
            const isSelected = selectedCompositeScenarios.includes(preset.key);
            return (
              <Card
                key={preset.key}
                variant="glass"
                className={`cursor-pointer transition-all ${
                  isSelected
                    ? "ring-2 ring-primary"
                    : "hover:border-primary/50"
                }`}
                onClick={() => onToggleCompositeScenario(preset.key)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-1">
                    {isSelected ? (
                      <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                    ) : (
                      <Square className="h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                    <span className={preset.color}>{preset.icon}</span>
                    <span className="text-sm font-medium">{preset.label}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {preset.description}
                  </p>
                  <Badge variant="secondary" className="mt-2 text-xs">
                    {preset.annual_kwh.toLocaleString()} kWh/yr
                  </Badge>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Combined summary for composite selection */}
        {selectedCompositeScenarios.length >= 2 && (
          <Card variant="glass" className="border-primary/30 bg-primary/5">
            <CardContent className="p-4">
              <h5 className="text-sm font-medium mb-2">Combined Load Summary</h5>
              <div className="flex flex-wrap gap-3 text-xs">
                <Badge variant="secondary">
                  {combinedAnnualKwh.toLocaleString()} kWh/yr
                </Badge>
                <Badge variant="secondary">
                  Est. Peak: {combinedPeakKw.toFixed(1)} kW
                </Badge>
                <Badge variant="secondary">
                  Daytime Load: {Math.round(combinedDaytime * 100)}%
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {compositePresets.map((p) => p.label).join(" + ")} (diversity factor: {DIVERSITY_FACTOR})
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Customize parameters panel */}
      {(isSingleScenario || isComposite) && (
        <div className="space-y-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCustomize(!showCustomize)}
            className="text-xs"
          >
            {showCustomize ? (
              <ChevronUp className="h-3 w-3 mr-1" />
            ) : (
              <ChevronDown className="h-3 w-3 mr-1" />
            )}
            Customize Parameters
          </Button>

          {showCustomize && (
            <Card variant="glass">
              <CardContent className="p-4 space-y-5">
                {/* Annual consumption */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs">Annual Consumption</Label>
                    <span className="text-xs font-medium tabular-nums">
                      {(effectiveKwh ?? 0).toLocaleString()} kWh/yr
                    </span>
                  </div>
                  <Slider
                    value={[effectiveKwh ?? 0]}
                    min={Math.round((baseKwh ?? 1000) * 0.1)}
                    max={Math.round((baseKwh ?? 1000) * 3)}
                    step={Math.max(100, Math.round((baseKwh ?? 1000) * 0.01))}
                    onValueChange={([v]) => onAnnualKwhChange(v)}
                  />
                </div>

                {/* Peak demand */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs">Peak Demand</Label>
                    <span className="text-xs font-medium tabular-nums">
                      {(effectivePeakKw ?? 0).toFixed(1)} kW
                    </span>
                  </div>
                  <Slider
                    value={[effectivePeakKw ?? 0]}
                    min={Math.round((basePeak ?? 1) * 0.2 * 10) / 10}
                    max={Math.round((basePeak ?? 1) * 3 * 10) / 10}
                    step={Math.max(0.1, Math.round((basePeak ?? 1) * 0.02 * 10) / 10)}
                    onValueChange={([v]) => onPeakKwChange(v)}
                  />
                </div>

                {/* Daytime load fraction */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs">Daytime Load Fraction</Label>
                    <span className="text-xs font-medium tabular-nums">
                      {Math.round((effectiveDaytime ?? 0.5) * 100)}%
                    </span>
                  </div>
                  <Slider
                    value={[Math.round((effectiveDaytime ?? 0.5) * 100)]}
                    min={10}
                    max={95}
                    step={5}
                    onValueChange={([v]) => onDaytimeFractionChange(v / 100)}
                  />
                </div>

                {/* Reset button */}
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    disabled={!hasOverrides}
                    className="text-xs"
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Reset to Defaults
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* CSV Upload */}
      <div className="space-y-2">
        <div className="relative flex items-center gap-3">
          <div className="flex-1 border-t border-border" />
          <span className="text-xs text-muted-foreground">or upload your own</span>
          <div className="flex-1 border-t border-border" />
        </div>
        <div className="flex items-center justify-center">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleCsvUpload(file);
              e.target.value = "";
            }}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full mr-2" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            <FileSpreadsheet className="h-4 w-4 mr-1" />
            Upload Load CSV (8760 hourly kW)
          </Button>
        </div>
      </div>

      {/* Next button */}
      <div className="flex justify-end pt-2">
        <Button disabled={!hasSelection} onClick={onNext}>
          Next: Set Your Goals
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
