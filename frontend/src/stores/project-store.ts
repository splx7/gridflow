import { create } from "zustand";
import type {
  Component,
  LoadProfile,
  Project,
  ProjectCreate,
  Simulation,
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

  // Components
  fetchComponents: (projectId: string) => Promise<void>;
  addComponent: (
    projectId: string,
    body: { component_type: string; name: string; config: Record<string, unknown> }
  ) => Promise<Component>;
  removeComponent: (projectId: string, componentId: string) => Promise<void>;

  // Weather
  fetchWeather: (projectId: string) => Promise<void>;
  fetchPVGIS: (projectId: string) => Promise<WeatherDataset>;

  // Load
  fetchLoadProfiles: (projectId: string) => Promise<void>;

  // Simulations
  fetchSimulations: (projectId: string) => Promise<void>;
  createSimulation: (
    projectId: string,
    body: { name: string; dispatch_strategy: string; weather_dataset_id: string; load_profile_id: string }
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
