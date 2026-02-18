import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import type {
  AdvisorRequest,
  AdvisorResponse,
  AutoGenerateRequest,
  AutoGenerateResponse,
  BESSRecommendation,
  Branch,
  BranchCreate,
  Bus,
  BusCreate,
  CableSpec,
  Component,
  ComponentTemplate,
  ContingencyAnalysisResult,
  EconomicsResult,
  GridCodeSummary,
  LoadAllocation,
  LoadAllocationCreate,
  LoadProfile,
  PowerFlowResult,
  Project,
  ProjectCreate,
  ProjectTemplate,
  ProjectTemplateSummary,
  SensitivityResult,
  SensitivityVariable,
  Simulation,
  SimulationCreate,
  SystemEvaluateRequest,
  SystemHealthResult,
  TimeseriesResult,
  TokenResponse,
  TransformerSpec,
  User,
  WeatherDataset,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: { msg?: string }) => d.msg || String(d)).join("; ");
    }
    if (error.response?.status) {
      return `Request failed (${error.response.status})`;
    }
    if (error.code === "ERR_NETWORK") {
      return "Network error — is the backend running?";
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred";
}

function createClient(): AxiosInstance {
  const client = axios.create({
    baseURL: `${API_BASE}/api/v1`,
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401 && typeof window !== "undefined") {
        const refreshToken = localStorage.getItem("refresh_token");
        if (refreshToken && !error.config._retry) {
          error.config._retry = true;
          try {
            const resp = await axios.post(`${API_BASE}/api/v1/auth/refresh`, {
              refresh_token: refreshToken,
            });
            const tokens: TokenResponse = resp.data;
            localStorage.setItem("access_token", tokens.access_token);
            localStorage.setItem("refresh_token", tokens.refresh_token);
            error.config.headers.Authorization = `Bearer ${tokens.access_token}`;
            return client(error.config);
          } catch {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            window.location.href = "/";
          }
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
}

const api = createClient();

// Auth
export async function register(
  email: string,
  password: string,
  fullName?: string
): Promise<TokenResponse> {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    full_name: fullName,
  });
  return data;
}

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const { data } = await api.post("/auth/login", { email, password });
  return data;
}

export async function loginAnonymous(): Promise<TokenResponse> {
  const { data } = await api.post("/auth/anonymous");
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await api.get("/auth/me");
  return data;
}

// Projects
export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get("/projects/");
  return data;
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await api.get(`/projects/${id}`);
  return data;
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  const { data } = await api.post("/projects/", body);
  return data;
}

export async function updateProject(
  id: string,
  body: Partial<ProjectCreate>
): Promise<Project> {
  const { data } = await api.patch(`/projects/${id}`, body);
  return data;
}

export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/projects/${id}`);
}

export async function duplicateProject(id: string): Promise<Project> {
  const { data } = await api.post(`/projects/${id}/duplicate`);
  return data;
}

export async function exportProject(id: string): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/projects/${id}/export`);
  return data;
}

export async function importProject(bundle: Record<string, unknown>): Promise<Project> {
  const { data } = await api.post("/projects/import", bundle);
  return data;
}

export async function downloadPdfReport(simulationId: string): Promise<Blob> {
  const response = await api.get(`/simulations/${simulationId}/report/pdf`, {
    responseType: "blob",
  });
  return response.data;
}

// Components
export async function listComponents(projectId: string): Promise<Component[]> {
  const { data } = await api.get(`/projects/${projectId}/components`);
  return data;
}

export async function createComponent(
  projectId: string,
  body: { component_type: string; name: string; config: Record<string, unknown> }
): Promise<Component> {
  const { data } = await api.post(`/projects/${projectId}/components`, body);
  return data;
}

export async function updateComponent(
  projectId: string,
  componentId: string,
  body: { name?: string; config?: Record<string, unknown>; bus_id?: string | null }
): Promise<Component> {
  const { data } = await api.patch(
    `/projects/${projectId}/components/${componentId}`,
    body
  );
  return data;
}

export async function deleteComponent(
  projectId: string,
  componentId: string
): Promise<void> {
  await api.delete(`/projects/${projectId}/components/${componentId}`);
}

