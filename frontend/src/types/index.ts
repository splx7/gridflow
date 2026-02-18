// Core types for GridFlow frontend

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export type NetworkMode = "single_bus" | "multi_bus";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  latitude: number;
  longitude: number;
  lifetime_years: number;
  discount_rate: number;
  currency: string;
  network_mode: NetworkMode;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  lifetime_years?: number;
  discount_rate?: number;
  currency?: string;
  network_mode?: NetworkMode;
  [key: string]: unknown;
}

export type ComponentType =
  | "solar_pv"
  | "wind_turbine"
  | "battery"
  | "diesel_generator"
  | "inverter"
  | "grid_connection";

export interface Component {
  id: string;
  project_id: string;
  component_type: ComponentType;
  name: string;
  config: Record<string, unknown>;
  bus_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SolarPVConfig {
  type: "solar_pv";
  capacity_kwp: number;
  tilt_deg: number;
  azimuth_deg: number;
  module_type: string;
  inverter_efficiency: number;
  inverter_capacity_kw: number | null;   // null = same as capacity_kwp (DC/AC ratio = 1.0)
  inverter_cost_per_kw: number;          // $/kW, separate from panel cost
  system_losses: number;
  capital_cost_per_kw: number;           // Panel + BOS cost (excl. inverter)
  om_cost_per_kw_year: number;
  lifetime_years: number;
  derating_factor: number;
}

export interface WindTurbineConfig {
  type: "wind_turbine";
  rated_power_kw: number;
  hub_height_m: number;
  rotor_diameter_m: number;
  cut_in_speed: number;
  cut_out_speed: number;
  rated_speed: number;
  power_curve: [number, number][] | null;
  quantity: number;
  capital_cost_per_kw: number;
  om_cost_per_kw_year: number;
  lifetime_years: number;
}

export interface BatteryConfig {
  type: "battery";
  capacity_kwh: number;
  max_charge_rate_kw: number;
  max_discharge_rate_kw: number;
  round_trip_efficiency: number;
  inverter_capacity_kw: number | null;   // null = max(charge_rate, discharge_rate)
  inverter_cost_per_kw: number;          // $/kW, separate from battery cell cost
  min_soc: number;
  max_soc: number;
  initial_soc: number;
  chemistry: string;
  cycle_life: number;
  capital_cost_per_kwh: number;          // Battery cells only (excl. inverter)
  replacement_cost_per_kwh: number;
  om_cost_per_kwh_year: number;
  lifetime_years: number;
}

export interface DieselGeneratorConfig {
  type: "diesel_generator";
  rated_power_kw: number;
  min_load_ratio: number;
  fuel_curve_a0: number;
  fuel_curve_a1: number;
  fuel_price_per_liter: number;
  capital_cost_per_kw: number;
  om_cost_per_hour: number;
  lifetime_hours: number;
  start_cost: number;
}

export interface InverterConfig {
  type: "inverter";
  rated_power_kw: number;
  efficiency: number;
  mode: "grid_following" | "grid_forming";
  bidirectional: boolean;
  reactive_power_capability_pct: number;
  capital_cost_per_kw: number;
  om_cost_per_kw_year: number;
  lifetime_years: number;
}

export interface GridConnectionConfig {
  type: "grid_connection";
  max_import_kw: number;
  max_export_kw: number;
  sell_back_enabled: boolean;
  net_metering: boolean;
  buy_rate: number;
  sell_rate: number;
  demand_charge: number;
  tou_schedule: Record<string, unknown> | null;
}

export type ComponentConfig =
  | SolarPVConfig
  | WindTurbineConfig
  | BatteryConfig
  | DieselGeneratorConfig
  | InverterConfig
  | GridConnectionConfig;

export interface WeatherDataset {
  id: string;
  project_id: string;
  name: string;
  source: string;
  correction_applied: boolean;
  created_at: string;
}

export interface LoadProfile {
  id: string;
  project_id: string;
  name: string;
  profile_type: string;
  annual_kwh: number;
  created_at: string;
}

export type SimulationStatus = "pending" | "running" | "completed" | "failed";
export type DispatchStrategy =
  | "load_following"
  | "cycle_charging"
  | "combined"
  | "optimal";

export interface Simulation {
  id: string;
  project_id: string;
  name: string;
  status: SimulationStatus;
  dispatch_strategy: DispatchStrategy;
  progress: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SimulationCreate {
  name: string;
  dispatch_strategy: DispatchStrategy;
  weather_dataset_id: string;
  load_profile_id: string;
}

export interface EconomicsResult {
  npc: number;
  lcoe: number;
  irr: number | null;
  payback_years: number | null;
  renewable_fraction: number;
  co2_emissions_kg: number;
  cost_breakdown: Record<string, number>;
}

export interface TimeseriesResult {
  load: number[];
  pv_output: number[] | null;
  wind_output: number[] | null;
  battery_soc: number[] | null;
  battery_power: number[] | null;
  generator_output: number[] | null;
  grid_import: number[] | null;
  grid_export: number[] | null;
  excess: number[] | null;
  unmet: number[] | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Advisor types
export interface GoalWeights {
  cost: number;
  renewables: number;
  reliability: number;
  roi: number;
}

export interface AdvisorRequest {
  load_profile_id?: string | null;
  scenario?: string | null;
  annual_kwh?: number | null;
  peak_kw?: number | null;
  daytime_fraction?: number | null;
  goals: GoalWeights;
  grid_available: boolean;
  budget_ceiling?: number | null;
}

export interface AdvisorComponentSpec {
  component_type: ComponentType;
  name: string;
  config: Record<string, unknown>;
}

export interface AdvisorEstimates {
  estimated_npc: number;
  estimated_lcoe: number;
  estimated_renewable_fraction: number;
  estimated_payback_years: number | null;
  estimated_capital_cost: number;
  estimated_co2_reduction_pct: number;
}

export interface AdvisorGoalScores {
  cost: number;
  renewables: number;
  reliability: number;
  roi: number;
}

export interface AdvisorRecommendation {
  name: string;
  description: string;
  best_for: string;
  components: AdvisorComponentSpec[];
  estimates: AdvisorEstimates;
  goal_scores: AdvisorGoalScores;
}

export interface AdvisorResponse {
  recommendations: AdvisorRecommendation[];
  load_summary: { annual_kwh: number; peak_kw: number; daytime_fraction: number };
  solar_resource: { peak_sun_hours: number; estimated_cf: number };
}

// System Health types
export interface SystemWarning {
  level: "critical" | "warning" | "info";
  code: string;
  message: string;
  detail: string;
}

export interface SystemEvaluateRequest {
  components: { component_type: string; config: Record<string, unknown> }[];
  load_summary: { annual_kwh: number; peak_kw: number; daytime_fraction: number };
  solar_resource: { peak_sun_hours: number; estimated_cf: number };
}

export interface SystemHealthResult {
  estimates: AdvisorEstimates;
  warnings: SystemWarning[];
}

// Network topology types
export type BusType = "slack" | "pv" | "pq";

export interface Bus {
  id: string;
  project_id: string;
  name: string;
  bus_type: BusType;
  nominal_voltage_kv: number;
  base_mva: number;
  x_position: number | null;
  y_position: number | null;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BusCreate {
  name: string;
  bus_type?: BusType;
  nominal_voltage_kv?: number;
  base_mva?: number;
  x_position?: number | null;
  y_position?: number | null;
  config?: Record<string, unknown>;
}

export type BranchType = "cable" | "line" | "transformer" | "inverter";

export interface Branch {
  id: string;
  project_id: string;
  from_bus_id: string;
  to_bus_id: string;
  branch_type: BranchType;
  name: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BranchCreate {
  from_bus_id: string;
  to_bus_id: string;
  branch_type: BranchType;
  name: string;
  config?: Record<string, unknown>;
}

export interface LoadAllocation {
  id: string;
  project_id: string;
  load_profile_id: string;
  bus_id: string;
  name: string;
  fraction: number;
  power_factor: number;
  created_at: string;
}

export interface LoadAllocationCreate {
  load_profile_id: string;
  bus_id: string;
  name: string;
  fraction?: number;
  power_factor?: number;
}

export interface CableSpec {
  name: string;
  size_mm2: number;
  cores: number;
  material: string;
  voltage_class: string;
  insulation: string;
  r_ohm_per_km: number;
  x_ohm_per_km: number;
  ampacity_a: number;
  max_voltage_kv: number;
}

export interface TransformerSpec {
  name: string;
  rating_kva: number;
  hv_kv: number;
  lv_kv: number;
  impedance_pct: number;
  x_r_ratio: number;
  vector_group: string;
  no_load_loss_kw: number;
  load_loss_kw: number;
}

// Recommendation action for network fixes
export interface RecommendationAction {
  type: string;
  target_id: string | null;
  target_name: string;
  field: string;
  old_value: unknown;
  new_value: unknown;
  description: string;
  cable_params?: {
    name: string;
    r_ohm_per_km: number;
    x_ohm_per_km: number;
    ampacity_a: number;
  } | null;
}

// Network auto-generate types
export interface NetworkRecommendation {
  level: "info" | "warning" | "error";
  code: string;
  message: string;
  suggestion: string;
  action?: RecommendationAction | null;
}

export interface AutoGenerateResponse {
  buses: Bus[];
  branches: Branch[];
  load_allocations: LoadAllocation[];
  recommendations: NetworkRecommendation[];
}

export interface AutoGenerateRequest {
  mv_voltage_kv?: number;
  lv_voltage_kv?: number;
  cable_material?: "Cu" | "Al";
  cable_length_km?: number;
}

// Power flow result types
export interface BranchFlowSummary {
  from_kw: number;
  to_kw: number;
  loss_kw: number;
  vd_pct: number;
  loading_pct: number;
}

export interface VoltageViolation {
  bus_id: string;
  bus_name: string;
  hour: number | null;
  voltage_pu: number;
  limit: "low" | "high";
}

export interface ThermalViolation {
  branch_id: string;
  branch_name: string;
  hour: number | null;
  loading_pct: number;
  rating_mva: number;
}

export interface ShortCircuitBus {
  i_sc_ka: number;
  s_sc_mva: number;
}

export interface PowerFlowSummary {
  min_voltage_pu: number;
  max_voltage_pu: number;
  worst_voltage_bus: string;
  max_branch_loading_pct: number;
  total_losses_pct: number;
  total_losses_kw: number;
}

export interface PowerFlowResult {
  converged: boolean;
  iterations: number;
  bus_voltages: Record<string, number>;
  branch_flows: Record<string, BranchFlowSummary>;
  voltage_violations: VoltageViolation[];
  thermal_violations: ThermalViolation[];
  short_circuit: Record<string, ShortCircuitBus>;
  summary: PowerFlowSummary;
  recommendations?: NetworkRecommendation[];
}

// Sensitivity analysis types
export interface SensitivityVariable {
  name: string;
  param_path: string;
  range: [number, number];
  points: number;
}

export interface SensitivitySpiderPoint {
  value: number;
  npc: number | null;
  lcoe: number | null;
  irr: number | null;
  payback_years: number | null;
}

export interface SensitivityTornadoEntry {
  low_value: number;
  high_value: number;
  low_npc: number | null;
  high_npc: number | null;
  low_lcoe: number | null;
  high_lcoe: number | null;
  low_irr: number | null;
  high_irr: number | null;
  base_npc: number | null;
  base_lcoe: number | null;
  base_irr: number | null;
  npc_spread: number;
}

export interface SensitivityResult {
  spider: Record<string, SensitivitySpiderPoint[]>;
  tornado: Record<string, SensitivityTornadoEntry>;
  base_results: {
    npc: number | null;
    lcoe: number | null;
    irr: number | null;
    payback_years: number | null;
  };
}

// Contingency analysis types — matches backend ContingencyResponse exactly
export interface ContingencyVoltageViolation {
  bus_name: string;
  bus_index: number;
  voltage_pu: number;
  limit_type: string;
  limit_value: number;
}

export interface ContingencyThermalViolation {
  branch_name: string;
  branch_index: number;
  loading_pct: number;
  rating_mva: number;
  limit_pct: number;
}

export interface ContingencyItem {
  branch_name: string;
  branch_index: number;
  branch_type: string;
  passed: boolean;
  converged: boolean;
  causes_islanding: boolean;
  min_voltage_pu: number;
  max_voltage_pu: number;
  max_loading_pct: number;
  voltage_violations: ContingencyVoltageViolation[];
  thermal_violations: ContingencyThermalViolation[];
}

export interface ContingencySummary {
  total_contingencies: number;
  passed: number;
  failed: number;
  islanding_cases: number;
  worst_voltage_pu: number;
  worst_voltage_bus: string;
  worst_loading_pct: number;
  worst_loading_branch: string;
  n1_secure: boolean;
}

export interface ContingencyAnalysisResult {
  grid_code: string;
  summary: ContingencySummary;
  contingencies: ContingencyItem[];
}

// BESS Sizing Recommendation
export interface BESSRecommendation {
  recommended_capacity_kwh: number;
  recommended_max_power_kw: number;
  recommended_charge_rate_kw: number;
  recommended_discharge_rate_kw: number;
  projected_unmet_fraction: number;
  projected_re_fraction: number;
  projected_shifted_kwh: number;
  analysis: {
    total_surplus_kwh: number;
    total_deficit_kwh: number;
    peak_surplus_kw: number;
    peak_deficit_kw: number;
    avg_daily_surplus_kwh: number;
    avg_daily_deficit_kwh: number;
    current_unmet_fraction: number;
    current_re_fraction: number;
  };
  notes: string[];
}

// Grid code profile summary — matches backend GridCodeProfileSummary
export interface GridCodeSummary {
  key: string;
  name: string;
  standard: string;
  voltage_normal: [number, number];
  thermal_limit_pct: number;
  frequency_nominal_hz: number;
}

// Project & Component Template types
export interface ProjectTemplateSummary {
  id: string;
  name: string;
  description: string;
  category: string;
  component_count: number;
  location: { latitude: number; longitude: number };
}

export interface ProjectTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  project: {
    latitude: number;
    longitude: number;
    lifetime_years: number;
    discount_rate: number;
  };
  components: {
    component_type: string;
    name: string;
    config: Record<string, unknown>;
  }[];
  load: { scenario: string; annual_kwh: number };
}

export interface ComponentTemplate {
  id: string;
  name: string;
  description: string;
  config: Record<string, unknown>;
}

// Network simulation results (from completed simulation)
export interface NetworkResultsData {
  power_flow_summary: {
    mode: string;
    hours_analyzed: number;
    converged_count: number;
    min_voltage_pu: number;
    max_voltage_pu: number;
    worst_voltage_bus: string;
    max_branch_loading_pct: number;
    total_losses_pct: number;
    total_losses_kw: number;
    voltage_violations_count: number;
    thermal_violations_count: number;
    short_circuit: Record<string, { i_sc_ka: number; s_sc_mva: number }>;
    branch_flows: Array<{
      hour: number;
      flows: Array<{
        branch_name: string;
        from_p_kw: number;
        loss_kw: number;
        loading_pct: number;
      }>;
    }>;
  };
  ts_bus_voltages: Record<string, number[]>;
}
