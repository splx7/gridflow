"use client";

import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

interface InverterEdgeData {
  label: string;
  ratedKw?: number;
  mode?: string;
  flowKw?: number;
  loadingPct?: number;
  efficiency?: number;
}

function InverterEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}: EdgeProps & { data?: InverterEdgeData }) {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  const loading = data?.loadingPct ?? 0;
  const strokeColor =
    loading > 90 ? "#ef4444" : loading > 70 ? "#eab308" : "#22c55e";
  const mode = data?.mode ?? "GFL";
  const isGFM = mode === "GFM";

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: strokeColor,
          strokeWidth: selected ? 3 : 2,
        }}
      />

      <EdgeLabelRenderer>
        <div
          className="absolute pointer-events-all nodrag nopan"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          <div className="bg-background/90 border border-border rounded-lg px-2 py-1 text-center">
            {/* IEC inverter symbol: rectangle with ~ (AC) and = (DC) */}
            <div className="flex justify-center mb-0.5">
              <svg width="36" height="20" viewBox="0 0 36 20">
                <rect
                  x="2"
                  y="2"
                  width="32"
                  height="16"
                  rx="2"
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth="1.5"
                />
                {/* AC side (~) */}
                <text
                  x="10"
                  y="14"
                  fontSize="10"
                  fill={strokeColor}
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  ~
                </text>
                {/* Divider */}
                <line
                  x1="18"
                  y1="4"
                  x2="18"
                  y2="16"
                  stroke={strokeColor}
                  strokeWidth="1"
                  strokeDasharray="2 1"
                />
                {/* DC side (=) */}
                <text
                  x="26"
                  y="14"
                  fontSize="10"
                  fill={strokeColor}
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  =
                </text>
              </svg>
            </div>
            <div className="text-[10px] font-medium text-foreground">
              {data?.label || "Inverter"}
            </div>
            <div className="text-[10px] text-muted-foreground font-mono">
              {data?.ratedKw !== undefined && <>{data.ratedKw.toFixed(0)} kW</>}
              {isGFM && (
                <span className="ml-1 text-amber-400 font-semibold">GFM</span>
              )}
              {!isGFM && (
                <span className="ml-1 text-blue-400">GFL</span>
              )}
            </div>
            {data?.flowKw !== undefined && (
              <div className="text-[10px] text-muted-foreground font-mono">
                {data.flowKw.toFixed(0)} kW
              </div>
            )}
            {data?.loadingPct !== undefined && (
              <div
                className="text-[10px] font-mono"
                style={{ color: strokeColor }}
              >
                {data.loadingPct.toFixed(0)}% loaded
              </div>
            )}
            {data?.efficiency !== undefined && (
              <div className="text-[10px] text-muted-foreground font-mono">
                {"\u03B7"}={(data.efficiency * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export default memo(InverterEdgeComponent);
