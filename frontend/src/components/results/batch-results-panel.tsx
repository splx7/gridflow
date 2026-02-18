"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { listBatches, getBatchStatus, getErrorMessage } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Layers, RefreshCw } from "lucide-react";

interface BatchRun {
  id: string;
  name: string;
  status: string;
  total_runs: number;
  completed_runs: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

interface BatchResult {
  simulation_id: string;
  simulation_name: string;
  status: string;
  params: Record<string, number>;
  npc?: number;
  lcoe?: number;
  irr?: number | null;
  payback_years?: number | null;
  renewable_fraction?: number;
}

interface BatchDetail extends BatchRun {
  results: BatchResult[];
}

interface Props {
  projectId: string;
}

const statusColor: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

const fmt = (v: number | undefined | null) => {
  if (v == null) return "-";
  return v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(1)}k` : `$${v.toFixed(0)}`;
};

export default function BatchResultsPanel({ projectId }: Props) {
  const [batches, setBatches] = useState<BatchRun[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<string>("npc");
  const [sortAsc, setSortAsc] = useState(true);

  const fetchBatches = async () => {
    try {
      const data = await listBatches(projectId);
      setBatches(data as unknown as BatchRun[]);
    } catch (err) {
      const msg = getErrorMessage(err);
      if (!msg.includes("404")) toast.error("Failed to load batches: " + msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const loadBatchDetail = async (batchId: string) => {
    try {
      const data = await getBatchStatus(projectId, batchId);
      setSelectedBatch(data as unknown as BatchDetail);
    } catch (err) {
      toast.error("Failed to load batch: " + getErrorMessage(err));
    }
  };

  const sortedResults = selectedBatch?.results
    ? [...selectedBatch.results].sort((a, b) => {
        const aVal = (a as unknown as Record<string, unknown>)[sortKey];
        const bVal = (b as unknown as Record<string, unknown>)[sortKey];
        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return 1;
        if (bVal == null) return -1;
        return sortAsc ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
      })
    : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (batches.length === 0) {
    return (
      <Card variant="glass">
        <CardContent className="py-8 text-center text-muted-foreground">
          <Layers className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No batch runs yet.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Batch List */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Batch Runs</h4>
        <Button variant="ghost" size="sm" onClick={fetchBatches}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="space-y-2">
        {batches.map((b) => (
          <Card
            key={b.id}
            variant="glass"
            className="cursor-pointer card-lift"
            onClick={() => loadBatchDetail(b.id)}
          >
            <CardContent className="py-3 flex items-center justify-between">
              <div>
                <span className="font-medium text-sm">{b.name}</span>
                <span className="text-xs text-muted-foreground ml-3">
                  {b.completed_runs}/{b.total_runs} runs
                </span>
              </div>
              <Badge className={statusColor[b.status] || ""}>{b.status}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Batch Detail */}
      {selectedBatch && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              {selectedBatch.name}
              <Badge className={statusColor[selectedBatch.status] || ""}>
                {selectedBatch.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sortedResults.length === 0 ? (
              <p className="text-muted-foreground text-sm">No results yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Parameters</th>
                      {["npc", "lcoe", "irr", "renewable_fraction"].map((key) => (
                        <th
                          key={key}
                          className="text-right py-2 px-3 font-medium cursor-pointer hover:text-primary"
                          onClick={() => {
                            if (sortKey === key) setSortAsc(!sortAsc);
                            else { setSortKey(key); setSortAsc(true); }
                          }}
                        >
                          {key === "npc" ? "NPC" : key === "lcoe" ? "LCOE" : key === "irr" ? "IRR" : "RE%"}
                          {sortKey === key && (sortAsc ? " ↑" : " ↓")}
                        </th>
                      ))}
                      <th className="text-right py-2 px-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedResults.map((r) => (
                      <tr key={r.simulation_id} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2 px-3 text-xs font-mono">
                          {Object.entries(r.params).map(([k, v]) => `${k}=${v}`).join(", ")}
                        </td>
                        <td className="text-right py-2 px-3 font-mono">{fmt(r.npc)}</td>
                        <td className="text-right py-2 px-3 font-mono">{r.lcoe != null ? `$${r.lcoe.toFixed(3)}` : "-"}</td>
                        <td className="text-right py-2 px-3 font-mono">{r.irr != null ? `${(r.irr * 100).toFixed(1)}%` : "-"}</td>
                        <td className="text-right py-2 px-3 font-mono">{r.renewable_fraction != null ? `${(r.renewable_fraction * 100).toFixed(1)}%` : "-"}</td>
                        <td className="text-right py-2 px-3">
                          <Badge className={`text-xs ${statusColor[r.status] || ""}`}>{r.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
