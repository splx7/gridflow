"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjectStore } from "@/stores/project-store";
import { getErrorMessage } from "@/lib/api";
import type { Bus, Branch, Component as GridComponent, PowerFlowResult } from "@/types";
import { Trash2, X, Sun, Wind, Battery, Fuel, Plug } from "lucide-react";

const COMPONENT_ICONS: Record<string, typeof Sun> = {
  solar_pv: Sun,
  wind_turbine: Wind,
  battery: Battery,
  diesel_generator: Fuel,
  grid_connection: Plug,
};

interface BusDetailPanelProps {
  projectId: string;
  selectedBusId: string | null;
  selectedBranchId: string | null;
  onClose: () => void;
}

export default function BusDetailPanel({
  projectId,
  selectedBusId,
  selectedBranchId,
  onClose,
}: BusDetailPanelProps) {
  const {
    buses,
    branches,
    components,
    powerFlowResult,
    updateBus,
    removeBus,
    updateBranch,
    removeBranch,
    updateComponent,
  } = useProjectStore();

  const selectedBus = buses.find((b) => b.id === selectedBusId);
  const selectedBranch = branches.find((br) => br.id === selectedBranchId);

  if (selectedBus) {
    return (
      <BusEditor
        projectId={projectId}
        bus={selectedBus}
        components={components}
        powerFlowResult={powerFlowResult}
        onUpdate={updateBus}
        onUpdateComponent={updateComponent}
        onDelete={async () => {
          await removeBus(projectId, selectedBus.id);
          toast.success(`Deleted ${selectedBus.name}`);
          onClose();
        }}
      />
    );
  }

  if (selectedBranch) {
    return (
      <BranchEditor
        projectId={projectId}
        branch={selectedBranch}
        buses={buses}
        powerFlowResult={powerFlowResult}
        onUpdate={updateBranch}
        onDelete={async () => {
          await removeBranch(projectId, selectedBranch.id);
          toast.success(`Deleted ${selectedBranch.name}`);
          onClose();
        }}
      />
    );
  }

  // No selection — show violations summary
  return (
    <div className="p-4 space-y-4">
      <h3 className="text-sm font-semibold">Network Summary</h3>
      <div className="text-xs text-muted-foreground space-y-1">
        <p>{buses.length} buses, {branches.length} branches</p>
        <p>{components.filter((c) => c.bus_id).length} components assigned to buses</p>
      </div>

      {powerFlowResult && (
        <Card>
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-xs">Power Flow Results</CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3 space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge variant={powerFlowResult.converged ? "success" : "destructive"}>
                {powerFlowResult.converged ? "Converged" : "Failed"}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Min Voltage</span>
              <span className="font-mono">
                {(powerFlowResult.summary.min_voltage_pu * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Max Loading</span>
              <span className="font-mono">
                {powerFlowResult.summary.max_branch_loading_pct.toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total Losses</span>
              <span className="font-mono">
                {powerFlowResult.summary.total_losses_kw.toFixed(1)} kW
                ({powerFlowResult.summary.total_losses_pct.toFixed(2)}%)
              </span>
            </div>

            {powerFlowResult.voltage_violations.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border">
                <p className="font-medium text-amber-400 mb-1">Voltage Violations</p>
                {powerFlowResult.voltage_violations.map((v, i) => (
                  <p key={i} className="text-muted-foreground">
                    {v.bus_name}: {(v.voltage_pu * 100).toFixed(2)}% ({v.limit})
                  </p>
                ))}
              </div>
            )}

            {powerFlowResult.thermal_violations.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border">
                <p className="font-medium text-red-400 mb-1">Thermal Violations</p>
                {powerFlowResult.thermal_violations.map((v, i) => (
                  <p key={i} className="text-muted-foreground">
                    {v.branch_name}: {v.loading_pct.toFixed(1)}%
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">
        Click a bus or branch in the diagram to edit its properties.
      </p>
    </div>
  );
}

function BusEditor({
  projectId,
  bus,
  components,
  powerFlowResult,
  onUpdate,
  onUpdateComponent,
  onDelete,
}: {
  projectId: string;
  bus: Bus;
  components: GridComponent[];
  powerFlowResult: PowerFlowResult | null;
  onUpdate: (projectId: string, busId: string, body: Record<string, unknown>) => Promise<unknown>;
  onUpdateComponent: (projectId: string, componentId: string, body: { bus_id?: string | null }) => Promise<unknown>;
  onDelete: () => void;
}) {
  const [name, setName] = useState(bus.name);
  const [saving, setSaving] = useState(false);

  const voltage = powerFlowResult?.bus_voltages[bus.name];
  const sc = powerFlowResult?.short_circuit[bus.name];

  const assignedComponents = components.filter((c) => c.bus_id === bus.id);
  const unassignedComponents = components.filter((c) => !c.bus_id);

  const handleAssign = async (componentId: string) => {
    try {
      await onUpdateComponent(projectId, componentId, { bus_id: bus.id });
      toast.success("Component assigned to bus");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleUnassign = async (componentId: string) => {
    try {
      await onUpdateComponent(projectId, componentId, { bus_id: null });
      toast.success("Component unassigned from bus");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Bus Properties</h3>
        <Button variant="ghost" size="sm" className="text-red-400" onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="space-y-3">
        <div>
          <Label className="text-xs">Name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-8 text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label className="text-xs">Type</Label>
            <div className="text-sm font-mono mt-1">
              <Badge variant="secondary">{bus.bus_type.toUpperCase()}</Badge>
            </div>
          </div>
          <div>
            <Label className="text-xs">Voltage</Label>
            <div className="text-sm font-mono mt-1">
              {bus.nominal_voltage_kv >= 1
                ? `${bus.nominal_voltage_kv} kV`
                : `${bus.nominal_voltage_kv * 1000} V`}
            </div>
          </div>
        </div>

        {voltage !== undefined && (
          <div className="p-2 rounded bg-muted/50 space-y-1">
            <Label className="text-xs text-muted-foreground">Power Flow Results</Label>
            <div className="flex justify-between text-xs">
              <span>Voltage</span>
              <span className="font-mono font-bold">{(voltage * 100).toFixed(2)}%</span>
            </div>
            {sc && (
              <>
                <div className="flex justify-between text-xs">
                  <span>Short Circuit Current</span>
                  <span className="font-mono">{sc.i_sc_ka.toFixed(2)} kA</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span>Short Circuit Power</span>
                  <span className="font-mono">{sc.s_sc_mva.toFixed(1)} MVA</span>
                </div>
              </>
            )}
          </div>
        )}

        <Button
          size="sm"
          className="w-full"
          disabled={saving || name === bus.name}
          onClick={async () => {
            setSaving(true);
            try {
              await onUpdate(projectId, bus.id, { name });
              toast.success("Bus updated");
            } catch (err) {
              toast.error(getErrorMessage(err));
            } finally {
              setSaving(false);
            }
          }}
        >
          {saving ? "Saving..." : "Save Changes"}
        </Button>

        {/* Component assignment section */}
        <div className="mt-3 pt-3 border-t border-border">
          <Label className="text-xs">Assigned Components</Label>
          {assignedComponents.length === 0 ? (
            <p className="text-xs text-muted-foreground mt-1">No components assigned</p>
          ) : (
            <div className="space-y-1.5 mt-2">
              {assignedComponents.map((c) => {
                const Icon = COMPONENT_ICONS[c.component_type] || Plug;
                return (
                  <div
                    key={c.id}
                    className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1.5"
                  >
                    <div className="flex items-center gap-1.5">
                      <Icon className="h-3 w-3 text-muted-foreground" />
                      <span>{c.name}</span>
                    </div>
                    <button
                      onClick={() => handleUnassign(c.id)}
                      className="text-muted-foreground hover:text-red-400 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
          {unassignedComponents.length > 0 && (
            <div className="mt-2">
              <Select onValueChange={handleAssign}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Assign component..." />
                </SelectTrigger>
                <SelectContent>
                  {unassignedComponents.map((c) => {
                    const Icon = COMPONENT_ICONS[c.component_type] || Plug;
                    return (
                      <SelectItem key={c.id} value={c.id} className="text-xs">
                        <div className="flex items-center gap-1.5">
                          <Icon className="h-3 w-3" />
                          {c.name}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function BranchEditor({
  projectId,
  branch,
  buses,
  powerFlowResult,
  onUpdate,
  onDelete,
}: {
  projectId: string;
  branch: Branch;
  buses: Bus[];
  powerFlowResult: PowerFlowResult | null;
  onUpdate: (projectId: string, branchId: string, body: Record<string, unknown>) => Promise<unknown>;
  onDelete: () => void;
}) {
  const [name, setName] = useState(branch.name);
  const [config, setConfig] = useState(branch.config);
  const [saving, setSaving] = useState(false);

  const flow = powerFlowResult?.branch_flows[branch.name];
  const fromBus = buses.find((b) => b.id === branch.from_bus_id);
  const toBus = buses.find((b) => b.id === branch.to_bus_id);

  const isCable = branch.branch_type === "cable" || branch.branch_type === "line";

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          {branch.branch_type === "transformer" ? "Transformer" : "Cable"} Properties
        </h3>
        <Button variant="ghost" size="sm" className="text-red-400" onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="space-y-3">
        <div>
          <Label className="text-xs">Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8 text-sm" />
        </div>

        <div className="text-xs text-muted-foreground">
          {fromBus?.name || "?"} → {toBus?.name || "?"}
        </div>

        {isCable && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">R (Ω/km)</Label>
                <Input
                  type="number"
                  step="0.001"
                  value={config.r_ohm_per_km as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, r_ohm_per_km: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">X (Ω/km)</Label>
                <Input
                  type="number"
                  step="0.001"
                  value={config.x_ohm_per_km as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, x_ohm_per_km: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Length (km)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={config.length_km as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, length_km: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">Ampacity (A)</Label>
                <Input
                  type="number"
                  value={config.ampacity_a as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, ampacity_a: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>
          </>
        )}

        {branch.branch_type === "transformer" && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Rating (kVA)</Label>
                <Input
                  type="number"
                  value={config.rating_kva as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, rating_kva: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">Impedance (%)</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={config.impedance_pct as number || 0}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, impedance_pct: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">X/R Ratio</Label>
              <Input
                type="number"
                step="0.5"
                value={config.x_r_ratio as number || 10}
                onChange={(e) =>
                  setConfig((c) => ({ ...c, x_r_ratio: parseFloat(e.target.value) || 10 }))
                }
                className="h-8 text-sm"
              />
            </div>
          </>
        )}

        {flow && (
          <div className="p-2 rounded bg-muted/50 space-y-1">
            <Label className="text-xs text-muted-foreground">Power Flow Results</Label>
            <div className="flex justify-between text-xs">
              <span>Flow</span>
              <span className="font-mono">{flow.from_kw.toFixed(0)} kW</span>
            </div>
            <div className="flex justify-between text-xs">
              <span>Losses</span>
              <span className="font-mono">{flow.loss_kw.toFixed(2)} kW</span>
            </div>
            <div className="flex justify-between text-xs">
              <span>Voltage Drop</span>
              <span className="font-mono">{flow.vd_pct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between text-xs">
              <span>Loading</span>
              <span className="font-mono">{flow.loading_pct.toFixed(1)}%</span>
            </div>
          </div>
        )}

        <Button
          size="sm"
          className="w-full"
          disabled={saving}
          onClick={async () => {
            setSaving(true);
            try {
              await onUpdate(projectId, branch.id, { name, config });
              toast.success("Branch updated");
            } catch (err) {
              toast.error(getErrorMessage(err));
            } finally {
              setSaving(false);
            }
          }}
        >
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
