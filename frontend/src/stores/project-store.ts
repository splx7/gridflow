import { create } from "zustand";
import type {
  AdvisorRequest,
  AdvisorResponse,
  AdvisorRecommendation,
  AutoGenerateRequest,
  AutoGenerateResponse,
  Branch,
  BranchCreate,
  Bus,
  BusCreate,
  Component,
  LoadAllocation,
  LoadAllocationCreate,
  LoadProfile,
  NetworkRecommendation,
  PowerFlowResult,
  Project,
  ProjectCreate,
  Simulation,
  SimulationCreate,
  SystemEvaluateRequest,
  SystemHealthResult,
  WeatherDataset,
} from "@/types";
import * as api from "@/lib/api";

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  components: Component[];
  weatherDatasets: WeatherDataset[];
  loadProfiles: LoadProfile[];
  simulations: Simulation[];
  advisorResult: AdvisorResponse | null;
  appliedRecommendation: AdvisorRecommendation | null;
  systemHealth: SystemHealthResult | null;
  healthLoading: boolean;
  isLoading: boolean;

  // Network state
  buses: Bus[];
  branches: Branch[];
  loadAllocations: LoadAllocation[];
  powerFlowResult: PowerFlowResult | null;
  powerFlowLoading: boolean;
  networkRecommendations: NetworkRecommendation[];
  autoGenerateLoading: boolean;

  // Projects
  fetchProjects: () => Promise<void>;
  setCurrentProject: (project: Project | null) => void;
  createProject: (body: ProjectCreate) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;

  updateProject: (
    id: string,
    body: Partial<ProjectCreate>
  ) => Promise<Project>;

  // Components
  fetchComponents: (projectId: string) => Promise<void>;
  addComponent: (
    projectId: string,
    body: { component_type: string; name: string; config: Record<string, unknown> }
  ) => Promise<Component>;
  removeComponent: (projectId: string, componentId: string) => Promise<void>;
  updateComponent: (
    projectId: string,
    componentId: string,
    body: { name?: string; config?: Record<string, unknown>; bus_id?: string | null }
  ) => Promise<Component>;

  // Weather
  fetchWeather: (projectId: string) => Promise<void>;
  fetchPVGIS: (projectId: string) => Promise<WeatherDataset>;

  // Load
  fetchLoadProfiles: (projectId: string) => Promise<void>;
  generateLoadProfile: (
    projectId: string,
    body: { scenario?: string; scenarios?: string[]; annual_kwh?: number }
  ) => Promise<LoadProfile>;

  // Simulations
  fetchSimulations: (projectId: string) => Promise<void>;
  createSimulation: (
    projectId: string,
    body: SimulationCreate
  ) => Promise<Simulation>;
  removeSimulation: (projectId: string, simulationId: string) => Promise<void>;

  // Advisor
  fetchRecommendations: (
    projectId: string,
    body: AdvisorRequest
  ) => Promise<AdvisorResponse>;
  clearRecommendations: () => void;

  // System Health
  setAppliedRecommendation: (rec: AdvisorRecommendation | null) => void;
  evaluateHealth: (
    projectId: string,
    body: SystemEvaluateRequest
  ) => Promise<SystemHealthResult>;
  clearHealth: () => void;

  // Network
  fetchBuses: (projectId: string) => Promise<void>;
  addBus: (projectId: string, body: BusCreate) => Promise<Bus>;
  updateBus: (projectId: string, busId: string, body: Partial<BusCreate>) => Promise<Bus>;
  removeBus: (projectId: string, busId: string) => Promise<void>;
  fetchBranches: (projectId: string) => Promise<void>;
  addBranch: (projectId: string, body: BranchCreate) => Promise<Branch>;
  updateBranch: (projectId: string, branchId: string, body: Partial<BranchCreate>) => Promise<Branch>;
  removeBranch: (projectId: string, branchId: string) => Promise<void>;
  fetchLoadAllocations: (projectId: string) => Promise<void>;
  addLoadAllocation: (projectId: string, body: LoadAllocationCreate) => Promise<LoadAllocation>;
  removeLoadAllocation: (projectId: string, allocationId: string) => Promise<void>;
  runPowerFlow: (projectId: string) => Promise<PowerFlowResult>;
  clearPowerFlow: () => void;
  autoGenerateNetwork: (projectId: string, body?: AutoGenerateRequest) => Promise<AutoGenerateResponse>;
  clearNetworkRecommendations: () => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  components: [],
  weatherDatasets: [],
  loadProfiles: [],
  simulations: [],
  advisorResult: null,
  appliedRecommendation: null,
  systemHealth: null,
  healthLoading: false,
  isLoading: false,
  buses: [],
  branches: [],
  loadAllocations: [],
  powerFlowResult: null,
  powerFlowLoading: false,
  networkRecommendations: [],
  autoGenerateLoading: false,

  fetchProjects: async () => {
    set({ isLoading: true });
    try {
      const projects = await api.listProjects();
      set({ projects, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  setCurrentProject: (project) => set({ currentProject: project }),

  createProject: async (body) => {
    const project = await api.createProject(body);
    set((s) => ({ projects: [project, ...s.projects] }));
    return project;
  },

  deleteProject: async (id) => {
    await api.deleteProject(id);
    set((s) => ({
      projects: s.projects.filter((p) => p.id !== id),
      currentProject: s.currentProject?.id === id ? null : s.currentProject,
    }));
  },

  updateProject: async (id, body) => {
    const updated = await api.updateProject(id, body);
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? updated : p)),
      currentProject: s.currentProject?.id === id ? updated : s.currentProject,
    }));
    return updated;
  },

  fetchComponents: async (projectId) => {
    const components = await api.listComponents(projectId);
    set({ components });
  },

  addComponent: async (projectId, body) => {
    const component = await api.createComponent(projectId, body);
    set((s) => ({ components: [...s.components, component] }));
    return component;
  },

  removeComponent: async (projectId, componentId) => {
    await api.deleteComponent(projectId, componentId);
    set((s) => ({
      components: s.components.filter((c) => c.id !== componentId),
    }));
  },

  updateComponent: async (projectId, componentId, body) => {
    const updated = await api.updateComponent(projectId, componentId, body);
    set((s) => ({
      components: s.components.map((c) => (c.id === componentId ? updated : c)),
    }));
    return updated;
  },

  fetchWeather: async (projectId) => {
    const weatherDatasets = await api.listWeatherDatasets(projectId);
    set({ weatherDatasets });
  },

  fetchPVGIS: async (projectId) => {
    const dataset = await api.fetchPVGIS(projectId);
    set((s) => ({ weatherDatasets: [...s.weatherDatasets, dataset] }));
    return dataset;
  },

  fetchLoadProfiles: async (projectId) => {
    const loadProfiles = await api.listLoadProfiles(projectId);
    set({ loadProfiles });
  },

  generateLoadProfile: async (projectId, body) => {
    const profile = await api.generateLoadProfile(projectId, body);
    set((s) => ({ loadProfiles: [...s.loadProfiles, profile] }));
    return profile;
  },

  fetchSimulations: async (projectId) => {
    const simulations = await api.listSimulations(projectId);
    set({ simulations });
  },

  createSimulation: async (projectId, body) => {
    const sim = await api.createSimulation(projectId, body);
    set((s) => ({ simulations: [sim, ...s.simulations] }));
    return sim;
  },

  removeSimulation: async (projectId, simulationId) => {
    await api.deleteSimulation(projectId, simulationId);
    set((s) => ({
      simulations: s.simulations.filter((sim) => sim.id !== simulationId),
    }));
  },

  fetchRecommendations: async (projectId, body) => {
    const result = await api.getRecommendations(projectId, body);
    set({ advisorResult: result });
    return result;
  },

  clearRecommendations: () => set({ advisorResult: null }),

  setAppliedRecommendation: (rec) => set({ appliedRecommendation: rec }),

  evaluateHealth: async (projectId, body) => {
    set({ healthLoading: true });
    try {
      const result = await api.evaluateSystemHealth(projectId, body);
      set({ systemHealth: result, healthLoading: false });
      return result;
    } catch {
      set({ healthLoading: false });
      throw new Error("Health evaluation failed");
    }
  },

  clearHealth: () => set({ systemHealth: null, appliedRecommendation: null }),

  // Network actions
  fetchBuses: async (projectId) => {
    const buses = await api.listBuses(projectId);
    set({ buses });
  },

  addBus: async (projectId, body) => {
    const bus = await api.createBus(projectId, body);
    set((s) => ({ buses: [...s.buses, bus] }));
    return bus;
  },

  updateBus: async (projectId, busId, body) => {
    const updated = await api.updateBus(projectId, busId, body);
    set((s) => ({
      buses: s.buses.map((b) => (b.id === busId ? updated : b)),
    }));
    return updated;
  },

  removeBus: async (projectId, busId) => {
    await api.deleteBus(projectId, busId);
    set((s) => ({
      buses: s.buses.filter((b) => b.id !== busId),
      branches: s.branches.filter(
        (br) => br.from_bus_id !== busId && br.to_bus_id !== busId
      ),
    }));
  },

  fetchBranches: async (projectId) => {
    const branches = await api.listBranches(projectId);
    set({ branches });
  },

  addBranch: async (projectId, body) => {
    const branch = await api.createBranch(projectId, body);
    set((s) => ({ branches: [...s.branches, branch] }));
    return branch;
  },

  updateBranch: async (projectId, branchId, body) => {
    const updated = await api.updateBranch(projectId, branchId, body);
    set((s) => ({
      branches: s.branches.map((br) => (br.id === branchId ? updated : br)),
    }));
    return updated;
  },

  removeBranch: async (projectId, branchId) => {
    await api.deleteBranch(projectId, branchId);
    set((s) => ({
      branches: s.branches.filter((br) => br.id !== branchId),
    }));
  },

  fetchLoadAllocations: async (projectId) => {
    const loadAllocations = await api.listLoadAllocations(projectId);
    set({ loadAllocations });
  },

  addLoadAllocation: async (projectId, body) => {
    const allocation = await api.createLoadAllocation(projectId, body);
    set((s) => ({ loadAllocations: [...s.loadAllocations, allocation] }));
    return allocation;
  },

  removeLoadAllocation: async (projectId, allocationId) => {
    await api.deleteLoadAllocation(projectId, allocationId);
    set((s) => ({
      loadAllocations: s.loadAllocations.filter((a) => a.id !== allocationId),
    }));
  },

  runPowerFlow: async (projectId) => {
    set({ powerFlowLoading: true });
    try {
      const result = await api.runPowerFlow(projectId);
      set({ powerFlowResult: result, powerFlowLoading: false });
      return result;
    } catch {
      set({ powerFlowLoading: false });
      throw new Error("Power flow analysis failed");
    }
  },

  clearPowerFlow: () => set({ powerFlowResult: null }),

  autoGenerateNetwork: async (projectId, body) => {
    set({ autoGenerateLoading: true });
    try {
      const result = await api.autoGenerateNetwork(projectId, body);
      set({
        buses: result.buses,
        branches: result.branches,
        loadAllocations: result.load_allocations,
        networkRecommendations: result.recommendations,
        autoGenerateLoading: false,
      });
      // Refresh project (network_mode changed) and components (bus_id updated)
      const [project, components] = await Promise.all([
        api.getProject(projectId),
        api.listComponents(projectId),
      ]);
      set((s) => ({
        currentProject: project,
        projects: s.projects.map((p) => (p.id === projectId ? project : p)),
        components,
      }));
      return result;
    } catch {
      set({ autoGenerateLoading: false });
      throw new Error("Auto-generate network failed");
    }
  },

  clearNetworkRecommendations: () => set({ networkRecommendations: [] }),
}));
