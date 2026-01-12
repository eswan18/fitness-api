import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { handleOAuthCallback, refreshAccessToken } from "../client";

// Mock the config
vi.mock("../config", () => ({
  OAUTH_CONFIG: {
    clientId: "test-client-id",
    redirectUri: "http://localhost:5173/oauth/callback",
    authorizationEndpoint: "http://localhost:8080/oauth/authorize",
    tokenEndpoint: "http://localhost:8080/oauth/token",
    refreshEndpoint: "http://localhost:8080/oauth/token",
    scope: "openid profile email",
  },
}));

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

// Mock window.location
const mockLocation = {
  search: "",
  href: "",
};

describe("OAuth client", () => {
  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();
    Object.keys(mockSessionStorage).forEach((key) => {
      delete mockSessionStorage[key];
    });

    // Setup global mocks
    vi.stubGlobal("sessionStorage", sessionStorageMock);
    vi.stubGlobal("location", mockLocation);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("handleOAuthCallback", () => {
    it("throws error when OAuth returns an error", async () => {
      mockLocation.search = "?error=access_denied&error_description=User%20denied%20access";

      await expect(handleOAuthCallback()).rejects.toThrow(
        "OAuth error: access_denied - User denied access"
      );
    });

    it("throws error when no authorization code received", async () => {
      mockLocation.search = "";

      await expect(handleOAuthCallback()).rejects.toThrow(
        "No authorization code received"
      );
    });

    it("throws error when state doesn't match (CSRF protection)", async () => {
      mockLocation.search = "?code=test-code&state=wrong-state";
      mockSessionStorage["oauth_state"] = "correct-state";

      await expect(handleOAuthCallback()).rejects.toThrow(
        "Invalid state parameter"
      );
    });

    it("throws error when state is missing from URL", async () => {
      mockLocation.search = "?code=test-code";
      mockSessionStorage["oauth_state"] = "stored-state";

      await expect(handleOAuthCallback()).rejects.toThrow(
        "Invalid state parameter"
      );
    });

    it("throws error when code verifier not found", async () => {
      mockLocation.search = "?code=test-code&state=test-state";
      mockSessionStorage["oauth_state"] = "test-state";
      // oauth_code_verifier is not set

      await expect(handleOAuthCallback()).rejects.toThrow(
        "Code verifier not found"
      );
    });

    it("exchanges code for tokens successfully", async () => {
      mockLocation.search = "?code=auth-code&state=test-state";
      mockSessionStorage["oauth_state"] = "test-state";
      mockSessionStorage["oauth_code_verifier"] = "test-verifier";

      const mockTokens = {
        access_token: "access-token-123",
        refresh_token: "refresh-token-456",
        expires_in: 3600,
        token_type: "Bearer",
        scope: "openid profile email",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockTokens),
      });

      const tokens = await handleOAuthCallback();

      expect(tokens).toEqual(mockTokens);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8080/oauth/token",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })
      );

      // Should clean up PKCE params
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith(
        "oauth_code_verifier"
      );
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith("oauth_state");
    });

    it("throws error when token exchange fails", async () => {
      mockLocation.search = "?code=auth-code&state=test-state";
      mockSessionStorage["oauth_state"] = "test-state";
      mockSessionStorage["oauth_code_verifier"] = "test-verifier";

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: "Bad Request",
        json: () =>
          Promise.resolve({ error_description: "Invalid authorization code" }),
      });

      await expect(handleOAuthCallback()).rejects.toThrow(
        "Token exchange failed: Invalid authorization code"
      );
    });
  });

  describe("refreshAccessToken", () => {
    it("refreshes token successfully", async () => {
      const mockTokens = {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        expires_in: 3600,
        token_type: "Bearer",
        scope: "openid profile email",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockTokens),
      });

      const tokens = await refreshAccessToken("old-refresh-token");

      expect(tokens).toEqual(mockTokens);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8080/oauth/token",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })
      );

      // Verify the body contains correct params
      const fetchCall = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      const body = fetchCall[1].body as URLSearchParams;
      expect(body.get("grant_type")).toBe("refresh_token");
      expect(body.get("refresh_token")).toBe("old-refresh-token");
      expect(body.get("client_id")).toBe("test-client-id");
    });

    it("throws error when refresh fails", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: "Unauthorized",
      });

      await expect(refreshAccessToken("invalid-refresh-token")).rejects.toThrow(
        "Token refresh failed"
      );
    });
  });
});
