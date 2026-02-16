"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
import { Plus, Cable, Zap, Play, Loader2 } from "lucide-react";

interface NetworkToolbarProps {
  projectId: string;
}

export default function NetworkToolbar({ projectId }: NetworkToolbarProps) {
  const {
    buses,
    addBus,
    addBranch,
    runPowerFlow,
    powerFlowLoading,
  } = useProjectStore();
  const [busCounter, setBusCounter] = useState(buses.length + 1);

  const handleAddBus = async (voltage: number) => {
    try {
      const name = `Bus${busCounter}`;
      setBusCounter((c) => c + 1);
      const busType = voltage >= 1 ? "pq" : "pq";
      await addBus(projectId, {
        name,
        bus_type: busType,
        nominal_voltage_kv: voltage,
        x_position: 300,
        y_position: 100 + buses.length * 200,
      });
      toast.success(`Added ${name} (${voltage >= 1 ? voltage + " kV" : voltage * 1000 + " V"})`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleAddSlackBus = async () => {
    try {
      const name = `Grid Bus`;
      setBusCounter((c) => c + 1);
      await addBus(projectId, {
        name,
        bus_type: "slack",
        nominal_voltage_kv: 11.0,
        config: { voltage_setpoint_pu: 1.0, sc_mva: 250 },
        x_position: 300,
        y_position: 0,
      });
      toast.success("Added Grid (Slack) Bus — 11 kV");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleAddCable = async () => {
    if (buses.length < 2) {
      toast.error("Need at least 2 buses to add a cable");
      return;
    }
    try {
      await addBranch(projectId, {
        from_bus_id: buses[0].id,
        to_bus_id: buses[1].id,
        branch_type: "cable",
        name: `Cable${Date.now().toString(36).slice(-3)}`,
        config: {
          r_ohm_per_km: 0.193,
          x_ohm_per_km: 0.072,
          length_km: 0.1,
          ampacity_a: 250,
        },
      });
      toast.success("Added cable — edit in detail panel");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleAddTransformer = async () => {
    if (buses.length < 2) {
      toast.error("Need at least 2 buses to add a transformer");
      return;
    }
    // Find HV and LV buses
    const sorted = [...buses].sort(
      (a, b) => b.nominal_voltage_kv - a.nominal_voltage_kv
    );
    try {
      await addBranch(projectId, {
        from_bus_id: sorted[0].id,
        to_bus_id: sorted[sorted.length - 1].id,
        branch_type: "transformer",
        name: `T${Date.now().toString(36).slice(-3)}`,
        config: {
          rating_kva: 1500,
          impedance_pct: 6.0,
          x_r_ratio: 10.0,
          hv_kv: sorted[0].nominal_voltage_kv,
          lv_kv: sorted[sorted.length - 1].nominal_voltage_kv,
        },
      });
      toast.success("Added transformer — edit in detail panel");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleRunPowerFlow = async () => {
    try {
      const result = await runPowerFlow(projectId);
      if (result.converged) {
        toast.success(
          `Power flow converged in ${result.iterations} iterations — ` +
          `Min V: ${(result.summary.min_voltage_pu * 100).toFixed(1)}%, ` +
          `Losses: ${result.summary.total_losses_pct.toFixed(1)}%`
        );
      } else {
        toast.warning("Power flow did not converge — using DC approximation");
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="flex items-center gap-2 p-2 border-b border-border bg-background/50">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add Bus
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Voltage Level</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleAddSlackBus}>
            <Zap className="h-4 w-4 mr-2 text-purple-400" />
            Grid (Slack) — 11 kV
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => handleAddBus(33)}>33 kV (HV)</DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleAddBus(11)}>11 kV (MV)</DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleAddBus(0.44)}>440 V (LV)</DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleAddBus(0.4)}>400 V (LV)</DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleAddBus(0.23)}>230 V (LV)</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Button variant="outline" size="sm" onClick={handleAddCable}>
        <Cable className="h-3.5 w-3.5 mr-1" />
        Add Cable
      </Button>

      <Button variant="outline" size="sm" onClick={handleAddTransformer}>
        <svg className="h-3.5 w-3.5 mr-1" viewBox="0 0 16 16">
          <circle cx="5" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="11" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        Add Transformer
      </Button>

      <div className="flex-1" />

      <Button
        variant="default"
        size="sm"
        onClick={handleRunPowerFlow}
        disabled={powerFlowLoading || buses.length < 2}
      >
        {powerFlowLoading ? (
          <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
        ) : (
          <Play className="h-3.5 w-3.5 mr-1" />
        )}
        Run Power Flow
      </Button>
    </div>
  );
}
