"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import CableEdgeComponent from "./cable-edge";
import TransformerEdgeComponent from "./transformer-edge";
import NetworkToolbar from "./network-toolbar";
import BusDetailPanel from "./bus-detail-panel";
import type { Bus, Branch, Component as GridComponent } from "@/types";

const nodeTypes: NodeTypes = {
  bus: BusNodeComponent as unknown as NodeTypes["bus"],
};

const edgeTypes: EdgeTypes = {
  cable: CableEdgeComponent as unknown as EdgeTypes["cable"],
  transformer: TransformerEdgeComponent as unknown as EdgeTypes["transformer"],
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
    powerFlowResult,
    fetchBuses,
    fetchBranches,
    updateBus,
  } = useProjectStore();

  const [selectedBusId, setSelectedBusId] = useState<string | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);

  useEffect(() => {
    fetchBuses(projectId);
    fetchBranches(projectId);
  }, [projectId, fetchBuses, fetchBranches]);

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
      const isTransformer = br.branch_type === "transformer";

      return {
        id: br.id,
        source: br.from_bus_id,
        target: br.to_bus_id,
        type: isTransformer ? "transformer" : "cable",
        selected: br.id === selectedBranchId,
        data: isTransformer
          ? {
              label: br.name,
              ratingKva: br.config.rating_kva as number,
              flowKw: flow?.from_kw,
              loadingPct: flow?.loading_pct,
              lossKw: flow?.loss_kw,
            }
          : {
              label: br.name,
              vdPct: flow?.vd_pct,
              flowKw: flow?.from_kw,
              loadingPct: flow?.loading_pct,
            },
      };
    });
  }, [branches, powerFlowResult, selectedBranchId]);

  const allNodes = useMemo(
    () => [...busNodes, ...componentNodes],
    [busNodes, componentNodes]
  );
  const allEdges = useMemo(
    () => [...branchEdges, ...componentEdges],
    [branchEdges, componentEdges]
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
      if (node.id.startsWith("comp-")) return;
      setSelectedBusId(node.id);
      setSelectedBranchId(null);
    },
    []
  );

  const onEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      if (edge.id.startsWith("comp-edge-")) return;
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
      if (!node.id.startsWith("comp-")) {
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
              nodeColor={() => "#3b82f6"}
              maskColor="hsla(222.2, 84%, 4.9%, 0.7)"
            />
          </ReactFlow>
        </div>
        <div className="w-80 border-l border-border overflow-y-auto">
          <BusDetailPanel
            projectId={projectId}
            selectedBusId={selectedBusId}
            selectedBranchId={selectedBranchId}
            onClose={() => {
              setSelectedBusId(null);
              setSelectedBranchId(null);
            }}
          />
        </div>
      </div>
    </div>
  );
}
