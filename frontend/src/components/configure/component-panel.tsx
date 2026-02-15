"use client";

import { useState } from "react";
import { useProjectStore } from "@/stores/project-store";
import type { ComponentType } from "@/types";

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
    chemistry: "li-ion",
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

interface ComponentPanelProps {
  projectId: string;
  selectedId: string | null;
}

export default function ComponentPanel({ projectId, selectedId }: ComponentPanelProps) {
  const { components, addComponent, removeComponent } = useProjectStore();
  const [addingType, setAddingType] = useState<ComponentType | null>(null);

  const selectedComponent = components.find((c) => c.id === selectedId);

  const handleAdd = async (type: ComponentType) => {
    await addComponent(projectId, {
      component_type: type,
      name: COMPONENT_LABELS[type],
      config: COMPONENT_DEFAULTS[type],
    });
    setAddingType(null);
  };

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-300 uppercase tracking-wider">
        Components
      </h3>

      {/* Add Component Buttons */}
      <div className="grid grid-cols-2 gap-2">
        {(Object.keys(COMPONENT_LABELS) as ComponentType[]).map((type) => (
          <button
            key={type}
            onClick={() => handleAdd(type)}
            className="bg-gray-800 hover:bg-gray-750 border border-gray-700 rounded-lg p-2 text-xs text-center transition-colors hover:border-gray-600"
          >
            + {COMPONENT_LABELS[type]}
          </button>
        ))}
      </div>

      {/* Component List */}
      <div className="space-y-2 mt-4">
        {components.map((comp) => (
          <div
            key={comp.id}
            className={`bg-gray-800 border rounded-lg p-3 ${
              comp.id === selectedId ? "border-blue-500" : "border-gray-700"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{comp.name}</span>
              <button
                onClick={() => removeComponent(projectId, comp.id)}
                className="text-xs text-gray-500 hover:text-red-400"
              >
                Remove
              </button>
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {COMPONENT_LABELS[comp.component_type as ComponentType] || comp.component_type}
            </div>

            {/* Config Summary */}
            <div className="mt-2 space-y-1">
              {Object.entries(comp.config)
                .filter(([k]) => k !== "type")
                .slice(0, 4)
                .map(([key, value]) => (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-gray-500">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="text-gray-300">{String(value)}</span>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
