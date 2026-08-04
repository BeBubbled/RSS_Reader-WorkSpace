import { create } from "zustand";

import type { CurrentUser } from "../api/client";

type AuthState = {
  user: CurrentUser | null;
  isLoading: boolean;
  setUser: (user: CurrentUser | null) => void;
  setLoading: (isLoading: boolean) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  setUser: (user) => set({ user }),
  setLoading: (isLoading) => set({ isLoading })
}));
