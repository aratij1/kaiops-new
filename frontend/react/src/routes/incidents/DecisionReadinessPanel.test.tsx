// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import DecisionReadinessPanel from "./DecisionReadinessPanel";

afterEach(cleanup);

const unmetChecks = [
  { id: "confidence", label: "Evidence confidence", detail: "40% investigation confidence.", passed: false, action: "publish corroborated evidence-derived confidence of at least 65%" },
  { id: "grounding", label: "Grounding coverage", detail: "9% grounding coverage.", passed: false, action: "raise grounding coverage to at least 85%" },
];

describe("DecisionReadinessPanel", () => {
  it("reports a hard block when the gate is unmet and no partial tier is offered", () => {
    render(<DecisionReadinessPanel title="Investigation readiness" checks={unmetChecks} />);
    expect(screen.getByText(/Not ready · 2 of 2 requirements remaining/)).toBeInTheDocument();
    expect(document.querySelector(".readiness-gate.is-blocked")).toBeInTheDocument();
    expect(document.querySelector(".readiness-gate.is-partial")).not.toBeInTheDocument();
  });

  it("renders a distinct partial-evidence state instead of the open-ended block, without hiding what's missing", () => {
    render(<DecisionReadinessPanel
      title="Investigation readiness"
      checks={unmetChecks}
      partiallyEligible
      partiallyEligibleLabel="Partial evidence — operator review recommended"
    />);
    expect(screen.getByText("Partial evidence — operator review recommended")).toBeInTheDocument();
    expect(screen.queryByText(/Not ready · 2 of 2/)).not.toBeInTheDocument();
    expect(document.querySelector(".readiness-gate.is-partial")).toBeInTheDocument();
    // The specific gaps are still fully disclosed - partial eligibility relabels the
    // top-line verdict, it never hides why the gate isn't fully cleared.
    expect(screen.getByText("9% grounding coverage.")).toBeInTheDocument();
    expect(screen.getByText("40% investigation confidence.")).toBeInTheDocument();
  });

  it("never shows the partial state once every check actually passes", () => {
    render(<DecisionReadinessPanel
      title="Investigation readiness"
      checks={unmetChecks.map((check) => ({ ...check, passed: true }))}
      partiallyEligible
      eligibleLabel="Evidence ready for operator review"
    />);
    expect(screen.getByText("Evidence ready for operator review")).toBeInTheDocument();
    expect(document.querySelector(".readiness-gate.is-ready")).toBeInTheDocument();
    expect(document.querySelector(".readiness-gate.is-partial")).not.toBeInTheDocument();
  });
});
