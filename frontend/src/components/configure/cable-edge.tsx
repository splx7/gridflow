"use client";

import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

interface CableEdgeData {
  label: string;
  vdPct?: number;
  flowKw?: number;
  loadingPct?: number;
}

function getLoadingColor(loading: number | undefined): string {
  if (loading === undefined) return "#6b7280";
  if (loading <= 70) return "#22c55e";
  if (loading <= 90) return "#eab308";
  return "#ef4444";
}

function CableEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}: EdgeProps & { data?: CableEdgeData }) {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  const strokeColor = getLoadingColor(data?.loadingPct);

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: strokeColor,
          strokeWidth: selected ? 3 : 2,
          strokeDasharray: undefined,
        }}
      />

      {/* Flow arrow (midpoint triangle) */}
      {data?.flowKw !== undefined && data.flowKw > 0 && (
        <marker
          id={`arrow-${id}`}
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={strokeColor} />
        </marker>
      )}

      <EdgeLabelRenderer>
        <div
          className="absolute pointer-events-all nodrag nopan"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          <div className="bg-background/90 border border-border rounded px-1.5 py-0.5 text-[10px] text-center space-y-0.5">
            <div className="font-medium text-foreground">{data?.label || "Cable"}</div>
            {data?.flowKw !== undefined && (
              <div className="text-muted-foreground font-mono">
                {data.flowKw.toFixed(0)} kW
              </div>
            )}
            {data?.vdPct !== undefined && (
              <div
                className="font-mono"
                style={{ color: data.vdPct > 3 ? "#ef4444" : data.vdPct > 2 ? "#eab308" : "#6b7280" }}
              >
                {data.vdPct.toFixed(1)}% Vd
              </div>
            )}
            {data?.loadingPct !== undefined && (
              <div className="font-mono" style={{ color: strokeColor }}>
                {data.loadingPct.toFixed(0)}%
              </div>
            )}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export default memo(CableEdgeComponent);
