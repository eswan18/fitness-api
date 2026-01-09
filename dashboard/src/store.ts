// store.ts
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { TimePeriodType } from "@/lib/timePeriods";
import { getTimePeriodById, migrateRangePreset } from "@/lib/timePeriods";

export type Theme = "light" | "dark" | "system";

type DashboardState = {
  timeRangeStart: Date;
  setTimeRangeStart: (date: Date) => void;
  timeRangeEnd: Date;
  setTimeRangeEnd: (date: Date) => void;
  selectedTimePeriod: TimePeriodType;
  setSelectedTimePeriod: (period: TimePeriodType) => void;
  selectTimePeriod: (period: TimePeriodType) => void;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  maxHr: number;
  setMaxHr: (maxHr: number) => void;
  restingHr: number;
  setRestingHr: (restingHr: number) => void;
  sex: "M" | "F";
  setSex: (sex: "M" | "F") => void;

  // OAuth state (stored in sessionStorage, NOT localStorage)
  accessToken: string | null;
  refreshToken: string | null;
  tokenExpiresAt: number | null;
  isAuthenticated: boolean;
  setTokens: (
    accessToken: string,
    refreshToken: string,
    expiresIn: number
  ) => void;
  clearTokens: () => void;
};

// Defaults if nothing persisted
const defaultPeriod: TimePeriodType = "30_days";
const defaultOption = getTimePeriodById(defaultPeriod)!;

// Default HR settings matching existing hardcoded values
const DEFAULT_MAX_HR = 192;
const DEFAULT_RESTING_HR = 42;
const DEFAULT_SEX = "M" as const;

// Theme utilities
const getSystemTheme = (): "light" | "dark" => {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

const applyTheme = (theme: Theme) => {
  const root = document.documentElement;
  const effectiveTheme = theme === "system" ? getSystemTheme() : theme;

  if (effectiveTheme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
};

// Listen for system theme changes
let systemThemeCleanup: (() => void) | null = null;

const setupSystemThemeListener = (callback: () => void) => {
  // Clean up previous listener
  if (systemThemeCleanup) {
    systemThemeCleanup();
  }

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  mediaQuery.addEventListener("change", callback);
  systemThemeCleanup = () => mediaQuery.removeEventListener("change", callback);
  return systemThemeCleanup;
};

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      timeRangeStart: defaultOption.start!,
      setTimeRangeStart: (date) => set({ timeRangeStart: date }),

      timeRangeEnd: defaultOption.end!,
      setTimeRangeEnd: (date) => set({ timeRangeEnd: date }),

      selectedTimePeriod: defaultPeriod,
      setSelectedTimePeriod: (period) => set({ selectedTimePeriod: period }),

      selectTimePeriod: (period) => {
        const option = getTimePeriodById(period);
        if (!option) return;

        set({
          selectedTimePeriod: period,
          ...(option.start &&
            option.end && {
              timeRangeStart: option.start,
              timeRangeEnd: option.end,
            }),
        });
      },

      theme: "system",
      setTheme: (theme) => {
        applyTheme(theme);

        // Set up or clean up system listener
        if (theme === "system") {
          setupSystemThemeListener(() => {
            applyTheme("system");
          });
        } else if (systemThemeCleanup) {
          systemThemeCleanup();
          systemThemeCleanup = null;
        }

        set({ theme });
      },

      maxHr: DEFAULT_MAX_HR,
      setMaxHr: (maxHr) => set({ maxHr }),

      restingHr: DEFAULT_RESTING_HR,
      setRestingHr: (restingHr) => set({ restingHr }),

      sex: DEFAULT_SEX,
      setSex: (sex) => set({ sex }),

      // OAuth state (initialized as not authenticated, NOT persisted in localStorage)
      accessToken: null,
      refreshToken: null,
      tokenExpiresAt: null,
      isAuthenticated: false,

      setTokens: (accessToken, refreshToken, expiresIn) => {
        const expiresAt = Date.now() + expiresIn * 1000;
        set({
          accessToken,
          refreshToken,
          tokenExpiresAt: expiresAt,
          isAuthenticated: true,
        });

        // Persist to sessionStorage
        sessionStorage.setItem("oauth_access_token", accessToken);
        sessionStorage.setItem("oauth_refresh_token", refreshToken);
        sessionStorage.setItem("oauth_expires_at", expiresAt.toString());
      },

      clearTokens: () => {
        set({
          accessToken: null,
          refreshToken: null,
          tokenExpiresAt: null,
          isAuthenticated: false,
        });
        sessionStorage.removeItem("oauth_access_token");
        sessionStorage.removeItem("oauth_refresh_token");
        sessionStorage.removeItem("oauth_expires_at");
      },
    }),
    {
      name: "dashboard-store",
      version: 5,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        selectedTimePeriod: state.selectedTimePeriod,
        timeRangeStart:
          state.timeRangeStart instanceof Date
            ? state.timeRangeStart.toISOString()
            : state.timeRangeStart,
        timeRangeEnd:
          state.timeRangeEnd instanceof Date
            ? state.timeRangeEnd.toISOString()
            : state.timeRangeEnd,
        theme: state.theme,
        maxHr: state.maxHr,
        restingHr: state.restingHr,
        sex: state.sex,
      }),
      migrate: (persisted) => {
        const ps = persisted as unknown as {
          state?: {
            selectedRangePreset?: string;
            selectedTimePeriod?: TimePeriodType;
          };
        } | null;
        if (ps?.state?.selectedRangePreset && !ps.state.selectedTimePeriod) {
          ps.state.selectedTimePeriod = migrateRangePreset(
            ps.state.selectedRangePreset,
          );
          delete ps.state.selectedRangePreset;
        }
        return persisted;
      },
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        const s = state as unknown as {
          timeRangeStart: unknown;
          timeRangeEnd: unknown;
          selectedTimePeriod: TimePeriodType;
          theme?: Theme;
        };
        if (typeof s.timeRangeStart === "string") {
          const d = new Date(s.timeRangeStart);
          if (!isNaN(d.getTime())) (state as DashboardState).timeRangeStart = d;
        }
        if (typeof s.timeRangeEnd === "string") {
          const d = new Date(s.timeRangeEnd);
          if (!isNaN(d.getTime())) (state as DashboardState).timeRangeEnd = d;
        }
        const option = getTimePeriodById(s.selectedTimePeriod);
        if (option?.start && option?.end) {
          (state as DashboardState).timeRangeStart = option.start;
          (state as DashboardState).timeRangeEnd = option.end;
        }

        // Apply theme on hydration
        const theme = s.theme || "system";
        applyTheme(theme);
        (state as DashboardState).theme = theme;

        // Set up system theme listener if theme is system
        if (theme === "system") {
          setupSystemThemeListener(() => {
            applyTheme("system");
          });
        }

        // Restore OAuth tokens from sessionStorage on page load
        const accessToken = sessionStorage.getItem("oauth_access_token");
        const refreshToken = sessionStorage.getItem("oauth_refresh_token");
        const expiresAt = sessionStorage.getItem("oauth_expires_at");

        if (accessToken && refreshToken && expiresAt) {
          (state as DashboardState).accessToken = accessToken;
          (state as DashboardState).refreshToken = refreshToken;
          (state as DashboardState).tokenExpiresAt = parseInt(expiresAt);
          (state as DashboardState).isAuthenticated = true;
        }
      },
    },
  ),
);
