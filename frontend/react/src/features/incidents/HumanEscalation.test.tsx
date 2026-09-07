// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import HumanEscalation from "./HumanEscalation";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const props = { incidentId: "incident-1", service: "mysql", severity: "high", accessToken: "test-token", onEscalated: vi.fn() };
function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText("Reason for escalation"), { target: { value: "Please investigate the unavailable database" } });
  fireEvent.click(screen.getByRole("button", { name: "Escalate to human agent" }));
}
it("requires a reason and confirms the assigned responder", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "escalated", assignment: { assignee: "responder@example.test" } }) });
  vi.stubGlobal("fetch", fetchMock);
  render(<HumanEscalation {...props} />);
  expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  fillAndSubmit();
  expect((await screen.findByRole("status")).textContent).toContain("responder@example.test");
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("/api-gateway/incidents/incident-1/escalate");
  expect(JSON.parse(options.body)).toEqual({ comment: "Please investigate the unavailable database", service: "mysql", severity: "high", resource_names: ["mysql"] });
  expect(options.headers.Authorization).toBe("Bearer test-token");
  expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
});
it.each([403, 409])("shows rejected handoff (%s) without claiming success", async (status) => {
  const refreshed = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ detail: { message: "Human assignment is unavailable" } }) }));
  render(<HumanEscalation {...props} onEscalated={refreshed} />);
  fillAndSubmit();
  expect((await screen.findByRole("alert")).textContent).toContain("Human assignment is unavailable");
  expect(refreshed).not.toHaveBeenCalled();
  expect(screen.queryByRole("status")).toBeNull();
});
it("keeps confirmed success when the follow-up refresh fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "escalated", assignment: { assignee: "operator" } }) }));
  render(<HumanEscalation {...props} onEscalated={async () => { throw new Error("refresh unavailable"); }} />);
  fillAndSubmit();
  expect((await screen.findByRole("status")).textContent).toContain("Assigned to operator");
  expect(screen.queryByRole("alert")).toBeNull();
});