// Weather
export async function listWeatherDatasets(
  projectId: string
): Promise<WeatherDataset[]> {
  const { data } = await api.get(`/projects/${projectId}/weather`);
  return data;
}

export async function fetchPVGIS(
  projectId: string,
  name?: string,
  applyCorrection: boolean = true,
  injectExtremeWeather: boolean = false,
): Promise<WeatherDataset> {
  const { data } = await api.post(`/projects/${projectId}/weather/pvgis`, {
    name: name || "PVGIS TMY",
    apply_correction: applyCorrection,
    inject_extreme_weather: injectExtremeWeather,
  });
  return data;
}

export async function uploadWeather(
  projectId: string,
  file: File
): Promise<WeatherDataset> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post(
    `/projects/${projectId}/weather/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// Load Profiles
export async function listLoadProfiles(
  projectId: string
): Promise<LoadProfile[]> {
  const { data } = await api.get(`/projects/${projectId}/load-profiles`);
  return data;
}

export async function getWeatherPreview(
  projectId: string,
  datasetId: string
): Promise<{ months: string[]; ghi_avg: number[]; temp_avg: number[]; annual_ghi_kwh_m2: number }> {
  const { data } = await api.get(`/projects/${projectId}/weather/${datasetId}/preview`);
  return data;
}

export async function getLoadProfilePreview(
  projectId: string,
  profileId: string
): Promise<{ hours: number[]; avg_kw: number[]; peak_kw: number; min_kw: number; annual_kwh: number }> {
  const { data } = await api.get(`/projects/${projectId}/load-profiles/${profileId}/preview`);
  return data;
}

export async function generateLoadProfile(
  projectId: string,
  body: { scenario?: string; scenarios?: string[]; annual_kwh?: number }
): Promise<LoadProfile> {
  const { data } = await api.post(
    `/projects/${projectId}/load-profiles/generate`,
    body
  );
  return data;
}

export async function uploadLoadProfile(
  projectId: string,
  file: File
): Promise<LoadProfile> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post(
    `/projects/${projectId}/load-profiles`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// Simulations
export async function listSimulations(
  projectId: string
): Promise<Simulation[]> {
  const { data } = await api.get(`/projects/${projectId}/simulations`);
  return data;
}

export async function createSimulation(
  projectId: string,
  body: SimulationCreate
): Promise<Simulation> {
  const { data } = await api.post(`/projects/${projectId}/simulations`, body);
  return data;
}

export async function deleteSimulation(
  projectId: string,
  simulationId: string
): Promise<void> {
  await api.delete(`/projects/${projectId}/simulations/${simulationId}`);
}

export async function getSimulationStatus(
  simulationId: string
): Promise<{ id: string; status: string; progress: number; error_message: string | null }> {
  const { data } = await api.get(`/simulations/${simulationId}/status`);
  return data;
}

export async function getEconomics(
  simulationId: string
): Promise<EconomicsResult> {
  const { data } = await api.get(
    `/simulations/${simulationId}/results/economics`
  );
  return data;
}

export async function getTimeseries(
  simulationId: string
): Promise<TimeseriesResult> {
  const { data } = await api.get(
    `/simulations/${simulationId}/results/timeseries`
  );
  return data;
}

// Advisor
export async function getRecommendations(
  projectId: string,
  body: AdvisorRequest
): Promise<AdvisorResponse> {
  const { data } = await api.post(
    `/projects/${projectId}/advisor/recommend`,
    body
  );
  return data;
}

export async function evaluateSystemHealth(
  projectId: string,
  body: SystemEvaluateRequest
): Promise<SystemHealthResult> {
  const { data } = await api.post(
    `/projects/${projectId}/advisor/evaluate`,
    body
  );
  return data;
}

// Buses
export async function listBuses(projectId: string): Promise<Bus[]> {
  const { data } = await api.get(`/projects/${projectId}/buses`);
  return data;
}

export async function createBus(
  projectId: string,
  body: BusCreate
): Promise<Bus> {
  const { data } = await api.post(`/projects/${projectId}/buses`, body);
  return data;
}

export async function updateBus(
  projectId: string,
  busId: string,
  body: Partial<BusCreate>
): Promise<Bus> {
  const { data } = await api.patch(`/projects/${projectId}/buses/${busId}`, body);
  return data;
}

export async function deleteBus(
  projectId: string,
  busId: string
): Promise<void> {
  await api.delete(`/projects/${projectId}/buses/${busId}`);
}

// Branches
export async function listBranches(projectId: string): Promise<Branch[]> {
  const { data } = await api.get(`/projects/${projectId}/branches`);
  return data;
}

export async function createBranch(
  projectId: string,
  body: BranchCreate
): Promise<Branch> {
  const { data } = await api.post(`/projects/${projectId}/branches`, body);
  return data;
}

export async function updateBranch(
  projectId: string,
  branchId: string,
  body: Partial<BranchCreate>
): Promise<Branch> {
  const { data } = await api.patch(
    `/projects/${projectId}/branches/${branchId}`,
    body
  );
  return data;
}

export async function deleteBranch(
  projectId: string,
  branchId: string
): Promise<void> {
  await api.delete(`/projects/${projectId}/branches/${branchId}`);
}

// Load Allocations
export async function listLoadAllocations(
  projectId: string
): Promise<LoadAllocation[]> {
  const { data } = await api.get(`/projects/${projectId}/load-allocations`);
  return data;
}

export async function createLoadAllocation(
  projectId: string,
  body: LoadAllocationCreate
): Promise<LoadAllocation> {
  const { data } = await api.post(
    `/projects/${projectId}/load-allocations`,
    body
  );
  return data;
}

export async function deleteLoadAllocation(
  projectId: string,
  allocationId: string
): Promise<void> {
  await api.delete(`/projects/${projectId}/load-allocations/${allocationId}`);
}

// Power Flow
export async function runPowerFlow(
  projectId: string,
  body?: { mode?: string; load_profile_id?: string }
): Promise<PowerFlowResult> {
  const { data } = await api.post(
    `/projects/${projectId}/power-flow`,
    body || {}
  );
  return data;
}

// Network Results (from simulation)
export async function getNetworkResults(
  simulationId: string
): Promise<{ power_flow_summary: Record<string, unknown>; ts_bus_voltages: Record<string, number[]> }> {
  const { data } = await api.get(
    `/simulations/${simulationId}/results/network`
  );
  return data;
}

// Network Auto-Generate
export async function autoGenerateNetwork(
  projectId: string,
  body?: AutoGenerateRequest
): Promise<AutoGenerateResponse> {
  const { data } = await api.post(
    `/projects/${projectId}/network/auto-generate`,
    body || {}
  );
  return data;
}

// Cable & Transformer Libraries
export async function getCableLibrary(params?: {
  voltage_class?: string;
  material?: string;
}): Promise<CableSpec[]> {
  const { data } = await api.get("/cable-library", { params });
  return data;
}

export async function getTransformerLibrary(): Promise<TransformerSpec[]> {
  const { data } = await api.get("/transformer-library");
  return data;
}

// Sensitivity Analysis
export async function runSensitivity(
  simulationId: string,
  variables: SensitivityVariable[]
): Promise<{ task_id: string; status: string }> {
  const { data } = await api.post(
    `/simulations/${simulationId}/sensitivity`,
    { variables }
  );
  return data;
}

export async function getSensitivityResults(
  simulationId: string
): Promise<SensitivityResult> {
  const { data } = await api.get(
    `/simulations/${simulationId}/sensitivity`
  );
  return data;
}

// Contingency Analysis
export async function runContingencyAnalysis(
  projectId: string,
  gridCode?: string,
  customProfile?: Record<string, unknown>
): Promise<ContingencyAnalysisResult> {
  const { data } = await api.post(`/projects/${projectId}/contingency-analysis`, {
    grid_code: gridCode || "iec_default",
    custom_profile: customProfile,
  });
  return data;
}

export async function listGridCodes(): Promise<GridCodeSummary[]> {
  const { data } = await api.get("/grid-codes");
  return data.profiles ?? data;
}

// BESS Recommendation
export async function getBESSRecommendation(
  projectId: string,
  simulationId: string,
  opts?: { max_unmet_fraction?: number; min_re_fraction?: number; max_capacity_kwh?: number }
): Promise<BESSRecommendation> {
  const { data } = await api.get(`/projects/${projectId}/advisor/bess-recommendation`, {
    params: { simulation_id: simulationId, ...opts },
  });
  return data;
}

// Project Templates
export async function listProjectTemplates(): Promise<ProjectTemplateSummary[]> {
  const { data } = await api.get("/project-templates");
  return data;
}

export async function getProjectTemplate(templateId: string): Promise<ProjectTemplate> {
  const { data } = await api.get(`/project-templates/${templateId}`);
  return data;
}

// Component Templates
export async function listComponentTemplates(
  componentType?: string
): Promise<Record<string, ComponentTemplate[]> | ComponentTemplate[]> {
  const { data } = await api.get("/component-templates", {
    params: componentType ? { component_type: componentType } : undefined,
  });
  return data;
}

// FREF Analysis
export async function getFREFAnalysis(
  simulationId: string,
  opts?: { num_households?: number; autonomy_days?: number }
): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/simulations/${simulationId}/fref-analysis`, {
    params: opts,
  });
  return data;
}

