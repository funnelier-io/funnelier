"use client";

import { create } from "zustand";
import { api, setTokens, clearTokens, getToken } from "@/lib/api-client";
import type { UserResponse, TokenResponse } from "@/types/auth";

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (username: string, password: string) => {
    const res = await api<TokenResponse>("POST", "/auth/login", {
      username,
      password,
    });

    if (res.ok) {
      setTokens(res.data.access_token, res.data.refresh_token);
      set({
        user: res.data.user,
        isAuthenticated: true,
        isLoading: false,
      });
      return true;
    }
    return false;
  },

  logout: () => {
    clearTokens();
    set({ user: null, isAuthenticated: false, isLoading: false });
  },

  checkAuth: async () => {
    const token = getToken();
    if (!token) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    const res = await api<UserResponse>("GET", "/auth/me");
    if (res.ok) {
      set({ user: res.data, isAuthenticated: true, isLoading: false });
    } else {
      clearTokens();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));

