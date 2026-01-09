export const OAUTH_CONFIG = {
  authorizationEndpoint: `${import.meta.env.VITE_IDENTITY_URL}/oauth/authorize`,
  tokenEndpoint: `${import.meta.env.VITE_IDENTITY_URL}/oauth/token`,
  refreshEndpoint: `${import.meta.env.VITE_IDENTITY_URL}/oauth/refresh`,
  clientId: import.meta.env.VITE_OAUTH_CLIENT_ID,
  redirectUri: `${window.location.origin}/oauth/callback`,
  scope: "openid profile email",
};
