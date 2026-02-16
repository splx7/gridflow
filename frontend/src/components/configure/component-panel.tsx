"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ComponentType } from "@/types";
import { Sun, Wind, Battery, Fuel, Plug, Trash2, Plus, Save, X } from "lucide-react";

const COMPONENT_DEFAULTS: Record<ComponentType, Record<string, unknown>> = {
  solar_pv: {
    type: "solar_pv",
    capacity_kwp: 10,
    tilt_deg: 30,
    azimuth_deg: 180,
    module_type: "mono-si",
    inverter_efficiency: 0.96,
    system_losses: 0.14,
    capital_cost_per_kw: 1000,
    om_cost_per_kw_year: 15,
    lifetime_years: 25,
    derating_factor: 0.005,
  },
  wind_turbine: {
    type: "wind_turbine",
    rated_power_kw: 25,
    hub_height_m: 50,
    rotor_diameter_m: 20,
    cut_in_speed: 3,
    cut_out_speed: 25,
    rated_speed: 12,
    quantity: 1,
    capital_cost_per_kw: 1500,
    om_cost_per_kw_year: 30,
    lifetime_years: 20,
  },
  battery: {
    type: "battery",
    capacity_kwh: 100,
    max_charge_rate_kw: 50,
    max_discharge_rate_kw: 50,
    round_trip_efficiency: 0.9,
    min_soc: 0.2,
    max_soc: 1.0,
    initial_soc: 0.5,
    chemistry: "nmc",
    cycle_life: 5000,
    capital_cost_per_kwh: 300,
    replacement_cost_per_kwh: 200,
    om_cost_per_kwh_year: 5,
    lifetime_years: 10,
  },
  diesel_generator: {
    type: "diesel_generator",
    rated_power_kw: 50,
    min_load_ratio: 0.25,
    fuel_curve_a0: 0.246,
    fuel_curve_a1: 0.08145,
    fuel_price_per_liter: 1.0,
    capital_cost_per_kw: 500,
    om_cost_per_hour: 2,
    lifetime_hours: 15000,
    start_cost: 5,
  },
  grid_connection: {
    type: "grid_connection",
    max_import_kw: 1000,
    max_export_kw: 1000,
    sell_back_enabled: true,
    net_metering: false,
    buy_rate: 0.12,
    sell_rate: 0.05,
    demand_charge: 0,
  },
};

const COMPONENT_LABELS: Record<ComponentType, string> = {
  solar_pv: "Solar PV",
  wind_turbine: "Wind Turbine",
  battery: "Battery Storage",
  diesel_generator: "Diesel Generator",
  grid_connection: "Grid Connection",
};

const COMPONENT_ICONS: Record<ComponentType, React.ReactNode> = {
  solar_pv: <Sun className="h-4 w-4 text-amber-400" />,
  wind_turbine: <Wind className="h-4 w-4 text-sky-400" />,
  battery: <Battery className="h-4 w-4 text-emerald-400" />,
  diesel_generator: <Fuel className="h-4 w-4 text-orange-400" />,
  grid_connection: <Plug className="h-4 w-4 text-violet-400" />,
};

interface FieldMeta {
  label: string;
  unit?: string;
  type: "number" | "boolean" | "select";
  options?: string[];
  step?: number;
}

