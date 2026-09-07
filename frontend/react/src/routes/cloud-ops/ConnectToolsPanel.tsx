import { useEffect, useMemo, useState } from "react";
import { KeyRound, Link2 } from "lucide-react";

import { useSession } from "../../app/SessionContext";
import { createIntegrationConnection, listConnectorCatalog, type ConnectorCatalogEntry } from "./cloudOpsApi";

type Category = "itsm" | "monitoring";

const CATEGORY_LABEL: Record<Category, string> = { itsm: "Ticketing / ITSM", monitoring: "Monitoring" };

/** Onboarding step: connect a ticketing platform (Jira, ServiceNow, Azure DevOps) or a
 * monitoring tool (Prometheus, Grafana, Datadog) so discovery and the knowledge base
 * have somewhere real to read from. Connections created here show up in the connection
 * list below with the same Validate / Discover actions as every other provider. */
export function ConnectToolsPanel({ projectId, owner, onConnected }: { projectId: string; owner: string; onConnected: () => void }) {
  const { accessToken } = useSession();
  const [category, setCategory] = useState<Category>("itsm");
  const [catalog, setCatalog] = useState<ConnectorCatalogEntry[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const [selected, setSelected] = useState<ConnectorCatalogEntry | null>(null);
  const [name, setName] = useState("");
  const [secretRef, setSecretRef] = useState("");
  const [scopeFields, setScopeFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!accessToken) return undefined;
    listConnectorCatalog(accessToken)
      .then((rows) => { if (!cancelled) setCatalog(rows); })
      .catch((err) => { if (!cancelled) setCatalogError(err instanceof Error ? err.message : "Unable to load connector catalog"); });
    return () => { cancelled = true; };
  }, [accessToken]);

  const tiles = useMemo(() => catalog.filter((entry) => entry.provider_type === category), [catalog, category]);

  function selectConnector(entry: ConnectorCatalogEntry) {
    setSelected(entry);
    setName(`${entry.display_name} connection`);
    setSecretRef("");
    setScopeFields({});
    setError("");
    setSuccess("");
  }

  async function submit() {
    if (!selected || !projectId) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await createIntegrationConnection(accessToken, {
        projectId,
        connectorId: selected.connector_id,
        providerType: selected.provider_type,
        connectionName: name.trim() || `${selected.display_name} connection`,
        secretRef: secretRef.trim(),
        scopeFields,
        owner,
      });
      setSuccess(`${selected.display_name} connection created. Validate it below, then discover its resources.`);
      setSelected(null);
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to connect ${selected.display_name}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="cloud-ops-panel" aria-labelledby="connect-tools-title">
      <header>
        <div>
          <h2 id="connect-tools-title">Connect your tools</h2>
          <p>Onboard a ticketing platform or monitoring tool so discovery and the knowledge base can read from it.</p>
        </div>
      </header>

      <div className="cloud-ops-toolbar" role="tablist" aria-label="Connector category">
        {(Object.keys(CATEGORY_LABEL) as Category[]).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={category === key}
            className={category === key ? "button-primary" : "button-secondary"}
            onClick={() => { setCategory(key); setSelected(null); }}
          >
            {CATEGORY_LABEL[key]}
          </button>
        ))}
      </div>

      {catalogError ? <div className="cloud-ops-error" role="alert">{catalogError}</div> : null}

      <div className="cloud-ops-grid">
        {tiles.map((entry) => (
          <button
            key={entry.connector_id}
            type="button"
            className={`cloud-ops-card cloud-ops-connector-tile ${selected?.connector_id === entry.connector_id ? "is-selected" : ""}`}
            onClick={() => selectConnector(entry)}
          >
            <Link2 size={18} aria-hidden="true" />
            <strong>{entry.display_name}</strong>
            <span>Connect {entry.display_name}</span>
          </button>
        ))}
        {!tiles.length && !catalogError ? <p className="cloud-ops-empty">Loading connector catalog…</p> : null}
      </div>

      {selected ? (
        <form
          className="cloud-ops-toolbar cloud-ops-connect-form"
          onSubmit={(event) => { event.preventDefault(); void submit(); }}
          aria-label={`Connect ${selected.display_name}`}
        >
          <label>
            <span>Connection name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          {selected.fields.map((field) => (
            <label key={field.name}>
              <span>{field.label}</span>
              <input
                value={scopeFields[field.name] || ""}
                placeholder={field.placeholder}
                onChange={(event) => setScopeFields((current) => ({ ...current, [field.name]: event.target.value }))}
                required
              />
            </label>
          ))}
          <label>
            <span><KeyRound size={13} aria-hidden="true" /> {selected.secret_label}{selected.secret_optional ? " (optional)" : ""}</span>
            <input
              value={secretRef}
              placeholder="env://VARIABLE_NAME"
              onChange={(event) => setSecretRef(event.target.value)}
              required={!selected.secret_optional}
            />
          </label>
          <div className="field-hint">Reference a secret already set as an environment variable on the cloud-operations service, e.g. <code>env://JIRA_API_TOKEN</code>. KaiMS never stores the raw credential.</div>
          <div className="button-row">
            <button type="submit" className="button-primary" disabled={busy || !projectId}>
              {busy ? "Connecting…" : `Save ${selected.display_name} connection`}
            </button>
            <button type="button" className="button-secondary" onClick={() => setSelected(null)}>Cancel</button>
          </div>
        </form>
      ) : null}

      {error ? <div className="cloud-ops-error" role="alert">{error}</div> : null}
      {success ? <p className="status-message" role="status">{success}</p> : null}
    </article>
  );
}
