"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { BusType } from "@/types";

interface BusNodeData {
  label: string;
  busType: BusType;
  nominalVoltageKv: number;
  voltagePu?: number;
  componentCount?: number;
  isSelected?: boolean;
}

function getVoltageColor(v: number | undefined): string {
  if (v === undefined) return "#6b7280";
  if (v >= 0.95 && v <= 1.05) return "#22c55e"; // green
  if (v >= 0.93 && v <= 1.07) return "#eab308"; // yellow
  return "#ef4444"; // red
}

const BUS_TYPE_LABELS: Record<BusType, string> = {
  slack: "Slack",
  pv: "PV",
  pq: "PQ",
};

function BusNodeComponent({ data, selected }: NodeProps & { data: BusNodeData }) {
  const voltageColor = getVoltageColor(data.voltagePu);
  const isSelected = selected || data.isSelected;

  return (
    <div className="relative">
      <Handle type="target" position={Position.Top} className="!bg-blue-500 !w-3 !h-3" />

      {/* Bus bar - thick horizontal line (IEEE standard representation) */}
      <div
        className={`
          relative px-2 py-1 min-w-[180px]
          border-2 rounded-sm
          transition-all
          ${isSelected ? "ring-2 ring-blue-500 ring-offset-1 ring-offset-background" : ""}
        `}
        style={{
          borderColor: voltageColor,
          backgroundColor: "hsl(222.2 84% 4.9%)",
        }}
      >
        {/* Thick bus bar at top */}
        <div
          className="absolute -top-[2px] left-0 right-0 h-[4px] rounded-t-sm"
          style={{ backgroundColor: voltageColor }}
        />

        <div className="flex items-center justify-between gap-2 mt-1">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-bold text-foreground">{data.label}</span>
            <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground">
              {BUS_TYPE_LABELS[data.busType]}
            </span>
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">
            {data.nominalVoltageKv >= 1
              ? `${data.nominalVoltageKv} kV`
              : `${data.nominalVoltageKv * 1000} V`}
          </span>
        </div>

        {/* Voltage badge (shown when power flow results exist) */}
        {data.voltagePu !== undefined && (
          <div className="flex items-center justify-center mt-1 mb-0.5">
            <span
              className="text-xs font-mono font-bold px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: `${voltageColor}22`,
                color: voltageColor,
              }}
            >
              {(data.voltagePu * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-blue-500 !w-3 !h-3" />
    </div>
  );
}

export default memo(BusNodeComponent);
