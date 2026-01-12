import { describe, it, expect, vi, beforeEach } from "vitest";
import { isTokenExpired, ensureValidToken, withTokenRefresh } from "../refresh";
import { useDashboardStore } from "@/store";

// Mock the client module
vi.mock("../client", () => ({
  refreshAccessToken: vi.fn(),
}));

import { refreshAccessToken } from "../client";

describe("Token refresh utilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the store to initial state
    useDashboardStore.setState({
      accessToken: null,
      refreshToken: null,
      tokenExpiresAt: null,
      isAuthenticated: false,
    });
  });

  describe("isTokenExpired", () => {
    it("returns true when tokenExpiresAt is null", () => {
      useDashboardStore.setState({ tokenExpiresAt: null });
      expect(isTokenExpired()).toBe(true);
    });

    it("returns true when token is expired", () => {
      // Token expired 1 hour ago
      const expiredTime = Date.now() - 60 * 60 * 1000;
      useDashboardStore.setState({ tokenExpiresAt: expiredTime });
      expect(isTokenExpired()).toBe(true);
    });

    it("returns true when token expires within 5 minutes", () => {
      // Token expires in 4 minutes
      const almostExpired = Date.now() + 4 * 60 * 1000;
      useDashboardStore.setState({ tokenExpiresAt: almostExpired });
      expect(isTokenExpired()).toBe(true);
    });

    it("returns false when token is valid and not about to expire", () => {
      // Token expires in 1 hour
      const validExpiry = Date.now() + 60 * 60 * 1000;
      useDashboardStore.setState({ tokenExpiresAt: validExpiry });
      expect(isTokenExpired()).toBe(false);
    });

    it("returns false when token expires in exactly 5 minutes", () => {
      // Token expires in 5 minutes + 1 second (just outside the buffer)
      const borderlineExpiry = Date.now() + 5 * 60 * 1000 + 1000;
      useDashboardStore.setState({ tokenExpiresAt: borderlineExpiry });
      expect(isTokenExpired()).toBe(false);
    });
  });

  describe("ensureValidToken", () => {
    it("returns true immediately if token is not expired", async () => {
      const validExpiry = Date.now() + 60 * 60 * 1000;
      useDashboardStore.setState({
        accessToken: "valid-token",
        refreshToken: "refresh-token",
        tokenExpiresAt: validExpiry,
        isAuthenticated: true,
      });

      const result = await ensureValidToken();

      expect(result).toBe(true);
      expect(refreshAccessToken).not.toHaveBeenCalled();
    });

    it("returns false and clears tokens when no refresh token available", async () => {
      useDashboardStore.setState({
        accessToken: "expired-token",
        refreshToken: null,
        tokenExpiresAt: Date.now() - 1000, // Expired
        isAuthenticated: true,
      });

      const result = await ensureValidToken();

      expect(result).toBe(false);
      expect(useDashboardStore.getState().isAuthenticated).toBe(false);
      expect(useDashboardStore.getState().accessToken).toBeNull();
    });

    it("refreshes token when expired and returns true on success", async () => {
      useDashboardStore.setState({
        accessToken: "expired-token",
        refreshToken: "valid-refresh-token",
        tokenExpiresAt: Date.now() - 1000, // Expired
        isAuthenticated: true,
      });

      const newTokens = {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        expires_in: 3600,
        token_type: "Bearer",
        scope: "openid",
      };

      vi.mocked(refreshAccessToken).mockResolvedValue(newTokens);

      const result = await ensureValidToken();

      expect(result).toBe(true);
      expect(refreshAccessToken).toHaveBeenCalledWith("valid-refresh-token");
      expect(useDashboardStore.getState().accessToken).toBe("new-access-token");
      expect(useDashboardStore.getState().isAuthenticated).toBe(true);
    });

    it("returns false and clears tokens when refresh fails", async () => {
      useDashboardStore.setState({
        accessToken: "expired-token",
        refreshToken: "invalid-refresh-token",
        tokenExpiresAt: Date.now() - 1000, // Expired
        isAuthenticated: true,
      });

      vi.mocked(refreshAccessToken).mockRejectedValue(
        new Error("Refresh failed")
      );

      const result = await ensureValidToken();

      expect(result).toBe(false);
      expect(useDashboardStore.getState().isAuthenticated).toBe(false);
      expect(useDashboardStore.getState().accessToken).toBeNull();
    });
  });

  describe("withTokenRefresh", () => {
    it("executes function when token is valid", async () => {
      const validExpiry = Date.now() + 60 * 60 * 1000;
      useDashboardStore.setState({
        accessToken: "valid-token",
        refreshToken: "refresh-token",
        tokenExpiresAt: validExpiry,
        isAuthenticated: true,
      });

      const mockFn = vi.fn().mockResolvedValue("result");

      const result = await withTokenRefresh(mockFn);

      expect(result).toBe("result");
      expect(mockFn).toHaveBeenCalled();
    });

    it("throws error when token refresh fails", async () => {
      useDashboardStore.setState({
        accessToken: null,
        refreshToken: null,
        tokenExpiresAt: null,
        isAuthenticated: false,
      });

      const mockFn = vi.fn();

      await expect(withTokenRefresh(mockFn)).rejects.toThrow(
        "Authentication required. Please log in again."
      );
      expect(mockFn).not.toHaveBeenCalled();
    });

    it("refreshes token before executing function if expired", async () => {
      useDashboardStore.setState({
        accessToken: "expired-token",
        refreshToken: "valid-refresh-token",
        tokenExpiresAt: Date.now() - 1000, // Expired
        isAuthenticated: true,
      });

      const newTokens = {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        expires_in: 3600,
        token_type: "Bearer",
        scope: "openid",
      };

      vi.mocked(refreshAccessToken).mockResolvedValue(newTokens);

      const mockFn = vi.fn().mockResolvedValue("success");

      const result = await withTokenRefresh(mockFn);

      expect(refreshAccessToken).toHaveBeenCalled();
      expect(result).toBe("success");
      expect(mockFn).toHaveBeenCalled();
    });
  });
});
