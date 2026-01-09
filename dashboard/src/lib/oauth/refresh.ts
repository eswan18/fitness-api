import { useDashboardStore } from "@/store";
import { refreshAccessToken } from "./client";

/**
 * Check if access token is expired or about to expire (within 5 minutes)
 */
export function isTokenExpired(): boolean {
  const { tokenExpiresAt } = useDashboardStore.getState();
  if (!tokenExpiresAt) return true;

  const fiveMinutes = 5 * 60 * 1000;
  return Date.now() >= tokenExpiresAt - fiveMinutes;
}

/**
 * Refresh access token if needed
 * Returns true if token is valid, false if refresh failed
 */
export async function ensureValidToken(): Promise<boolean> {
  const { refreshToken, setTokens, clearTokens } = useDashboardStore.getState();

  if (!isTokenExpired()) {
    return true; // Token still valid
  }

  if (!refreshToken) {
    clearTokens();
    return false; // No refresh token available
  }

  try {
    const tokens = await refreshAccessToken(refreshToken);
    setTokens(tokens.access_token, tokens.refresh_token, tokens.expires_in);
    return true;
  } catch (error) {
    console.error("Token refresh failed:", error);
    clearTokens();
    return false;
  }
}

/**
 * Wrapper for async functions to refresh token before executing
 */
export async function withTokenRefresh<T>(fn: () => Promise<T>): Promise<T> {
  const tokenValid = await ensureValidToken();

  if (!tokenValid) {
    throw new Error("Authentication required. Please log in again.");
  }

  return fn();
}
