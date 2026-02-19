"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

interface LoadNodeData {
  label: string;
  annualKwh?: number;
  powerFactor?: number;
  fractionPct?: number;
}

function LoadNodeComponent({ data }: NodeProps & { data: LoadNodeData }) {
  return (
    <div className="relative">
      <Handle type="target" position={Position.Top} className="!bg-pink-500 !w-3 !h-3" />

      <div
        className="relative px-3 py-2 min-w-[160px] border-2 rounded-md"
        style={{
          borderColor: "#ec4899",
          backgroundColor: "hsl(222.2 84% 4.9%)",
        }}
      >
        {/* IEEE load symbol triangle */}
        <div className="flex items-center gap-2 mb-1">
          <span
            className="text-sm leading-none"
            style={{ color: "#ec4899" }}
          >
            ▽
          </span>
          <span className="text-xs font-bold text-foreground truncate">
            {data.label}
          </span>
        </div>

        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground font-mono">
          {data.annualKwh != null && data.annualKwh > 0 && (
            <span>
              {data.annualKwh >= 1000
                ? `${(data.annualKwh / 1000).toFixed(1)} MWh/yr`
                : `${data.annualKwh.toFixed(0)} kWh/yr`}
            </span>
          )}
          {data.powerFactor != null && (
            <span>PF={data.powerFactor.toFixed(2)}</span>
          )}
          {data.fractionPct != null && (
            <span>{data.fractionPct.toFixed(0)}%</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default memo(LoadNodeComponent);
