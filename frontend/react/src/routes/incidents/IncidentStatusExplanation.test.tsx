// @vitest-environment jsdom
import { render, fireEvent, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { IncidentStatusExplanation } from "./IncidentStatusExplanation";
it("keeps full backend blockers available on demand without expanding the queue by default", () => {
 const blocker="Unsupported operation; missing rollback; ".repeat(30);
 const {container}=render(<IncidentStatusExplanation blocker={blocker} reason="" />);
 expect(container.querySelector("details")?.open).toBe(false);
 fireEvent.click(screen.getByText("Review resolution blockers"));
 expect(container.querySelector("details")?.open).toBe(true);
 expect(container.querySelector("p")?.textContent).toBe(blocker);
});
