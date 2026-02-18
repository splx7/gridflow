"use client";

import { useState, useMemo, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AlertTriangle, ChevronDown, ChevronRight, Info, Loader2, Play, ShieldCheck, ShieldAlert, Zap } from "lucide-react";
import { toast } from "sonner";
import type { NetworkResultsData, ContingencyAnalysisResult, ContingencyItem, GridCodeSummary } from "@/types";
import { runContingencyAnalysis, listGridCodes, getErrorMessage } from "@/lib/api";
import { HelpIcon } from "@/components/ui/help-drawer";
import { ChartExportButton } from "./chart-export-button";

const LINE_COLORS = [
  "#3b82f6", "#f59e0b", "#10b981", "#a855f7", "#ef4444",
  "#8b5cf6", "#ec4899", "#6366f1", "#14b8a6", "#f97316",
];

interface NetworkResultsPanelProps {
  data: NetworkResultsData;
  projectId?: string;
}

function voltageBadge(v: number) {
  if (v < 0.9 || v > 1.1) return { text: `${v.toFixed(3)} pu`, variant: "destructive" as const };
  if (v < 0.95 || v > 1.05) return { text: `${v.toFixed(3)} pu`, variant: "secondary" as const };
  return { text: `${v.toFixed(3)} pu`, variant: "default" as const };
}

function loadingBadge(pct: number) {
  if (pct > 100) return { text: `${pct.toFixed(1)}%`, variant: "destructive" as const };
  if (pct > 80) return { text: `${pct.toFixed(1)}%`, variant: "secondary" as const };
  return { text: `${pct.toFixed(1)}%`, variant: "default" as const };
}

/** Branch type display label */
function branchTypeLabel(t: string) {
  switch (t) {
    case "cable": return "Cable";
    case "transformer": return "Xfmr";
    case "line": return "Line";
    case "inverter": return "Inv";
    default: return t;
  }
}

/** Severity for a contingency item */
function contingencySeverity(r: ContingencyItem): "critical" | "warning" | "pass" {
  if (r.causes_islanding || !r.converged) return "critical";
  if (r.min_voltage_pu < 0.85 || r.max_loading_pct > 150) return "critical";
  if (!r.passed) return "warning";
  return "pass";
}

/** Suggestion text based on violation type */
function violationAdvice(r: ContingencyItem): string | null {
  if (r.causes_islanding) {
    return "Removing this branch disconnects part of the network. Consider adding a redundant parallel feeder or ring topology to maintain supply.";
  }
  if (!r.converged) {
    return "Power flow did not converge — indicates potential voltage collapse. Increase generation capacity or add reactive power support near load centers.";
  }
  const issues: string[] = [];
  if (r.voltage_violations.length > 0) {
    issues.push("Voltage outside limits — upgrade cables to reduce impedance, or install a capacitor bank / voltage regulator at the affected bus.");
  }
  if (r.thermal_violations.length > 0) {
    issues.push("Branch overloaded — replace with a higher-rated cable/transformer, or split the load across parallel paths.");
  }
  return issues.length > 0 ? issues.join(" ") : null;
}

