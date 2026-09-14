# KaiMS agentic AIOps roadmap

This roadmap turns KaiMS into a reliable operations agent instead of a chat layer over alerts. It follows the strongest common product patterns: noise reduction and event grouping, probable origin and change correlation, topology-aware causal analysis, governed actions, operator feedback, and explicit incident roles. PagerDuty documents those triage and orchestration capabilities; Dynatrace combines topology with event correlation and governed agentic actions; Datadog Watchdog separates anomaly detection, impact analysis, and RCA; Google SRE formalizes Incident Commander, Communications Lead, and Operations Lead roles.

## Product north star

KaiMS should move an incident through a durable evidence loop:

`detect -> group -> scope -> collect -> correlate -> explain -> decide -> act -> verify -> learn`

Every conclusion needs source evidence, every action needs a reviewed policy, and every outcome feeds evaluation. The agent may propose the next step, but it cannot convert a correlation into a cause or an unqualified runbook into production execution.

## Current baseline

Implemented in the preview:

- tenant-scoped application onboarding and document discovery;
- durable RabbitMQ discovery, context, collection, assessment, planning, authorization, execution and verification stages;
- unified alerts/investigations inbox;
- deterministic impact/RCA with trace relationships and measured latency findings;
- retention-safe reruns that preserve usable prior evidence;
- policy-bound execution with idempotency and two fresh recovery observations;
- operator feedback API and UI, with corrective reasons and evidence requests;
- durable incident role assignments for Incident Commander, Communications Lead and Operations Lead, plus append-only governance audit.

Still missing or deliberately unqualified:

- real multi-user identity, roles, separation of duties, ownership and escalation;
- topology/change/deployment connectors and causal scoring across them;
- source pagination, retention-aware backfill and a full-text/semantic knowledge index;
- production-quality log correlation and dependency server-span coverage for every connector;
- reviewed action catalog, rollback contracts, blast-radius checks and staged canaries;
- evaluation datasets, acceptance precision, false-accept tracking and feedback-driven model release;
- post-incident timeline, communications, tasks and postmortem workflow;
- MySQL concurrency qualification, HA deployment and operational SLOs.

## Delivery gates

### Gate 1 ? Trust and control

Add OIDC-backed users, teams, service ownership, Incident Commander/Communications/Operations roles, immutable audit records, policy versioning, approval separation, and tenant-scoped access tests. No action can run without an owner, scope, expiry, rollback and verification contract.

### Gate 2 ? Signal intelligence

Add canonical alert fingerprints, time-window grouping, suppression with expiry, related-incident search, topology edges, deployment/configuration events, and probable-origin scoring. Show the evidence and score components beside every recommendation.

### Gate 3 ? Agent investigation

Give the agent a bounded tool registry: query metrics/logs/traces, inspect deployment changes, retrieve approved documents, compare prior incidents, and request missing evidence. Persist an investigation graph and hypothesis ledger so the agent can explain what it checked and why it stopped.

### Gate 4 ? Safe action

Create an action catalog with dry-run, preconditions, blast-radius limits, idempotency, timeout, rollback, canary and postcondition checks. Start with disposable validation targets, then shadow mode, then human-approved production pilots. Automatic execution is enabled per policy and per service, never globally.

### Gate 5 ? Learning and qualification

Freeze independent Track B truth, score field accuracy, critical-field accuracy, accepted precision, critical accepted precision, field/claim HITL, STP_SAFE and false accepts. Use operator feedback as labeled data only after adjudication. Release model/policy changes behind replay and regression gates.

### Gate 6 ? Production operations

Qualify MySQL, RabbitMQ HA, retention/backfill, connector SLOs, rate limits, secrets rotation, disaster recovery, and a migration path from preview state. Measure MTTA/MTTR only after timestamps and ownership are authoritative.

## This release

The governance control plane now exposes `POST /applications/{application}/incidents/{incident}/assignments` and `GET .../governance`. It records role assignments and an append-only audit trail. The preview still reports `multi_user: false`; these are durable operational assignments, not an authorization boundary.

The feedback loop is now durable at `POST /applications/{application}/incidents/{incident}/feedback` and queryable at the matching `GET` endpoint. Feedback is attached to the incident and never mutates evidence. Corrective feedback requires a reason category. The incident page exposes helpful/incomplete/incorrect choices and stores missing-evidence and operator comments for later adjudication.

The telemetry/frontend repair policy remains unqualified because no verified diagnostic and idempotent repair contract exists. A latency spike alone must not authorize a restart.

## References

- PagerDuty AIOps feature areas: https://support.pagerduty.com/main/docs/aiops
- PagerDuty triage and RCA: https://support.pagerduty.com/main/docs/pagerduty-aiops-quickstart-guide
- Dynatrace Davis event correlation: https://docs.dynatrace.com/docs/semantic-dictionary/model/davis
- Dynatrace causal correlation: https://docs.dynatrace.com/docs/dynatrace-intelligence/reference/ai-models/causal-correlation-analysis
- Datadog Watchdog: https://docs.datadoghq.com/watchdog/
- Google SRE incident roles: https://sre.google/workbook/incident-response/
