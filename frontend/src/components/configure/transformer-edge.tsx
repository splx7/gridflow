"use client";

import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

interface TransformerEdgeData {
  label: string;
  ratingKva?: number;
  flowKw?: number;
  loadingPct?: number;
  lossKw?: number;
}

function TransformerEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}: EdgeProps & { data?: TransformerEdgeData }) {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  const loading = data?.loadingPct ?? 0;
  const strokeColor = loading > 90 ? "#ef4444" : loading > 70 ? "#eab308" : "#8b5cf6";

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
            {/* Transformer IEC symbol: two overlapping circles */}
            <div className="flex justify-center mb-0.5">
              <svg width="24" height="16" viewBox="0 0 24 16">
                <circle cx="8" cy="8" r="6" fill="none" stroke={strokeColor} strokeWidth="1.5" />
                <circle cx="16" cy="8" r="6" fill="none" stroke={strokeColor} strokeWidth="1.5" />
              </svg>
            </div>
            <div className="text-[10px] font-medium text-foreground">{data?.label || "Tx"}</div>
            {data?.ratingKva !== undefined && (
              <div className="text-[10px] text-muted-foreground font-mono">
                {data.ratingKva >= 1000
                  ? `${(data.ratingKva / 1000).toFixed(1)} MVA`
                  : `${data.ratingKva} kVA`}
              </div>
            )}
            {data?.flowKw !== undefined && (
              <div className="text-[10px] text-muted-foreground font-mono">
                {data.flowKw.toFixed(0)} kW
              </div>
            )}
            {data?.loadingPct !== undefined && (
              <div className="text-[10px] font-mono" style={{ color: strokeColor }}>
                {data.loadingPct.toFixed(0)}% loaded
              </div>
            )}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export default memo(TransformerEdgeComponent);