/** Expandable contingency table row */
function ContingencyRow({
  item: r,
  hasDetails,
  isExpanded,
  onToggle,
}: {
  item: ContingencyItem;
  hasDetails: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const severity = contingencySeverity(r);
  const advice = violationAdvice(r);
  const rowBg = severity === "critical"
    ? "bg-red-500/5"
    : severity === "warning"
    ? "bg-orange-500/5"
    : "";

  return (
    <>
      <tr
        className={`border-b border-border/50 ${rowBg} ${hasDetails ? "cursor-pointer hover:bg-muted/30" : ""}`}
        onClick={hasDetails ? onToggle : undefined}
      >
        <td className="py-2 px-1 text-center">
          {hasDetails && (
            isExpanded
              ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </td>
        <td className="py-2 px-3 font-medium">{r.branch_name}</td>
        <td className="py-2 px-2 text-center">
          <span className="text-xs text-muted-foreground">{branchTypeLabel(r.branch_type)}</span>
        </td>
        <td className="py-2 px-3 text-center">
          {r.causes_islanding ? (
            <Badge variant="secondary">Island</Badge>
          ) : !r.converged ? (
            <Badge variant="destructive">Collapse</Badge>
          ) : r.passed ? (
            <Badge variant="default">Pass</Badge>
          ) : (
            <Badge variant="destructive">Fail</Badge>
          )}
        </td>
        <td className="py-2 px-3 text-right font-mono">
          {r.causes_islanding ? "—" : r.min_voltage_pu.toFixed(4)}
        </td>
        <td className="py-2 px-3 text-right font-mono">
          {r.causes_islanding ? "—" : `${r.max_loading_pct.toFixed(1)}%`}
        </td>
      </tr>
      {isExpanded && hasDetails && (
        <tr className={rowBg}>
          <td colSpan={6} className="px-6 pb-3 pt-1">
            {/* Voltage violations */}
            {r.voltage_violations.length > 0 && (
              <div className="mb-2">
                <p className="text-xs font-medium text-muted-foreground mb-1">Voltage Violations</p>
                <div className="space-y-1">
                  {r.voltage_violations.map((v, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <AlertTriangle className="h-3 w-3 text-red-500 shrink-0" />
                      <span>
                        <span className="font-medium">{v.bus_name}</span>: {v.voltage_pu.toFixed(4)} pu
                        {" "}({v.limit_type === "low" ? "below" : "above"} limit of {v.limit_value.toFixed(2)} pu)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Thermal violations */}
            {r.thermal_violations.length > 0 && (
              <div className="mb-2">
                <p className="text-xs font-medium text-muted-foreground mb-1">Thermal Violations</p>
                <div className="space-y-1">
                  {r.thermal_violations.map((t, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <Zap className="h-3 w-3 text-orange-500 shrink-0" />
                      <span>
                        <span className="font-medium">{t.branch_name}</span>: {t.loading_pct.toFixed(1)}%
                        {" "}(limit: {t.limit_pct.toFixed(0)}%, rated {t.rating_mva.toFixed(3)} MVA)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Remediation advice */}
            {advice && (
              <div className="flex items-start gap-2 mt-2 pt-2 border-t border-border/30">
                <Info className="h-3 w-3 text-blue-400 mt-0.5 shrink-0" />
                <p className="text-xs text-muted-foreground">{advice}</p>
              </div>
            )}
          </td>
        </tr>
      )}
      {/* Inline advice for islanding/collapse (no expand needed) */}
      {!hasDetails && (r.causes_islanding || !r.converged) && advice && (
        <tr className={rowBg}>
          <td colSpan={6} className="px-6 pb-2 pt-0">
            <div className="flex items-start gap-2">
              <Info className="h-3 w-3 text-blue-400 mt-0.5 shrink-0" />
              <p className="text-xs text-muted-foreground">{advice}</p>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function NetworkResultsPanel({ data, projectId }: NetworkResultsPanelProps) {
  const [showShortCircuit, setShowShortCircuit] = useState(false);
  const [contingencyResult, setContingencyResult] = useState<ContingencyAnalysisResult | null>(null);
  const [contingencyLoading, setContingencyLoading] = useState(false);
  const [showContingency, setShowContingency] = useState(false);
  const [gridCode, setGridCode] = useState("iec_default");
  const [gridCodes, setGridCodes] = useState<GridCodeSummary[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const voltageChartRef = useRef<HTMLDivElement>(null);
  const s = data.power_flow_summary;

  const handleRunContingency = async () => {
    if (!projectId) return;
    setContingencyLoading(true);
    try {
      // Load grid codes if not yet loaded
      if (gridCodes.length === 0) {
        const codes = await listGridCodes();
        setGridCodes(codes);
      }
      const result = await runContingencyAnalysis(projectId, gridCode);
      setContingencyResult(result);
      setShowContingency(true);
    } catch (err) {
      toast.error("Contingency analysis failed: " + getErrorMessage(err));
    } finally {
      setContingencyLoading(false);
    }
  };

  // Bus voltage chart data
  const busNames = Object.keys(data.ts_bus_voltages);
  const voltageChartData = useMemo(() => {
    if (busNames.length === 0) return [];
    const len = data.ts_bus_voltages[busNames[0]]?.length ?? 0;
    const result = [];
    for (let i = 0; i < len; i++) {
      const point: Record<string, number> = { hour: i };
      for (const bus of busNames) {
        point[bus] = data.ts_bus_voltages[bus][i];
      }
      result.push(point);
    }
    return result;
  }, [data.ts_bus_voltages, busNames]);

  // Peak-hour branch flows (find the snapshot with highest total loading)
  const peakSnapshot = useMemo(() => {
    if (!s.branch_flows || s.branch_flows.length === 0) return null;
    let best = s.branch_flows[0];
    let bestMax = 0;
    for (const snap of s.branch_flows) {
      const maxLoad = Math.max(...snap.flows.map((f) => f.loading_pct), 0);
      if (maxLoad > bestMax) {
        bestMax = maxLoad;
        best = snap;
      }
    }
    return best;
  }, [s.branch_flows]);

  const scEntries = s.short_circuit ? Object.entries(s.short_circuit) : [];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Section 1: Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Min Voltage</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.min_voltage_pu.toFixed(3)}</span>
              <Badge variant={voltageBadge(s.min_voltage_pu).variant}>
                {s.min_voltage_pu < 0.95 ? "Low" : "OK"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">at {s.worst_voltage_bus}</p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Max Voltage</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.max_voltage_pu.toFixed(3)}</span>
              <Badge variant={voltageBadge(s.max_voltage_pu).variant}>
                {s.max_voltage_pu > 1.05 ? "High" : "OK"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Max Branch Loading</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.max_branch_loading_pct.toFixed(1)}%</span>
              <Badge variant={loadingBadge(s.max_branch_loading_pct).variant}>
                {s.max_branch_loading_pct > 100 ? "Overloaded" : s.max_branch_loading_pct > 80 ? "High" : "OK"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Losses</p>
            <p className="text-2xl font-bold mt-1">
              {s.total_losses_pct.toFixed(2)}%
              <span className="text-sm font-normal text-muted-foreground ml-2">
                ({s.total_losses_kw.toFixed(1)} kW)
              </span>
            </p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Voltage Violations</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.voltage_violations_count}</span>
              {s.voltage_violations_count > 0 && (
                <Badge variant="destructive">!</Badge>
              )}
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Thermal Violations</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold">{s.thermal_violations_count}</span>
              {s.thermal_violations_count > 0 && (
                <Badge variant="destructive">!</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Section 2: Bus Voltage Chart */}
      {voltageChartData.length > 0 && (
        <Card variant="glass">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Bus Voltages (per-unit)</CardTitle>
            <ChartExportButton chartRef={voltageChartRef} filename="bus-voltages" />
          </CardHeader>
          <CardContent ref={voltageChartRef}>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={voltageChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2 32.6% 17.5%)" />
                <XAxis
                  dataKey="hour"
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  tickFormatter={(v) => `${v}h`}
                />
                <YAxis
                  stroke="hsl(215 20.2% 65.1%)"
                  fontSize={11}
                  domain={["auto", "auto"]}
                  tickFormatter={(v) => v.toFixed(2)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(222.2 84% 4.9%)",
                    border: "1px solid hsl(217.2 32.6% 17.5%)",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                  }}
                  labelFormatter={(v) => `Hour ${v}`}
                  formatter={(value: number) => [value.toFixed(4), ""]}
                />
                <Legend />
                <ReferenceLine y={0.95} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "0.95", fill: "#ef4444", fontSize: 10 }} />
                <ReferenceLine y={1.05} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "1.05", fill: "#ef4444", fontSize: 10 }} />
                {busNames.map((bus, i) => (
                  <Line
                    key={bus}
                    type="monotone"
                    dataKey={bus}
                    name={bus}
                    stroke={LINE_COLORS[i % LINE_COLORS.length]}
                    strokeWidth={1.5}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Section 3: Branch Flows Table */}
      {peakSnapshot && (
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-sm">
              Branch Flows — Peak Hour {peakSnapshot.hour}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">Branch</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Power (kW)</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Losses (kW)</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Loading (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {peakSnapshot.flows.map((flow) => {
                    const lb = loadingBadge(flow.loading_pct);
                    return (
                      <tr key={flow.branch_name} className="border-b border-border/50">
                        <td className="py-2 px-3">{flow.branch_name}</td>
                        <td className="py-2 px-3 text-right font-mono">{flow.from_p_kw.toFixed(1)}</td>
                        <td className="py-2 px-3 text-right font-mono">{flow.loss_kw.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right">
                          <Badge variant={lb.variant}>{lb.text}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Section 4: N-1 Contingency Analysis */}
      {projectId && (
        <Card variant="glass">
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-sm">N-1 Contingency Analysis</CardTitle>
              <HelpIcon helpKey="network.contingency" />
            </div>
            <div className="flex items-center gap-2">
              {gridCodes.length > 0 && (
                <Select value={gridCode} onValueChange={setGridCode}>
                  <SelectTrigger className="w-36 h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {gridCodes.map((gc) => (
                      <SelectItem key={gc.key} value={gc.key}>
                        {gc.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleRunContingency}
                disabled={contingencyLoading}
              >
                {contingencyLoading ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5 mr-1" />
                )}
                {contingencyResult ? "Re-run" : "Run"}
              </Button>
            </div>
          </CardHeader>
          {contingencyResult && showContingency && (
            <CardContent className="space-y-4">
              {/* Summary banner */}
              <div className="flex items-center gap-3">
                {contingencyResult.summary.n1_secure ? (
                  <div className="flex items-center gap-2 text-emerald-500">
                    <ShieldCheck className="h-5 w-5" />
                    <span className="text-sm font-medium">N-1 Secure</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-500">
                    <ShieldAlert className="h-5 w-5" />
                    <span className="text-sm font-medium">N-1 Violations Detected</span>
                  </div>
                )}
                <span className="text-xs text-muted-foreground">
                  {contingencyResult.summary.passed}/{contingencyResult.summary.total_contingencies} passed
                  {contingencyResult.summary.islanding_cases > 0 && ` · ${contingencyResult.summary.islanding_cases} islanding`}
                </span>
              </div>

              {/* Worst-case summary cards (only when violations exist) */}
              {!contingencyResult.summary.n1_secure && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {contingencyResult.summary.worst_voltage_pu < 0.95 && (
                    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-medium text-red-500">Worst Voltage: {contingencyResult.summary.worst_voltage_pu.toFixed(3)} pu</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            at <span className="font-medium">{contingencyResult.summary.worst_voltage_bus}</span>
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Upgrade feeder cables to reduce impedance, or add reactive power compensation (capacitor bank) at the affected bus.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  {contingencyResult.summary.worst_loading_pct > 100 && (
                    <div className="rounded-lg border border-orange-500/30 bg-orange-500/5 p-3">
                      <div className="flex items-start gap-2">
                        <Zap className="h-4 w-4 text-orange-500 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-medium text-orange-500">Worst Loading: {contingencyResult.summary.worst_loading_pct.toFixed(1)}%</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            on <span className="font-medium">{contingencyResult.summary.worst_loading_branch}</span>
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Upgrade the overloaded branch to a higher-rated cable/transformer, or redistribute load across parallel paths.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Contingency table with expandable rows */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="w-6 py-2 px-1"></th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Outaged Branch</th>
                      <th className="text-center py-2 px-2 text-muted-foreground font-medium">Type</th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">Status</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">Min V (pu)</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">Max Loading</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Sort: failed first, then by severity */}
                    {[...contingencyResult.contingencies]
                      .sort((a, b) => {
                        if (a.passed !== b.passed) return a.passed ? 1 : -1;
                        return b.max_loading_pct - a.max_loading_pct;
                      })
                      .map((r) => {
                        const hasDetails = !r.causes_islanding && (r.voltage_violations.length > 0 || r.thermal_violations.length > 0);
                        const isExpanded = expandedRows.has(r.branch_name);
                        const toggleExpand = () => {
                          setExpandedRows((prev) => {
                            const next = new Set(prev);
                            if (next.has(r.branch_name)) next.delete(r.branch_name);
                            else next.add(r.branch_name);
                            return next;
                          });
                        };
                        return (
                          <ContingencyRow
                            key={r.branch_name}
                            item={r}
                            hasDetails={hasDetails}
                            isExpanded={isExpanded}
                            onToggle={toggleExpand}
                          />
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Section 5: Short Circuit (collapsible) */}
      {scEntries.length > 0 && (
        <Card variant="glass">
          <CardContent className="p-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowShortCircuit(!showShortCircuit)}
              className="w-full justify-start text-sm font-medium"
            >
              {showShortCircuit ? (
                <ChevronDown className="h-4 w-4 mr-2" />
              ) : (
                <ChevronRight className="h-4 w-4 mr-2" />
              )}
              Short Circuit Analysis ({scEntries.length} buses)
            </Button>
            {showShortCircuit && (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Bus</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">I_sc (kA)</th>
                      <th className="text-right py-2 px-3 text-muted-foreground font-medium">S_sc (MVA)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scEntries.map(([bus, sc]) => (
                      <tr key={bus} className="border-b border-border/50">
                        <td className="py-2 px-3">{bus}</td>
                        <td className="py-2 px-3 text-right font-mono">{sc.i_sc_ka.toFixed(3)}</td>
                        <td className="py-2 px-3 text-right font-mono">{sc.s_sc_mva.toFixed(3)}</td>
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
