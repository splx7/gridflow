"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  EdgeTypes,
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useProjectStore } from "@/stores/project-store";
import BusNodeComponent from "./bus-node";
import LoadNodeComponent from "./load-node";
import CableEdgeComponent from "./cable-edge";
import TransformerEdgeComponent from "./transformer-edge";
import InverterEdgeComponent from "./inverter-edge";
import NetworkToolbar from "./network-toolbar";
import BusDetailPanel from "./bus-detail-panel";
import ComponentPanel from "./component-panel";
import NetworkRecommendationsBar from "./network-recommendations";
import type { Bus, Branch, Component as GridComponent } from "@/types";

const nodeTypes: NodeTypes = {
  bus: BusNodeComponent as unknown as NodeTypes["bus"],
  load: LoadNodeComponent as unknown as NodeTypes["load"],
};

const edgeTypes: EdgeTypes = {
  cable: CableEdgeComponent as unknown as EdgeTypes["cable"],
  transformer: TransformerEdgeComponent as unknown as EdgeTypes["transformer"],
  inverter: InverterEdgeComponent as unknown as EdgeTypes["inverter"],
};

// Auto-layout: position buses in a vertical tree
function autolayout(buses: Bus[], branches: Branch[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  // Sort by voltage level (highest first = top)
  const sorted = [...buses].sort(
    (a, b) => b.nominal_voltage_kv - a.nominal_voltage_kv
  );

  // Group by voltage level
  const levels: Map<number, Bus[]> = new Map();
  for (const bus of sorted) {
    const v = bus.nominal_voltage_kv;
    if (!levels.has(v)) levels.set(v, []);
    levels.get(v)!.push(bus);
  }

  let y = 0;
  for (const [, levelBuses] of levels) {
    const totalWidth = levelBuses.length * 250;
    const startX = (800 - totalWidth) / 2;
    for (let i = 0; i < levelBuses.length; i++) {
      const bus = levelBuses[i];
      positions.set(bus.id, {
        x: bus.x_position ?? startX + i * 250,
        y: bus.y_position ?? y,
      });
    }
    y += 200;
  }

  return positions;
}

interface NetworkDiagramProps {
  projectId: string;
  components: GridComponent[];
}

export default function NetworkDiagram({
  projectId,
  components,
}: NetworkDiagramProps) {
  const {
    buses,
    branches,
    loadAllocations,
    loadProfiles,
    powerFlowResult,
    networkRecommendations,
    fetchBuses,
    fetchBranches,
    fetchLoadAllocations,
    updateBus,
    runPowerFlow,
  } = useProjectStore();

  const [selectedBusId, setSelectedBusId] = useState<string | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<"network" | "components">("network");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);

  // Auto-switch to network tab when bus/branch is selected
  useEffect(() => {
    if (selectedBusId || selectedBranchId) {
      setRightTab("network");
    }
  }, [selectedBusId, selectedBranchId]);

  useEffect(() => {
    fetchBuses(projectId);
    fetchBranches(projectId);
    fetchLoadAllocations(projectId);
  }, [projectId, fetchBuses, fetchBranches, fetchLoadAllocations]);

  // Auto power-flow on structure changes (debounced)
  const prevStructureRef = useRef<string>("");
  useEffect(() => {
    const structureKey = `${buses.length}-${branches.length}`;
    if (prevStructureRef.current && prevStructureRef.current !== structureKey && buses.length > 0) {
      const timer = setTimeout(() => {
        runPowerFlow(projectId).catch(() => {});
      }, 1500);
      return () => clearTimeout(timer);
    }
    prevStructureRef.current = structureKey;
  }, [buses.length, branches.length, projectId, runPowerFlow]);

  const positions = useMemo(() => autolayout(buses, branches), [buses, branches]);

  // Build nodes from buses
  const busNodes: Node[] = useMemo(() => {
    return buses.map((bus) => {
      const pos = positions.get(bus.id) || { x: 0, y: 0 };
      const voltagePu = powerFlowResult?.bus_voltages[bus.name];

      return {
        id: bus.id,
        type: "bus",
        position: pos,
        data: {
          label: bus.name,
          busType: bus.bus_type,
          nominalVoltageKv: bus.nominal_voltage_kv,
          voltagePu,
          isSelected: bus.id === selectedBusId,
        },
        selected: bus.id === selectedBusId,
      };
    });
  }, [buses, positions, powerFlowResult, selectedBusId]);

  // Build component nodes attached to buses
  const componentNodes: Node[] = useMemo(() => {
    const busComponents = components.filter((c) => c.bus_id);
    const byBus: Map<string, GridComponent[]> = new Map();
    for (const c of busComponents) {
      if (!byBus.has(c.bus_id!)) byBus.set(c.bus_id!, []);
      byBus.get(c.bus_id!)!.push(c);
    }

    const nodes: Node[] = [];
    for (const [busId, comps] of byBus) {
      const busPos = positions.get(busId);
      if (!busPos) continue;
      comps.forEach((comp, i) => {
        nodes.push({
          id: `comp-${comp.id}`,
          type: "default",
          position: { x: busPos.x + 220 + i * 160, y: busPos.y - 10 },
          data: { label: `${comp.name}` },
          style: {
            fontSize: "10px",
            padding: "4px 8px",
            borderRadius: "6px",
            background: "hsl(222.2 84% 8%)",
            border: "1px solid hsl(217.2 32.6% 20%)",
            color: "hsl(210 40% 80%)",
          },
        });
      });
    }
    return nodes;
  }, [components, positions]);

  // Component → bus edges
  const componentEdges: Edge[] = useMemo(() => {
    return components
      .filter((c) => c.bus_id)
      .map((c) => ({
        id: `comp-edge-${c.id}`,
        source: c.bus_id!,
        target: `comp-${c.id}`,
        style: { stroke: "#6b7280", strokeWidth: 1, strokeDasharray: "4 2" },
      }));
  }, [components]);

  // Build edges from branches
  const branchEdges: Edge[] = useMemo(() => {
    return branches.map((br) => {
      const flow = powerFlowResult?.branch_flows[br.name];
      const btype = br.branch_type;

      let edgeType: string;
      let data: Record<string, unknown>;

      if (btype === "transformer") {
        edgeType = "transformer";
        data = {
          label: br.name,
          ratingKva: br.config.rating_kva as number,
          flowKw: flow?.from_kw,
          loadingPct: flow?.loading_pct,
          lossKw: flow?.loss_kw,
        };
      } else if (btype === "inverter") {
        edgeType = "inverter";
        data = {
          label: br.name,
          ratedKw: br.config.rated_power_kw as number,
          mode: br.config.mode as string,
          efficiency: br.config.efficiency as number,
          flowKw: flow?.from_kw,
          loadingPct: flow?.loading_pct,
        };
      } else {
        edgeType = "cable";
        data = {
          label: br.name,
          vdPct: flow?.vd_pct,
          flowKw: flow?.from_kw,
          loadingPct: flow?.loading_pct,
        };
      }

      return {
        id: br.id,
        source: br.from_bus_id,
        target: br.to_bus_id,
        type: edgeType,
        selected: br.id === selectedBranchId,
        data,
      };
    });
  }, [branches, powerFlowResult, selectedBranchId]);

  // Build load nodes from load allocations
  const loadNodes: Node[] = useMemo(() => {
    return loadAllocations.map((alloc, i) => {
      const busPos = positions.get(alloc.bus_id);
      const lp = loadProfiles.find((p) => p.id === alloc.load_profile_id);
      // Position below the parent bus, or use a default
      const pos = busPos
        ? { x: busPos.x, y: busPos.y + 160 }
        : { x: 100 + i * 250, y: 500 };
      return {
        id: `load-${alloc.id}`,
        type: "load" as const,
        position: pos,
        data: {
          label: alloc.name || lp?.name || "Load",
          annualKwh: lp?.annual_kwh,
          powerFactor: alloc.power_factor,
          fractionPct: alloc.fraction * 100,
        },
      };
    });
  }, [loadAllocations, loadProfiles, positions]);

  // Load allocation edges (dashed pink, bus → load node)
  const loadEdges: Edge[] = useMemo(() => {
    return loadAllocations.map((alloc) => ({
      id: `load-edge-${alloc.id}`,
      source: alloc.bus_id,
      target: `load-${alloc.id}`,
      style: { stroke: "#ec4899", strokeWidth: 1.5, strokeDasharray: "6 3" },
    }));
  }, [loadAllocations]);

  const allNodes = useMemo(
    () => [...busNodes, ...componentNodes, ...loadNodes],
    [busNodes, componentNodes, loadNodes]
  );
  const allEdges = useMemo(
    () => [...branchEdges, ...componentEdges, ...loadEdges],
    [branchEdges, componentEdges, loadEdges]
  );

  const [nodes, setNodes] = useState<Node[]>(allNodes);
  const [edges, setEdges] = useState<Edge[]>(allEdges);

  useEffect(() => {
    setNodes(allNodes);
    setEdges(allEdges);
  }, [allNodes, allEdges]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) =>
      setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.id.startsWith("comp-") || node.id.startsWith("load-")) return;
      setSelectedBusId(node.id);
      setSelectedBranchId(null);
    },
    []
  );

  const onEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      if (edge.id.startsWith("comp-edge-") || edge.id.startsWith("load-edge-")) return;
      setSelectedBranchId(edge.id);
      setSelectedBusId(null);
    },
    []
  );

  const onPaneClick = useCallback(() => {
    setSelectedBusId(null);
    setSelectedBranchId(null);
  }, []);

  // Save bus positions on drag end
  const onNodeDragStop = useCallback(
    (_: unknown, node: Node) => {
      if (!node.id.startsWith("comp-") && !node.id.startsWith("load-")) {
        updateBus(projectId, node.id, {
          x_position: node.position.x,
          y_position: node.position.y,
        }).catch(() => {});
      }
    },
    [projectId, updateBus]
  );

  return (
    <div className="flex-1 flex flex-col">
      <NetworkRecommendationsBar
        recommendations={networkRecommendations}
        powerFlowResult={powerFlowResult}
        projectId={projectId}
      />
      <NetworkToolbar projectId={projectId} />
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 relative" style={{ minHeight: "500px" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            onNodeDragStop={onNodeDragStop}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            className="bg-background"
          >
            <Background color="hsl(217.2 32.6% 17.5%)" gap={20} />
            <Controls className="!bg-card !border-border !text-foreground [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground" />
            <MiniMap
              className="!bg-card !border-border"
              nodeColor={(node) => node.id.startsWith("load-") ? "#ec4899" : "#3b82f6"}
              maskColor="hsla(222.2, 84%, 4.9%, 0.7)"
            />
          </ReactFlow>
        </div>
        <div className="w-80 border-l border-border flex flex-col">
          {/* Tab switcher */}
          <div className="flex border-b border-border shrink-0">
            <button
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                rightTab === "network"
                  ? "text-foreground border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setRightTab("network")}
            >
              Network
            </button>
            <button
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                rightTab === "components"
                  ? "text-foreground border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setRightTab("components")}
            >
              Components
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {rightTab === "network" ? (
              <BusDetailPanel
                projectId={projectId}
                selectedBusId={selectedBusId}
                selectedBranchId={selectedBranchId}
                onClose={() => {
                  setSelectedBusId(null);
                  setSelectedBranchId(null);
                }}
              />
            ) : (
              <ComponentPanel
                projectId={projectId}
                selectedId={selectedComponentId}
                onSelect={setSelectedComponentId}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
