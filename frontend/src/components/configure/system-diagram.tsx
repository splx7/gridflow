"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Node,
  Edge,
  NodeTypes,
  Handle,
  Position,
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Component, ComponentType, LoadProfile } from "@/types";

const COMPONENT_ICONS: Record<ComponentType, string> = {
  solar_pv: "PV",
  wind_turbine: "Wind",
  battery: "Batt",
  diesel_generator: "Gen",
  inverter: "Inv",
  grid_connection: "Grid",
};

const COMPONENT_COLORS: Record<ComponentType, string> = {
  solar_pv: "#f59e0b",
  wind_turbine: "#3b82f6",
  battery: "#10b981",
  diesel_generator: "#ef4444",
  inverter: "#06b6d4",
  grid_connection: "#8b5cf6",
};

const LOAD_COLOR = "#ec4899";

function ComponentNode({ data }: { data: { label: string; type: ComponentType; config: Record<string, unknown> } }) {
  const color = COMPONENT_COLORS[data.type] || "#6b7280";
  const icon = COMPONENT_ICONS[data.type] || "?";

  return (
    <div
      className="bg-card border-2 rounded-xl p-4 min-w-[140px] text-center cursor-pointer hover:shadow-lg transition-shadow"
      style={{ borderColor: color }}
    >
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2 text-white text-xs font-bold"
        style={{ backgroundColor: color }}
      >
        {icon}
      </div>
      <div className="text-sm font-medium text-foreground">{data.label}</div>
      <div className="text-xs text-muted-foreground mt-1">
        {data.type === "solar_pv" && `${data.config.capacity_kw || data.config.capacity_kwp || 0} kWp`}
        {data.type === "wind_turbine" && `${data.config.rated_power_kw || 0} kW`}
        {data.type === "battery" && `${data.config.capacity_kwh || 0} kWh`}
        {data.type === "diesel_generator" && `${data.config.rated_power_kw || 0} kW`}
        {data.type === "grid_connection" && "Utility"}
      </div>
    </div>
  );
}

function LoadNode({ data }: { data: { label: string; annualKwh: number } }) {
  return (
    <div
      className="bg-card border-2 rounded-xl p-4 min-w-[140px] text-center cursor-default"
      style={{ borderColor: LOAD_COLOR }}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2 text-white text-xs font-bold"
        style={{ backgroundColor: LOAD_COLOR }}
      >
        Load
      </div>
      <div className="text-sm font-medium text-foreground">{data.label}</div>
      <div className="text-xs text-muted-foreground mt-1">
        {data.annualKwh.toLocaleString()} kWh/yr
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  component: ComponentNode,
  load: LoadNode,
};

// Layout positions for different component types
const LAYOUT_POSITIONS: Record<ComponentType, { x: number; y: number }> = {
  solar_pv: { x: 50, y: 50 },
  wind_turbine: { x: 50, y: 220 },
  battery: { x: 350, y: 300 },
  diesel_generator: { x: 50, y: 390 },
  inverter: { x: 350, y: 130 },
  grid_connection: { x: 600, y: 50 },
};

const LOAD_BASE_POSITION = { x: 600, y: 300 };

interface SystemDiagramProps {
  components: Component[];
  loadProfiles: LoadProfile[];
  onSelect: (id: string | null) => void;
}

export default function SystemDiagram({ components, loadProfiles, onSelect }: SystemDiagramProps) {
  const busNode: Node = {
    id: "bus",
    type: "default",
    position: { x: 350, y: 130 },
    data: { label: "AC Bus" },
    style: {
      background: "hsl(222.2 84% 4.9%)",
      border: "2px solid hsl(217.2 32.6% 17.5%)",
      borderRadius: "8px",
      color: "hsl(210 40% 98%)",
      fontWeight: "bold",
      padding: "12px 24px",
    },
  };

  const buildComponentNodes = (prevNodes: Node[]): Node[] =>
    components.map((comp, idx) => {
      const basePos = LAYOUT_POSITIONS[comp.component_type as ComponentType] || { x: 50, y: 50 + idx * 170 };
      const sameTypeBefore = components.filter(
        (c, i) => i < idx && c.component_type === comp.component_type
      ).length;
      const existing = prevNodes.find((n) => n.id === comp.id);
      return {
        id: comp.id,
        type: "component",
        position: existing?.position ?? { x: basePos.x, y: basePos.y + sameTypeBefore * 170 },
        data: {
          label: comp.name,
          type: comp.component_type as ComponentType,
          config: comp.config,
        },
      };
    });

  const buildLoadNodes = (prevNodes: Node[]): Node[] =>
    loadProfiles.map((lp, idx) => {
      const existing = prevNodes.find((n) => n.id === `load-${lp.id}`);
      return {
        id: `load-${lp.id}`,
        type: "load",
        position: existing?.position ?? { x: LOAD_BASE_POSITION.x, y: LOAD_BASE_POSITION.y + idx * 170 },
        data: {
          label: lp.name,
          annualKwh: lp.annual_kwh,
        },
      };
    });

  const buildEdges = (): Edge[] => {
    const compEdges: Edge[] = components.map((comp) => ({
      id: `e-${comp.id}-bus`,
      source: comp.id,
      target: "bus",
      animated: true,
      style: { stroke: COMPONENT_COLORS[comp.component_type as ComponentType] || "#6b7280" },
    }));
    const loadEdges: Edge[] = loadProfiles.map((lp) => ({
      id: `e-bus-load-${lp.id}`,
      source: "bus",
      target: `load-${lp.id}`,
      animated: true,
      style: { stroke: LOAD_COLOR, strokeDasharray: "6 3" },
    }));
    return [...compEdges, ...loadEdges];
  };

  const [nodes, setNodes] = useState<Node[]>([
    busNode,
    ...buildComponentNodes([]),
    ...buildLoadNodes([]),
  ]);
  const [edgeState, setEdges] = useState<Edge[]>(buildEdges());

  useEffect(() => {
    setNodes((prev) => [busNode, ...buildComponentNodes(prev), ...buildLoadNodes(prev)]);
    setEdges(buildEdges());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [components, loadProfiles]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.id !== "bus" && !node.id.startsWith("load-")) {
        onSelect(node.id);
      }
    },
    [onSelect]
  );

  return (
    <div className="w-full h-full" style={{ minHeight: "500px" }}>
      <ReactFlow
        nodes={nodes}
        edges={edgeState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        className="bg-background"
      >
        <Background color="hsl(217.2 32.6% 17.5%)" gap={20} />
        <Controls className="!bg-card !border-border !text-foreground [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground" />
      </ReactFlow>
    </div>
  );
}
