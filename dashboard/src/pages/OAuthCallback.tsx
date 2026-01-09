import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { handleOAuthCallback } from "@/lib/oauth/client";
import { useDashboardStore } from "@/store";
import { notifySuccess, notifyError } from "@/lib/errors";

export function OAuthCallback() {
  const navigate = useNavigate();
  const { setTokens } = useDashboardStore();
  const [error, setError] = useState<string | null>(null);
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Guard against double execution in React StrictMode
    if (hasProcessed.current) {
      return;
    }
    hasProcessed.current = true;

    async function processCallback() {
      try {
        const tokens = await handleOAuthCallback();
        setTokens(tokens.access_token, tokens.refresh_token, tokens.expires_in);
        notifySuccess("Logged in successfully!");
        navigate("/");
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Authentication failed";
        setError(message);
        notifyError(err, "Authentication failed");
      }
    }

    processCallback();
  }, [navigate, setTokens]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Authentication Error</h1>
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => navigate("/")}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Authenticating...</h1>
        <p>Please wait while we complete your login.</p>
      </div>
    </div>
  );
}
