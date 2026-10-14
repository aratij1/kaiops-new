import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { z } from "zod";
import { requestValidated } from "../../services/apiClient";

interface InvestigationRetryProps {
  alertId?: string;
  accessToken?: string;
  disabled?: boolean;
}

export function InvestigationRetry({ alertId, accessToken, disabled = false }: InvestigationRetryProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  if (!alertId) return null;

  async function handleRetry() {
    if (!alertId || loading || disabled) return;
    setLoading(true);
    setError(null);
    setStatusMessage(null);

    try {
      await requestValidated(
        `/analysis/alerts/${encodeURIComponent(alertId)}/regenerate`,
        z.unknown(),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({ mode: "fresh" }),
        }
      );
      setStatusMessage("Analysis regeneration queued in the backend.");
    } catch (err: any) {
      setError(err?.message || "Failed to trigger analysis retry.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ic-investigation-retry">
      <button
        type="button"
        className="button-secondary"
        onClick={handleRetry}
        disabled={disabled || loading}
      >
        <RefreshCw className={loading ? "spin" : ""} size={14} aria-hidden="true" />
        {loading ? "Triggering RCA retry..." : "Re-run RCA investigation"}
      </button>
      {statusMessage ? <p className="status-message" role="status">{statusMessage}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
    </div>
  );
}
