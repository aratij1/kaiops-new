# Resolution pipeline audit ? 2026-09-07

The review traced context/investigation, governed plan selection, approval,
remediation dispatch and reconciliation, recovery validation, persistence,
broker delivery, Jira synchronization, and frontend resolution controls.

## Fixed gaps

- Pending stability now remains `pending_stability` in the lifecycle and report,
  with incident status `validating`. Pending and failed validation use separate
  report and event identities, so a pending event cannot suppress a later failure.
- Plan-integrity failures cannot be mislabeled as an incomplete stability window.
- Recovery samples must belong to the post-execution period and correct phase.
  Duplicate timestamps cannot satisfy the minimum sample count. Malformed,
  timezone-free pre-state observations are ignored safely.
- Closure builds the outgoing event after finalizing its lifecycle and ticket
  binding. The report, saved incident, immediate event, and outbox agree.
- Jira synchronization preserves the outbox delivery flag even when Jira skips
  an update or fails.
- Report, learning, incident, audit, and outbox writes share one transaction.
  Duplicate delivery does not repeat learning outcomes; pending stability does
  not count as a runbook failure.
- Closure serializes incident writes and rejects mismatched tenant/incident
  identities, superseded plans and attempts, and older lifecycle versions.
- Related incidents no longer close using copied action/report identities.
  Each incident requires its own recovery evidence.
- Administrative closure checks the lifecycle before attempting Jira updates;
  active execution cannot be administratively closed. Quiescent closure keeps
  the operator identity and makes no technical-recovery claim.
- Legacy payload construction preserves the action tenant when no prior
  incident payload is available.

## Verification and limits

`backend/tests/test_closure_pipeline_handoffs.py` adds database-backed handoff,
replay, stale identity, evidence, manual closure, and transaction rollback tests.
Existing backend and frontend suites cover investigation, governance, approval,
execution contracts, lifecycle transitions, and UI controls.

Tests use isolated SQLite and mocked external calls. They do not establish live
MySQL row-lock behavior, broker redelivery, Temporal worker execution, Jenkins
execution, or Jira delivery.

The missing independent-observer runtime was implemented in the follow-up.
Closure can now collect registered Prometheus range observations and resume
pending stability from persisted actions after restart. Plan compilation binds
registered validator specs rather than treating every check as availability.
See [Independent recovery observations](independent-recovery-observers.md) for
the implementation, activation steps, and supported extension approaches.

Production activation still requires reviewed, target-specific query profiles
and deployment configuration; live production recovery was not exercised.
