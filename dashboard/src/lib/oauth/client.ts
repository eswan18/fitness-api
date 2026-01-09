import { OAUTH_CONFIG } from "./config";
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
} from "./pkce";

export interface OAuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  scope: string;
}

/**
 * Start OAuth authorization flow
 */
export async function startOAuthFlow(): Promise<void> {
  // Generate PKCE parameters
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  const state = generateState();

  // Store verifier and state in sessionStorage for callback
  sessionStorage.setItem("oauth_code_verifier", codeVerifier);
  sessionStorage.setItem("oauth_state", state);

  // Build authorization URL
  const params = new URLSearchParams({
    response_type: "code",
    client_id: OAUTH_CONFIG.clientId,
    redirect_uri: OAUTH_CONFIG.redirectUri,
    scope: OAUTH_CONFIG.scope,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  const authUrl = `${OAUTH_CONFIG.authorizationEndpoint}?${params}`;

  // Redirect to identity provider
  window.location.href = authUrl;
}

/**
 * Handle OAuth callback after authorization
 */
export async function handleOAuthCallback(): Promise<OAuthTokens> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const state = params.get("state");
  const error = params.get("error");

  if (error) {
    throw new Error(
      `OAuth error: ${error} - ${params.get("error_description")}`
    );
  }

  if (!code) {
    throw new Error("No authorization code received");
  }

  // Verify state (CSRF protection)
  const storedState = sessionStorage.getItem("oauth_state");
  if (!state || !storedState || state !== storedState) {
    throw new Error("Invalid state parameter");
  }

  // Get code verifier
  const codeVerifier = sessionStorage.getItem("oauth_code_verifier");
  if (!codeVerifier) {
    throw new Error("Code verifier not found");
  }

  // Exchange code for tokens
  const tokenResponse = await fetch(OAUTH_CONFIG.tokenEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: OAUTH_CONFIG.redirectUri,
      client_id: OAUTH_CONFIG.clientId,
      code_verifier: codeVerifier,
    }),
  });

  if (!tokenResponse.ok) {
    const errorData = await tokenResponse.json().catch(() => ({}));
    throw new Error(
      `Token exchange failed: ${errorData.error_description || tokenResponse.statusText}`
    );
  }

  const tokens: OAuthTokens = await tokenResponse.json();

  // Clean up PKCE parameters
  sessionStorage.removeItem("oauth_code_verifier");
  sessionStorage.removeItem("oauth_state");

  return tokens;
}

/**
 * Refresh access token using refresh token
 */
export async function refreshAccessToken(
  refreshToken: string
): Promise<OAuthTokens> {
  const response = await fetch(OAUTH_CONFIG.refreshEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: OAUTH_CONFIG.clientId,
    }),
  });

  if (!response.ok) {
    throw new Error("Token refresh failed");
  }

  return response.json();
}
