// @vitest-environment jsdom
import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { InvestigationRecords } from "./InvestigationRecords";
afterEach(cleanup);
const evidence = Array.from({length: 145}, (_, index) => ({evidence_id: `evidence-${index}`, category: index === 144 ? "logs" : "topology", citation: `source-${index}`, accepted_for_rca: false}));
it("keeps the library collapsed and paginates every record without dropping duplicates", () => {
 const {container}=render(<InvestigationRecords evidence={evidence} requirements={[]} />);
 expect(container.querySelector("details")?.open).toBe(false);
 expect(container.querySelectorAll(".ic-attached-records li")).toHaveLength(8);
 fireEvent.click(screen.getByText("Browse evidence (145)"));
 fireEvent.click(screen.getByRole("button",{name:"Next evidence"}));
 expect(screen.getByText("9-16 of 145")).toBeTruthy();
});
it("searches all records, resets pagination, and keeps requirements visible", () => {
 render(<InvestigationRecords evidence={evidence} requirements={[{question:"Confirm queue processing",category:"metrics",status:"open"}]} />);
 expect(screen.getByText("Confirm queue processing")).toBeTruthy();
 fireEvent.click(screen.getByText("Browse evidence (145)"));
 fireEvent.click(screen.getByRole("button",{name:"Next evidence"}));
 fireEvent.change(screen.getByLabelText("Search evidence"),{target:{value:"source-144"}});
 expect(screen.getByText("source-144")).toBeTruthy();
 expect(screen.getByText("1-1 of 1")).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Category"),{target:{value:"topology"}});
 expect(screen.getByText("No evidence matches these filters.")).toBeTruthy();
});
