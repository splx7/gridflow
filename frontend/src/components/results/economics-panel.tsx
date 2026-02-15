"use client";

import type { EconomicsResult } from "@/types";

interface EconomicsPanelProps {
  data: EconomicsResult;
}

export default function EconomicsPanel({ data }: EconomicsPanelProps) {
  const metrics = [
    {
      label: "Net Present Cost",
      value: `$${(data.npc / 1000).toFixed(0)}k`,
      description: "Total lifecycle cost discounted to present",
    },
    {
      label: "LCOE",
      value: `$${data.lcoe.toFixed(3)}/kWh`,
      description: "Levelized cost of energy",
    },
    {
      label: "IRR",
      value: data.irr != null ? `${(data.irr * 100).toFixed(1)}%` : "N/A",
      description: "Internal rate of return vs grid-only",
    },
    {
      label: "Payback",
      value: data.payback_years != null ? `${data.payback_years.toFixed(1)} years` : "N/A",
      description: "Simple payback period",
    },
    {
      label: "Renewable Fraction",
      value: `${(data.renewable_fraction * 100).toFixed(1)}%`,
      description: "Energy served from renewables",
    },
    {
      label: "CO2 Emissions",
      value: `${(data.co2_emissions_kg / 1000).toFixed(1)} t/yr`,
      description: "Annual CO2 emissions",
    },
  ];

  const costItems = Object.entries(data.cost_breakdown).sort(
    ([, a], [, b]) => (b as number) - (a as number)
  );
  const totalCost = costItems.reduce((sum, [, v]) => sum + (v as number), 0);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="bg-gray-900 border border-gray-800 rounded-xl p-4"
          >
            <p className="text-xs text-gray-500 uppercase tracking-wider">
              {m.label}
            </p>
            <p className="text-2xl font-bold mt-1">{m.value}</p>
            <p className="text-xs text-gray-500 mt-1">{m.description}</p>
          </div>
        ))}
      </div>

      {/* Cost Breakdown */}
      <section>
        <h3 className="text-lg font-semibold mb-4">Cost Breakdown</h3>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="space-y-3">
            {costItems.map(([key, value]) => {
              const pct = totalCost > 0 ? ((value as number) / totalCost) * 100 : 0;
              return (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-300">
                      {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <span className="font-medium">
                      ${((value as number) / 1000).toFixed(1)}k
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${Math.max(pct, 1)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 pt-4 border-t border-gray-800 flex justify-between text-sm font-semibold">
            <span>Total NPC</span>
            <span>${(data.npc / 1000).toFixed(0)}k</span>
          </div>
        </div>
      </section>
    </div>
  );
}
