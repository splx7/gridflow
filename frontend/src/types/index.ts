// Core types for GridFlow frontend

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  latitude: number;
  longitude: number;
  lifetime_years: number;
  discount_rate: number;
  currency: string;
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
}

export type ComponentType =
  | "solar_pv"
  | "wind_turbine"
  | "battery"
  | "diesel_generator"
  | "grid_connection";

export interface Component {
  id: string;
  project_id: string;
  component_type: ComponentType;
  name: string;
  config: Record<string, unknown>;
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
  system_losses: number;
  capital_cost_per_kw: number;
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
  min_soc: number;
  max_soc: number;
  initial_soc: number;
  chemistry: string;
  cycle_life: number;
  capital_cost_per_kwh: number;
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
  | GridConnectionConfig;

export interface WeatherDataset {
  id: string;
  project_id: string;
  name: string;
  source: string;
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