const FIELD_META: Record<string, Record<string, FieldMeta>> = {
  solar_pv: {
    capacity_kwp: { label: "Capacity", unit: "kWp", type: "number" },
    tilt_deg: { label: "Tilt", unit: "°", type: "number" },
    azimuth_deg: { label: "Azimuth", unit: "°", type: "number" },
    module_type: { label: "Module Type", type: "select", options: ["mono-si", "poly-si", "thin-film", "cis"] },
    inverter_efficiency: { label: "Inverter Efficiency", type: "number", step: 0.01 },
    system_losses: { label: "System Losses", type: "number", step: 0.01 },
    capital_cost_per_kw: { label: "Capital Cost", unit: "$/kW", type: "number" },
    om_cost_per_kw_year: { label: "O&M Cost", unit: "$/kW/yr", type: "number" },
    lifetime_years: { label: "Lifetime", unit: "years", type: "number" },
    derating_factor: { label: "Derating Factor", unit: "%/yr", type: "number", step: 0.001 },
  },
  wind_turbine: {
    rated_power_kw: { label: "Rated Power", unit: "kW", type: "number" },
    hub_height_m: { label: "Hub Height", unit: "m", type: "number" },
    rotor_diameter_m: { label: "Rotor Diameter", unit: "m", type: "number" },
    cut_in_speed: { label: "Cut-in Speed", unit: "m/s", type: "number", step: 0.1 },
    cut_out_speed: { label: "Cut-out Speed", unit: "m/s", type: "number", step: 0.1 },
    rated_speed: { label: "Rated Speed", unit: "m/s", type: "number", step: 0.1 },
    quantity: { label: "Quantity", type: "number" },
    capital_cost_per_kw: { label: "Capital Cost", unit: "$/kW", type: "number" },
    om_cost_per_kw_year: { label: "O&M Cost", unit: "$/kW/yr", type: "number" },
    lifetime_years: { label: "Lifetime", unit: "years", type: "number" },
  },
  battery: {
    capacity_kwh: { label: "Capacity", unit: "kWh", type: "number" },
    max_charge_rate_kw: { label: "Max Charge Rate", unit: "kW", type: "number" },
    max_discharge_rate_kw: { label: "Max Discharge Rate", unit: "kW", type: "number" },
    round_trip_efficiency: { label: "Round-trip Efficiency", type: "number", step: 0.01 },
    min_soc: { label: "Min SoC", type: "number", step: 0.01 },
    max_soc: { label: "Max SoC", type: "number", step: 0.01 },
    initial_soc: { label: "Initial SoC", type: "number", step: 0.01 },
    chemistry: { label: "Chemistry", type: "select", options: ["nmc", "lfp", "lto", "lead_acid"] },
    cycle_life: { label: "Cycle Life", unit: "cycles", type: "number" },
    capital_cost_per_kwh: { label: "Capital Cost", unit: "$/kWh", type: "number" },
    replacement_cost_per_kwh: { label: "Replacement Cost", unit: "$/kWh", type: "number" },
    om_cost_per_kwh_year: { label: "O&M Cost", unit: "$/kWh/yr", type: "number" },
    lifetime_years: { label: "Lifetime", unit: "years", type: "number" },
  },
  diesel_generator: {
    rated_power_kw: { label: "Rated Power", unit: "kW", type: "number" },
    min_load_ratio: { label: "Min Load Ratio", type: "number", step: 0.01 },
    fuel_curve_a0: { label: "Fuel Curve a₀", type: "number", step: 0.001 },
    fuel_curve_a1: { label: "Fuel Curve a₁", type: "number", step: 0.001 },
    fuel_price_per_liter: { label: "Fuel Price", unit: "$/L", type: "number", step: 0.01 },
    capital_cost_per_kw: { label: "Capital Cost", unit: "$/kW", type: "number" },
    om_cost_per_hour: { label: "O&M Cost", unit: "$/hr", type: "number", step: 0.1 },
    lifetime_hours: { label: "Lifetime", unit: "hours", type: "number" },
    start_cost: { label: "Start Cost", unit: "$", type: "number" },
  },
  grid_connection: {
    max_import_kw: { label: "Max Import", unit: "kW", type: "number" },
    max_export_kw: { label: "Max Export", unit: "kW", type: "number" },
    sell_back_enabled: { label: "Sell-back Enabled", type: "boolean" },
    net_metering: { label: "Net Metering", type: "boolean" },
    buy_rate: { label: "Buy Rate", unit: "$/kWh", type: "number", step: 0.01 },
    sell_rate: { label: "Sell Rate", unit: "$/kWh", type: "number", step: 0.01 },
    demand_charge: { label: "Demand Charge", unit: "$/kW", type: "number", step: 0.01 },
  },
};

