// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ResolutionPanel from "./ResolutionPanel";

const { fetchJson } = vi.hoisted(() => ({ fetchJson: vi.fn() }));
vi.mock("../../services/routeApi", () => ({ routeJson: fetchJson }));
vi.mock("../../app/SessionContext", () => ({ useSession: () => ({ accessToken: "test-token" }) }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
beforeEach(() => {
  // Existing tests below never set `workflow.incident.id`, so the panel's
  // live approval-readiness fetch never fires for them regardless of this
  // default - it only matters for the new test that does set an incident id.
  fetchJson.mockResolvedValue({});
});
const base = { alertRow: { service: "payments-api", environment: "prod" }, confidenceScore: .88, onNavigateTab: vi.fn() };
describe("ResolutionPanel", () => {
  it("shows exact governed scripts and the reason", () => {
    render(<ResolutionPanel {...base} workflow={{ investigation_integrity: { verified: true }, recommendation: { id: "rec-1", recommended_action: "Restart the unhealthy revision", root_cause: "Connection pool exhaustion is confirmed." } }} executionPlan={{ requiresApproval: true, riskTier: "high", executionMode: "jenkins", target: "payments-api", expectedOutcome: "Error rate returns below 1%.", catalogPlan: { plan_id: "p1", plan_fingerprint: `sha256:${"a".repeat(64)}`, recommendation_id: "rec-1", commands: ["kubectl rollout restart deployment/payments-api -n prod"], validation_commands: ["kubectl rollout status deployment/payments-api -n prod"], rollback_commands: ["kubectl rollout undo deployment/payments-api -n prod"] }, readinessDecision: { decision_id: "d1", signature: "signed", state: "execution_eligible", plan_id: "p1", plan_fingerprint: `sha256:${"a".repeat(64)}`, recommendation_id: "rec-1" } }} />);
    expect(screen.getByRole("heading", { name: "Review execution plan" })).toBeVisible();
    // The RCA conclusion now also appears in the recap strip that connects this
    // panel back to the evidence/RCA tab, in addition to the purpose paragraph -
    // both are expected, so assert presence rather than a single unique match.
    expect(screen.getAllByText("Connection pool exhaustion is confirmed.", { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText("kubectl rollout restart deployment/payments-api -n prod")).toBeVisible();
    expect(screen.getByText("kubectl rollout status deployment/payments-api -n prod")).toBeVisible();
    expect(screen.getByText("kubectl rollout undo deployment/payments-api -n prod")).toBeVisible();
  });
  it("does not fake a remediation script for evidence collection", () => {
    render(<ResolutionPanel {...base} workflow={{ recommendation: { recommended_action: "Collect traces evidence for this incident.", root_cause: "Causal confirmation is still required." } }} executionPlan={{ target: "payments-api" }} />);
    expect(screen.getByText("No executable remediation script is available")).toBeVisible();
    expect(screen.getByText(/close the evidence gaps/)).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspect safeguards/ })).toBeDisabled();
  });
  it("labels model commands review-only", () => {
    render(<ResolutionPanel {...base} workflow={{ recommendation: { recommended_action: "Restart API", root_cause: "API stopped responding", metadata: { model_proposed_execution_plan: { commands: ["systemctl restart api"] } } } }} executionPlan={{ target: "api" }} />);
    expect(screen.getByText("Review-only model suggestion")).toBeVisible();
    expect(screen.getByText("systemctl restart api")).toBeInTheDocument();
    expect(screen.getByText(/not governed and cannot be executed/)).toBeInTheDocument();
  });
  it("carries the RCA conclusion forward and links back to it, so resolution reads as a continuation", () => {
    const onNavigateTab = vi.fn();
    render(<ResolutionPanel {...base} onNavigateTab={onNavigateTab} workflow={{ recommendation: { recommended_action: "Restart API", root_cause: "Connection pool exhaustion is confirmed.", confidence: 0.82 } }} executionPlan={{ target: "api" }} />);
    const recap = screen.getByRole("button", { name: /Connection pool exhaustion is confirmed/ });
    expect(recap).toBeVisible();
    expect(recap).toHaveTextContent("82%");
    fireEvent.click(recap);
    expect(onNavigateTab).toHaveBeenCalledWith("rca");
  });
  it("fetches the live, real approval-readiness receipt instead of always reporting it missing", async () => {
    // approval-service computes this receipt correctly, but only inside its
    // own GET /incident/{id} handler - nothing ever called it before, so
    // this checklist item showed "missing" for every incident regardless of
    // true readiness. Once the live fetch resolves a real, valid receipt,
    // that specific reason must disappear (other, unrelated reasons - no
    // investigation integrity, no bound plan - correctly remain, since this
    // test doesn't supply them).
    fetchJson.mockResolvedValueOnce({
      data: { approval_readiness: { decision_id: "decision-live-1", signature: "hmac-sha256:abc", state: "eligible" } },
    });
    render(<ResolutionPanel {...base} workflow={{
      incident: { id: "incident-1" },
      recommendation: { recommended_action: "Restart API", root_cause: "Connection pool exhaustion is confirmed." },
    }} executionPlan={{ target: "api" }} />);

    await waitFor(() => {
      expect(fetchJson).toHaveBeenCalledWith(
        "/api-gateway/approval/incident/incident-1",
        expect.objectContaining({ headers: { Authorization: "Bearer test-token" } }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByText("signed backend approval-readiness receipt is missing")).not.toBeInTheDocument();
    });
  });
});
