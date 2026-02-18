"use client";

import { useState } from "react";
import { Button } from "./button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "./sheet";
import { HelpCircle, X } from "lucide-react";

const HELP_CONTENT: Record<string, { title: string; content: string }> = {
  "economics.npc": {
    title: "Net Present Cost (NPC)",
    content:
      "The total lifecycle cost of the system, discounted to present value. Includes capital costs, O&M, fuel, replacements, minus salvage value. Lower NPC means lower total system cost over the project lifetime.",
  },
  "economics.lcoe": {
    title: "Levelized Cost of Energy (LCOE)",
    content:
      "The average cost per kWh of energy produced over the system lifetime. Calculated as NPC divided by total discounted energy served. Compare with local grid tariff to assess economic viability.",
  },
  "economics.irr": {
    title: "Internal Rate of Return (IRR)",
    content:
      "The discount rate at which the net present value of savings equals zero. Higher IRR means better investment return. A project with IRR above the discount rate is financially viable.",
  },
  "economics.payback": {
    title: "Simple Payback Period",
    content:
      "The number of years for cumulative savings to equal the initial investment. Does not account for time value of money. Useful for quick assessment of investment recovery time.",
  },
  "economics.renewable_fraction": {
    title: "Renewable Fraction",
    content:
      "Percentage of total energy served from renewable sources (solar PV, wind). A renewable fraction of 100% means no fossil fuel or grid dependence.",
  },
  "network.power_flow": {
    title: "Power Flow Analysis",
    content:
      "Newton-Raphson AC power flow calculates voltage magnitudes, angles, and branch power flows for the electrical network. Identifies voltage violations (outside ±5% of nominal) and thermal overloads (branch loading > 100%).",
  },
  "network.contingency": {
    title: "N-1 Contingency Analysis",
    content:
      "Tests system resilience by removing each branch one at a time and re-running power flow. The system passes N-1 if no voltage or thermal violations occur for any single branch outage.",
  },
  "sensitivity.spider": {
    title: "Spider Chart",
    content:
      "Shows how each input parameter affects the output metric (e.g., LCOE) when varied from its base value. Steeper lines indicate higher sensitivity — parameters with steep slopes should be estimated carefully.",
  },
  "sensitivity.tornado": {
    title: "Tornado Chart",
    content:
      "Shows the range of output values for each parameter varied between its min and max. Wider bars indicate more influential parameters. Useful for identifying which assumptions matter most.",
  },
  "dispatch.load_following": {
    title: "Load Following Strategy",
    content:
      "PV/wind surplus charges the battery first. Battery discharges when renewables are insufficient. Generator runs only when battery is depleted. Most common for solar-dominant off-grid systems.",
  },
  "dispatch.optimal": {
    title: "Optimal (LP) Dispatch",
    content:
      "Uses linear programming (HiGHS solver) to find the cost-minimizing dispatch for all 8,760 hours simultaneously. Produces the theoretical best-case operation but assumes perfect forecasting.",
  },
  "configure.components": {
    title: "System Components",
    content:
      "Configure the generation, storage, and grid connection components of your power system. Each component has technical parameters (capacity, efficiency) and economic parameters (costs, lifetime).",
  },
  "configure.weather": {
    title: "Weather Data",
    content:
      "Hourly weather data (GHI, DNI, DHI, temperature, wind speed) drives PV and wind generation models. PVGIS provides free Typical Meteorological Year (TMY) data for any global location.",
  },
  "configure.load": {
    title: "Load Profiles",
    content:
      "8,760 hourly electricity demand values (kW) for one year. Choose from preset scenarios (residential, commercial, industrial) or upload a custom CSV. The load profile determines system sizing requirements.",
  },
};

interface HelpDrawerProps {
  helpKey: string;
  className?: string;
}

export function HelpIcon({ helpKey, className }: HelpDrawerProps) {
  const [open, setOpen] = useState(false);
  const helpEntry = HELP_CONTENT[helpKey];

  if (!helpEntry) return null;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          className={`text-muted-foreground/50 hover:text-muted-foreground transition-colors ${className || ""}`}
          title="Help"
        >
          <HelpCircle className="h-3.5 w-3.5" />
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-80 sm:w-96">
        <SheetHeader>
          <SheetTitle className="text-left">{helpEntry.title}</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-3">
          <p className="text-sm text-muted-foreground leading-relaxed">
            {helpEntry.content}
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function HelpDrawer() {
  const [open, setOpen] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" title="Help">
          <HelpCircle className="h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-80 sm:w-96">
        <SheetHeader>
          <SheetTitle className="text-left">Help & Documentation</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-2 overflow-y-auto max-h-[calc(100vh-100px)]">
          {Object.entries(HELP_CONTENT).map(([key, entry]) => (
            <button
              key={key}
              onClick={() => setActiveKey(activeKey === key ? null : key)}
              className="w-full text-left p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors"
            >
              <p className="text-sm font-medium">{entry.title}</p>
              {activeKey === key && (
                <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                  {entry.content}
                </p>
              )}
            </button>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