function formatFieldDisplay(key: string, value: unknown, componentType: string): string {
  const meta = FIELD_META[componentType]?.[key];
  if (!meta) return String(value);
  if (meta.type === "boolean") return value ? "Yes" : "No";
  if (meta.unit) return `${value} ${meta.unit}`;
  return String(value);
}

interface ComponentPanelProps {
  projectId: string;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export default function ComponentPanel({
  projectId,
  selectedId,
  onSelect,
}: ComponentPanelProps) {
  const {
    components,
    addComponent,
    removeComponent,
    updateComponent,
    advisorResult,
    appliedRecommendation,
    evaluateHealth,
  } = useProjectStore();
  const [editConfig, setEditConfig] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Build what-if component list (saved components + current edit override)
  const triggerEvaluate = useCallback(
    (overrideConfig?: Record<string, unknown> | null) => {
      if (!advisorResult || !appliedRecommendation) return;

      const whatIfComponents = components.map((c) => {
        if (c.id === selectedId && overrideConfig) {
          return { component_type: c.component_type, config: overrideConfig };
        }
        return { component_type: c.component_type, config: c.config };
      });

      evaluateHealth(projectId, {
        components: whatIfComponents,
        load_summary: advisorResult.load_summary,
        solar_resource: advisorResult.solar_resource,
      }).catch(() => {});
    },
    [projectId, components, selectedId, advisorResult, appliedRecommendation, evaluateHealth]
  );

  // Re-evaluate whenever components list changes (initial load, add, remove, update)
  const prevComponentsRef = useRef<string>("");
  useEffect(() => {
    if (!advisorResult || !appliedRecommendation) return;
    if (components.length === 0) return;

    // Only re-evaluate if component list actually changed (not just re-render)
    const fingerprint = components.map(c => `${c.id}:${c.component_type}:${JSON.stringify(c.config)}`).join(",");
    if (fingerprint === prevComponentsRef.current) return;
    prevComponentsRef.current = fingerprint;

    triggerEvaluate();
  }, [components, advisorResult, appliedRecommendation, triggerEvaluate]);

  // Debounced evaluate when editConfig changes
  useEffect(() => {
    if (!editConfig || !appliedRecommendation) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      triggerEvaluate(editConfig);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [editConfig, appliedRecommendation, triggerEvaluate]);

  const handleAdd = async (type: ComponentType) => {
    try {
      await addComponent(projectId, {
        component_type: type,
        name: COMPONENT_LABELS[type],
        config: COMPONENT_DEFAULTS[type],
      });
      toast.success(`${COMPONENT_LABELS[type]} added`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleCardClick = (compId: string, config: Record<string, unknown>) => {
    if (selectedId === compId) {
      onSelect(null);
      setEditConfig(null);
    } else {
      onSelect(compId);
      setEditConfig({ ...config });
    }
  };

  const handleCancel = () => {
    onSelect(null);
    setEditConfig(null);
  };

  const handleSave = async (componentId: string) => {
    if (!editConfig) return;
    setSaving(true);
    try {
      await updateComponent(projectId, componentId, { config: editConfig });
      onSelect(null);
      setEditConfig(null);
      toast.success("Component updated");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleFieldChange = (key: string, value: unknown) => {
    setEditConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
        Components
      </h3>

      {/* Add Component Buttons */}
      <div className="grid grid-cols-2 gap-2">
        {(Object.keys(COMPONENT_LABELS) as ComponentType[]).map((type) => (
          <Button
            key={type}
            variant="outline"
            size="sm"
            className="justify-start gap-2 h-auto py-2"
            onClick={() => handleAdd(type)}
          >
            <Plus className="h-3 w-3" />
            {COMPONENT_LABELS[type]}
          </Button>
        ))}
      </div>

      {/* Component List */}
      <div className="space-y-2 mt-4">
        {components.map((comp) => {
          const isSelected = comp.id === selectedId;
          const typeMeta = FIELD_META[comp.component_type] || {};

          return (
            <Card
              key={comp.id}
              variant={isSelected ? "elevated" : "glass"}
              className={isSelected ? "ring-1 ring-primary" : "cursor-pointer"}
            >
              <CardContent className="p-3">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => handleCardClick(comp.id, comp.config)}
                >
                  <div className="flex items-center gap-2">
                    {COMPONENT_ICONS[comp.component_type as ComponentType]}
                    <span className="text-sm font-medium">{comp.name}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeComponent(projectId, comp.id)
                        .then(() => toast.success("Component removed"))
                        .catch((err) => toast.error(getErrorMessage(err)));
                    }}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                <Badge variant="secondary" className="mt-2 text-[10px]">
                  {COMPONENT_LABELS[comp.component_type as ComponentType] ||
                    comp.component_type}
                </Badge>

                {/* Collapsed: Config Summary with units */}
                {!isSelected && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(comp.config)
                      .filter(([k]) => k !== "type")
                      .slice(0, 4)
                      .map(([key, value]) => (
                        <div
                          key={key}
                          className="flex justify-between text-xs"
                        >
                          <span className="text-muted-foreground">
                            {typeMeta[key]?.label || key.replace(/_/g, " ")}
                            {typeMeta[key]?.unit && (
                              <span className="ml-1 text-muted-foreground/60">
                                ({typeMeta[key].unit})
                              </span>
                            )}
                          </span>
                          <span>
                            {formatFieldDisplay(key, value, comp.component_type)}
                          </span>
                        </div>
                      ))}
                  </div>
                )}

                {/* Expanded: Edit Form */}
                {isSelected && editConfig && (
                  <div className="mt-3 space-y-3 border-t border-border pt-3">
                    {Object.entries(editConfig)
                      .filter(([k]) => k !== "type")
                      .map(([key, value]) => {
                        const meta = typeMeta[key];
                        if (!meta) return null;

                        const fieldLabel = meta.unit
                          ? `${meta.label} (${meta.unit})`
                          : meta.label;

                        return (
                          <div key={key} className="space-y-1">
                            <Label className="text-xs text-muted-foreground">
                              {fieldLabel}
                            </Label>

                            {meta.type === "number" && (
                              <Input
                                type="number"
                                step={meta.step || 1}
                                value={value as number}
                                onChange={(e) =>
                                  handleFieldChange(key, parseFloat(e.target.value) || 0)
                                }
                                className="h-8 text-sm"
                              />
                            )}

                            {meta.type === "boolean" && (
                              <div className="flex items-center gap-2">
                                <Switch
                                  checked={value as boolean}
                                  onCheckedChange={(checked) =>
                                    handleFieldChange(key, checked)
                                  }
                                />
                                <span className="text-xs text-muted-foreground">
                                  {value ? "Yes" : "No"}
                                </span>
                              </div>
                            )}

                            {meta.type === "select" && meta.options && (
                              <Select
                                value={value as string}
                                onValueChange={(v) => handleFieldChange(key, v)}
                              >
                                <SelectTrigger className="h-8 text-sm">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {meta.options.map((opt) => (
                                    <SelectItem key={opt} value={opt}>
                                      {opt}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            )}
                          </div>
                        );
                      })}

                    <div className="flex gap-2 pt-2">
                      <Button
                        size="sm"
                        className="flex-1 gap-1"
                        onClick={() => handleSave(comp.id)}
                        disabled={saving}
                      >
                        <Save className="h-3 w-3" />
                        {saving ? "Saving..." : "Save"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1 gap-1"
                        onClick={handleCancel}
                      >
                        <X className="h-3 w-3" />
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
