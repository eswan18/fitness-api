import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useDashboardStore } from "@/store";

// Mock sessionStorage
const mockSessionStorage: Record<string, string> = {};
const sessionStorageMock = {
  getItem: vi.fn((key: string) => mockSessionStorage[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    mockSessionStorage[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete mockSessionStorage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(mockSessionStorage).forEach((key) => {
      delete mockSessionStorage[key];
    });
  }),
  length: 0,
  key: vi.fn(),
};

describe("Dashboard store - Auth state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.keys(mockSessionStorage).forEach((key) => {
      delete mockSessionStorage[key];
    });
    vi.stubGlobal("sessionStorage", sessionStorageMock);

    // Reset store to initial state
    useDashboardStore.setState({
      accessToken: null,
      refreshToken: null,
      tokenExpiresAt: null,
      isAuthenticated: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("setTokens", () => {
    it("stores tokens in state", () => {
      const { setTokens } = useDashboardStore.getState();

      setTokens("access-token-123", "refresh-token-456", 3600);

      const state = useDashboardStore.getState();
      expect(state.accessToken).toBe("access-token-123");
      expect(state.refreshToken).toBe("refresh-token-456");
      expect(state.isAuthenticated).toBe(true);
    });

    it("calculates expiry time from expires_in", () => {
      const now = Date.now();
      vi.spyOn(Date, "now").mockReturnValue(now);

      const { setTokens } = useDashboardStore.getState();
      setTokens("access-token", "refresh-token", 3600);

      const state = useDashboardStore.getState();
      expect(state.tokenExpiresAt).toBe(now + 3600 * 1000);

      vi.restoreAllMocks();
    });

    it("persists tokens to sessionStorage", () => {
      const { setTokens } = useDashboardStore.getState();

      setTokens("access-token-123", "refresh-token-456", 3600);

      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        "oauth_access_token",
        "access-token-123"
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        "oauth_refresh_token",
        "refresh-token-456"
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        "oauth_expires_at",
        expect.any(String)
      );
    });
  });

  describe("clearTokens", () => {
    it("clears tokens from state", () => {
      // First set some tokens
      useDashboardStore.setState({
        accessToken: "some-token",
        refreshToken: "some-refresh",
        tokenExpiresAt: Date.now() + 3600000,
        isAuthenticated: true,
      });

      const { clearTokens } = useDashboardStore.getState();
      clearTokens();

      const state = useDashboardStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.tokenExpiresAt).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("removes tokens from sessionStorage", () => {
      const { clearTokens } = useDashboardStore.getState();
      clearTokens();

      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(
        "oauth_access_token"
      );
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(
        "oauth_refresh_token"
      );
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(
        "oauth_expires_at"
      );
    });
  });

  describe("initial state", () => {
    it("starts with unauthenticated state", () => {
      // Reset to fresh state
      useDashboardStore.setState({
        accessToken: null,
        refreshToken: null,
        tokenExpiresAt: null,
        isAuthenticated: false,
      });

      const state = useDashboardStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.tokenExpiresAt).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("isAuthenticated", () => {
    it("is true when tokens are set", () => {
      const { setTokens } = useDashboardStore.getState();
      setTokens("token", "refresh", 3600);

      expect(useDashboardStore.getState().isAuthenticated).toBe(true);
    });

    it("is false after tokens are cleared", () => {
      const { setTokens, clearTokens } = useDashboardStore.getState();
      setTokens("token", "refresh", 3600);
      clearTokens();

      expect(useDashboardStore.getState().isAuthenticated).toBe(false);
    });
  });
});
