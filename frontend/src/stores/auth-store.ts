import { create } from "zustand";

import { OpenAPI } from "@/api/generated";
import type { UserResponse } from "@/api/generated";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  currentUser: UserResponse | null;
  hydrated: boolean;
  setTokens: (payload: { accessToken: string; refreshToken: string }) => void;
  setCurrentUser: (user: UserResponse | null) => void;
  logout: () => void;
  markHydrated: () => void;
  initialize: () => void;
};

const STORAGE_KEY = "dmgr-auth";

function writeStorage(state: Pick<AuthState, "accessToken" | "refreshToken" | "currentUser">) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clearStorage() {
  localStorage.removeItem(STORAGE_KEY);
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  currentUser: null,
  hydrated: false,
  setTokens: ({ accessToken, refreshToken }) => {
    OpenAPI.TOKEN = accessToken;
    set((state) => {
      const next = { ...state, accessToken, refreshToken };
      writeStorage(next);
      return next;
    });
  },
  setCurrentUser: (currentUser) =>
    set((state) => {
      const next = { ...state, currentUser };
      writeStorage(next);
      return next;
    }),
  logout: () => {
    OpenAPI.TOKEN = undefined;
    clearStorage();
    set({ accessToken: null, refreshToken: null, currentUser: null });
  },
  markHydrated: () => set({ hydrated: true }),
  initialize: () => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      get().markHydrated();
      return;
    }

    try {
      const parsed = JSON.parse(raw) as {
        accessToken?: string | null;
        refreshToken?: string | null;
        currentUser?: UserResponse | null;
      };
      OpenAPI.TOKEN = parsed.accessToken ?? undefined;
      set({
        accessToken: parsed.accessToken ?? null,
        refreshToken: parsed.refreshToken ?? null,
        currentUser: parsed.currentUser ?? null,
        hydrated: true,
      });
    } catch {
      clearStorage();
      set({ accessToken: null, refreshToken: null, currentUser: null, hydrated: true });
    }
  },
}));
