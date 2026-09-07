import { CheckCircle2, CircleAlert, CircleDashed, ShieldAlert, ShieldCheck } from "lucide-react";

export interface ReadinessCheck {
  id: string;
  label: string;
  detail: string;
  /** When a check has several distinct blocking reasons, list them here instead of
   * cramming them into `detail` as one run-on, semicolon-joined sentence. */
  detailList?: string[];
  passed: boolean;
  action?: string;
}

interface DecisionReadinessPanelProps {
  title?: string;
  checks: ReadinessCheck[];
  eligibleLabel?: string;
  onReviewEvidence?: () => void;
  /** True when the full bar above isn't cleared, but evidence collection has
   * genuinely run its course (nothing left in flight) rather than merely
   * being incomplete so far. Renders a distinct "reviewable with caveats"
   * state instead of the same open-ended "not ready" as an investigation
   * that is still actively collecting evidence. Never affects auto-execution
   * eligibility - that stays governed entirely by `ready`. */
  partiallyEligible?: boolean;
  partiallyEligibleLabel?: string;
  partialNote?: string;
}

export default function DecisionReadinessPanel({
  title = "Decision readiness",
  checks,
  eligibleLabel = "Ready for guarded operator review",
  onReviewEvidence,
  partiallyEligible = false,
  partiallyEligibleLabel = "Partial evidence — operator judgment required",
  partialNote,
}: DecisionReadinessPanelProps) {
  const missing = checks.filter((check) => !check.passed);
  const passed = checks.filter((check) => check.passed);
  const ready = checks.length > 0 && missing.length === 0;
  const partial = !ready && partiallyEligible;

  return (
    <section className={`readiness-gate ${ready ? "is-ready" : partial ? "is-partial" : "is-blocked"}`} aria-labelledby="readiness-gate-title">
      <header>
        <div>
          <span className="discovery-eyebrow">Evidence and safety gate</span>
          <h4 id="readiness-gate-title">{title}</h4>
        </div>
        <span className="readiness-gate-status" role="status">
          {ready ? <ShieldCheck size={18} /> : partial ? <ShieldAlert size={18} /> : <CircleAlert size={18} />}
          {ready ? eligibleLabel : partial ? partiallyEligibleLabel : `Not ready · ${missing.length} of ${checks.length} requirement${checks.length === 1 ? "" : "s"} remaining`}
        </span>
      </header>
      {partial ? <p className="readiness-gate-partial-note">{partialNote || "Evidence collection has exhausted every automated and human avenue available for this incident - waiting longer will not produce more of it. The gaps below are real; weigh them yourself before acting."}</p> : null}

      {/* Blocking requirements get the room to actually be read - a wall of same-size
          cards (passed and failed mixed together) was how a single check with many
          distinct reasons turned into an unreadable run-on paragraph. Everything that
          still needs attention is listed first, in full; what's already satisfied is
          folded into one compact strip below it. */}
      {missing.length ? (
        <ul className="readiness-checks readiness-checks-missing">
          {missing.map((check) => (
            <li key={check.id} className="is-missing">
              <CircleDashed size={17} aria-hidden="true" />
              <div>
                <strong>{check.label}</strong>
                {check.detailList?.length ? (
                  <ul className="readiness-check-reasons">
                    {check.detailList.map((reason, index) => <li key={`${check.id}-${index}`}>{reason}</li>)}
                  </ul>
                ) : (
                  <span>{check.detail}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {passed.length ? (
        <details className="readiness-checks-passed" open={!missing.length}>
          <summary>
            <CheckCircle2 size={15} aria-hidden="true" />
            {passed.length} of {checks.length} requirement{checks.length === 1 ? "" : "s"} already satisfied
          </summary>
          <ul className="readiness-checks">
            {passed.map((check) => (
              <li key={check.id} className="is-passed">
                <CheckCircle2 size={17} aria-hidden="true" />
                <div><strong>{check.label}</strong><span>{check.detail}</span></div>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {!ready ? (
        <footer>
          <div>
            <strong>Next steps</strong>
            <ol>
              {missing.map((check) => <li key={check.id}>{check.action || check.label}</li>)}
            </ol>
          </div>
          {onReviewEvidence ? <button type="button" className="button-secondary" onClick={onReviewEvidence}>Review missing evidence</button> : null}
        </footer>
      ) : null}
    </section>
  );
}
