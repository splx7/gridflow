import { create } from "zustand";
import type { User } from "@/types";
import { getMe, login as apiLogin, register as apiRegister } from "@/lib/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  login: async (email, password) => {
    const tokens = await apiLogin(email, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const user = await getMe();
    set({ user, isAuthenticated: true });
  },

  register: async (email, password, fullName) => {
    const tokens = await apiRegister(email, password, fullName);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const user = await getMe();
    set({ user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        set({ isLoading: false, isAuthenticated: false });
        return;
      }
      const user = await getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
