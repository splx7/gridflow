import { create } from "zustand";
import type {
  Component,
  LoadProfile,
  Project,
  ProjectCreate,
  Simulation,
  SimulationCreate,
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
  isLoading: boolean;

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
    body: { name?: string; config?: Record<string, unknown> }
  ) => Promise<Component>;

  // Weather
  fetchWeather: (projectId: string) => Promise<void>;
  fetchPVGIS: (projectId: string) => Promise<WeatherDataset>;

  // Load
  fetchLoadProfiles: (projectId: string) => Promise<void>;
  generateLoadProfile: (
    projectId: string,
    body: { scenario: string; annual_kwh?: number }
  ) => Promise<LoadProfile>;

  // Simulations
  fetchSimulations: (projectId: string) => Promise<void>;
  createSimulation: (
    projectId: string,
    body: SimulationCreate
  ) => Promise<Simulation>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  components: [],
  weatherDatasets: [],
  loadProfiles: [],
  simulations: [],
  isLoading: false,

  fetchProjects: async () => {
    set({ isLoading: true });
    const projects = await api.listProjects();
    set({ projects, isLoading: false });
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
}));
