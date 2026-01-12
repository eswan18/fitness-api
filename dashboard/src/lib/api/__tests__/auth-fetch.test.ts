import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useDashboardStore } from "@/store";

// We need to test getAuthHeaders which is not exported, so we'll test it
// through the fetch functions that use it

// Mock the OAuth refresh module
vi.mock("@/lib/oauth/refresh", () => ({
  ensureValidToken: vi.fn(),
}));

import { ensureValidToken } from "@/lib/oauth/refresh";

// Import a function that uses getAuthHeaders
import { fetchShoeMileage } from "../fetch";

describe("Authenticated fetch utilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Reset store
    useDashboardStore.setState({
      accessToken: "test-access-token",
      refreshToken: "test-refresh-token",
      tokenExpiresAt: Date.now() + 3600000,
      isAuthenticated: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("getAuthHeaders (tested through fetch functions)", () => {
    it("adds Authorization header with Bearer token", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchShoeMileage();

      expect(fetch).toHaveBeenCalledWith(
        expect.any(URL),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer test-access-token",
          }),
        })
      );
    });

    it("throws error when token validation fails", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(false);

      await expect(fetchShoeMileage()).rejects.toThrow(
        "Authentication required. Please log in again."
      );

      expect(fetch).not.toHaveBeenCalled();
    });

    it("refreshes token before making request if needed", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchShoeMileage();

      expect(ensureValidToken).toHaveBeenCalled();
      expect(fetch).toHaveBeenCalled();
    });
  });

  describe("fetch error handling", () => {
    it("throws error on non-ok response", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      });

      await expect(fetchShoeMileage()).rejects.toThrow(
        "Failed to fetch shoe mileage"
      );
    });

    it("handles 401 response", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
      });

      await expect(fetchShoeMileage()).rejects.toThrow();
    });
  });

  describe("multiple authenticated requests", () => {
    it("uses current token for each request", async () => {
      vi.mocked(ensureValidToken).mockResolvedValue(true);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      // First request with initial token
      await fetchShoeMileage();
      expect(fetch).toHaveBeenLastCalledWith(
        expect.any(URL),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer test-access-token",
          }),
        })
      );

      // Update token
      useDashboardStore.setState({
        accessToken: "new-access-token",
      });

      // Second request should use new token
      await fetchShoeMileage();
      expect(fetch).toHaveBeenLastCalledWith(
        expect.any(URL),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer new-access-token",
          }),
        })
      );
    });
  });
});
