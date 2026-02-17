import type { EconomicsResult, TimeseriesResult, NetworkResultsData } from "@/types";

function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportTimeseriesCSV(data: TimeseriesResult, simId: string) {
  const headers = ["hour", "load_kw"];
  const keys: (keyof TimeseriesResult)[] = ["load"];

  if (data.pv_output) { headers.push("pv_output_kw"); keys.push("pv_output"); }
  if (data.wind_output) { headers.push("wind_output_kw"); keys.push("wind_output"); }
  if (data.battery_power) { headers.push("battery_power_kw"); keys.push("battery_power"); }
  if (data.battery_soc) { headers.push("battery_soc"); keys.push("battery_soc"); }
  if (data.generator_output) { headers.push("generator_kw"); keys.push("generator_output"); }
  if (data.grid_import) { headers.push("grid_import_kw"); keys.push("grid_import"); }
  if (data.grid_export) { headers.push("grid_export_kw"); keys.push("grid_export"); }
  if (data.excess) { headers.push("excess_kw"); keys.push("excess"); }
  if (data.unmet) { headers.push("unmet_kw"); keys.push("unmet"); }

  const rows = [headers.join(",")];
  const len = data.load?.length ?? 8760;
  for (let i = 0; i < len; i++) {
    const vals = [String(i)];
    for (const key of keys) {
      const arr = data[key] as number[] | null;
      vals.push(arr ? String(arr[i]) : "");
    }
    rows.push(vals.join(","));
  }

  downloadCSV(rows.join("\n"), `timeseries_${simId.slice(0, 8)}.csv`);
}

export function exportEconomicsCSV(data: EconomicsResult, simId: string) {
  const rows = [
    "metric,value",
    `npc_usd,${data.npc}`,
    `lcoe_usd_per_kwh,${data.lcoe}`,
    `irr,${data.irr ?? ""}`,
    `payback_years,${data.payback_years ?? ""}`,
    `renewable_fraction,${data.renewable_fraction}`,
    `co2_emissions_kg,${data.co2_emissions_kg}`,
    "",
    "cost_category,amount_usd",
  ];
  for (const [key, value] of Object.entries(data.cost_breakdown)) {
    rows.push(`${key},${value}`);
  }

  downloadCSV(rows.join("\n"), `economics_${simId.slice(0, 8)}.csv`);
}

export function exportNetworkCSV(data: NetworkResultsData, simId: string) {
  const s = data.power_flow_summary;
  const rows = [
    "section,key,value",
    `summary,mode,${s.mode}`,
    `summary,hours_analyzed,${s.hours_analyzed}`,
    `summary,converged_count,${s.converged_count}`,
    `summary,min_voltage_pu,${s.min_voltage_pu}`,
    `summary,max_voltage_pu,${s.max_voltage_pu}`,
    `summary,worst_voltage_bus,${s.worst_voltage_bus}`,
    `summary,max_branch_loading_pct,${s.max_branch_loading_pct}`,
    `summary,total_losses_pct,${s.total_losses_pct}`,
    `summary,total_losses_kw,${s.total_losses_kw}`,
    `summary,voltage_violations,${s.voltage_violations_count}`,
    `summary,thermal_violations,${s.thermal_violations_count}`,
    "",
    "bus_name,hour,voltage_pu",
  ];

  for (const [bus, voltages] of Object.entries(data.ts_bus_voltages)) {
    for (let h = 0; h < voltages.length; h++) {
      rows.push(`${bus},${h},${voltages[h]}`);
    }
  }

  rows.push("", "branch_name,hour,power_kw,loss_kw,loading_pct");
  for (const snapshot of s.branch_flows) {
    for (const flow of snapshot.flows) {
      rows.push(
        `${flow.branch_name},${snapshot.hour},${flow.from_p_kw},${flow.loss_kw},${flow.loading_pct}`
      );
    }
  }

  if (s.short_circuit && Object.keys(s.short_circuit).length > 0) {
    rows.push("", "bus_name,i_sc_ka,s_sc_mva");
    for (const [bus, sc] of Object.entries(s.short_circuit)) {
      rows.push(`${bus},${sc.i_sc_ka},${sc.s_sc_mva}`);
    }
  }

  downloadCSV(rows.join("\n"), `network_${simId.slice(0, 8)}.csv`);
}