// Financing Analysis
export async function getFinancingAnalysis(
  simulationId: string,
  params: {
    debt_fraction?: number;
    interest_rate?: number;
    loan_term?: number;
    equity_cost?: number;
    tax_rate?: number;
    om_escalation?: number;
  }
): Promise<Record<string, unknown>> {
  const { data } = await api.post(
    `/simulations/${simulationId}/results/financing`,
    params
  );
  return data;
}

// Wind Assessment
export async function getWindAssessment(
  projectId: string,
  opts?: { hub_height?: number; rated_power_kw?: number }
): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/projects/${projectId}/wind-assessment`, {
    params: opts,
  });
  return data;
}

// Comparisons
export async function compareSimulations(
  simulationIds: string[]
): Promise<{ comparisons: Record<string, unknown>[] }> {
  const { data } = await api.post("/comparisons/", {
    simulation_ids: simulationIds,
  });
  return data;
}

// Annotations
export async function listAnnotations(projectId: string): Promise<Record<string, unknown>[]> {
  const { data } = await api.get(`/projects/${projectId}/annotations`);
  return data;
}

export async function createAnnotation(
  projectId: string,
  body: { text: string; annotation_type?: string }
): Promise<Record<string, unknown>> {
  const { data } = await api.post(`/projects/${projectId}/annotations`, body);
  return data;
}

export async function updateAnnotation(
  projectId: string,
  annotationId: string,
  body: { text?: string; annotation_type?: string }
): Promise<Record<string, unknown>> {
  const { data } = await api.patch(`/projects/${projectId}/annotations/${annotationId}`, body);
  return data;
}

export async function deleteAnnotation(projectId: string, annotationId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/annotations/${annotationId}`);
}

// Scoring
export async function scoreSimulations(
  simulationIds: string[],
  weights?: Record<string, number>
): Promise<{ scored: Record<string, unknown>[] }> {
  const { data } = await api.post("/comparisons/score", {
    simulation_ids: simulationIds,
    weights: weights || null,
  });
  return data;
}

// Batch Simulation
export async function createBatch(
  projectId: string,
  body: {
    name: string;
    dispatch_strategy: string;
    weather_dataset_id: string;
    load_profile_id: string;
    sweep_params: { name: string; param_path: string; start: number; end: number; step: number }[];
  }
): Promise<Record<string, unknown>> {
  const { data } = await api.post(`/projects/${projectId}/batch`, body);
  return data;
}

export async function listBatches(projectId: string): Promise<Record<string, unknown>[]> {
  const { data } = await api.get(`/projects/${projectId}/batch`);
  return data;
}

export async function getBatchStatus(
  projectId: string,
  batchId: string
): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/projects/${projectId}/batch/${batchId}`);
  return data;
}
