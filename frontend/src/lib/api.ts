import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import type {
  Component,
  EconomicsResult,
  LoadProfile,
  Project,
  ProjectCreate,
  Simulation,
  SimulationCreate,
  TimeseriesResult,
  TokenResponse,
  User,
  WeatherDataset,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  body: { name?: string; config?: Record<string, unknown> }
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
  name?: string
): Promise<WeatherDataset> {
  const { data } = await api.post(`/projects/${projectId}/weather/pvgis`, {
    name: name || "PVGIS TMY",
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

export async function generateLoadProfile(
  projectId: string,
  body: { scenario: string; annual_kwh?: number }
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

// Comparisons
export async function compareSimulations(
  simulationIds: string[]
): Promise<{ comparisons: Record<string, unknown>[] }> {
  const { data } = await api.post("/comparisons/", {
    simulation_ids: simulationIds,
  });
  return data;
}
