// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectToolsPanel } from "./ConnectToolsPanel";
import * as cloudApi from "./cloudOpsApi";

vi.mock("../../app/SessionContext", () => ({
  useSession: () => ({ accessToken: "session-token" }),
}));

vi.mock("./cloudOpsApi", async () => {
  const actual = await vi.importActual<typeof import("./cloudOpsApi")>("./cloudOpsApi");
  return { ...actual, listConnectorCatalog: vi.fn(), createIntegrationConnection: vi.fn() };
});

const CATALOG: cloudApi.ConnectorCatalogEntry[] = [
  { connector_id: "jira", provider_type: "itsm", display_name: "Jira", fields: [{ name: "base_url", label: "Site URL" }, { name: "email", label: "Account email" }], secret_label: "API token" },
  { connector_id: "prometheus", provider_type: "monitoring", display_name: "Prometheus", fields: [{ name: "base_url", label: "Server URL" }], secret_label: "Bearer token", secret_optional: true },
];

afterEach(cleanup);

describe("ConnectToolsPanel", () => {
  it("lists ticketing connectors first and lets the operator create a connection", async () => {
    vi.mocked(cloudApi.listConnectorCatalog).mockResolvedValue(CATALOG);
    vi.mocked(cloudApi.createIntegrationConnection).mockResolvedValue({} as cloudApi.CloudConnection);
    const onConnected = vi.fn();

    render(<ConnectToolsPanel projectId="demo-project" owner="admin" onConnected={onConnected} />);
    await act(async () => { await Promise.resolve(); });

    expect(screen.getByRole("button", { name: /Connect Jira/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Connect Prometheus/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Connect Jira/ }));
    fireEvent.change(screen.getByLabelText("Site URL"), { target: { value: "https://acme.atlassian.net" } });
    fireEvent.change(screen.getByLabelText("Account email"), { target: { value: "bot@acme.com" } });
    fireEvent.change(screen.getByLabelText(/API token/), { target: { value: "env://JIRA_API_TOKEN" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Save Jira connection/ }));
      await Promise.resolve();
    });

    expect(cloudApi.createIntegrationConnection).toHaveBeenCalledWith("session-token", expect.objectContaining({
      projectId: "demo-project",
      connectorId: "jira",
      providerType: "itsm",
      secretRef: "env://JIRA_API_TOKEN",
      scopeFields: { base_url: "https://acme.atlassian.net", email: "bot@acme.com" },
    }));
    expect(onConnected).toHaveBeenCalled();
  });

  it("switches to the monitoring tab and shows monitoring tiles", async () => {
    vi.mocked(cloudApi.listConnectorCatalog).mockResolvedValue(CATALOG);
    render(<ConnectToolsPanel projectId="demo-project" owner="admin" onConnected={vi.fn()} />);
    await act(async () => { await Promise.resolve(); });

    fireEvent.click(screen.getByRole("tab", { name: "Monitoring" }));
    expect(screen.getByRole("button", { name: /Connect Prometheus/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Connect Jira/ })).not.toBeInTheDocument();
  });
});
