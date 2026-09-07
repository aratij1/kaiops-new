# Incident flow recovery, 2026-09-07

## Latest outcome: one live incident closed

`MySQLExporterDatabaseConnectionFailed` (`4e0efeed-3c9c-47bc-ae9d-6e89e2212474`)
closed at **10:04:40 IST** after an operator-authorized independent recovery
assessment. Six registered checks produced 66 passing observations spanning
09:59:30 to 10:04:30 IST. The repair occurred outside the KaiMS executor;
the report preserves that distinction and leaves the causal RCA inconclusive.

The closure event is published. The canonical incident, resolution lifecycle,
and incident lifecycle projection all show closed. The UI shows the result under
**KaiMS > Incidents > Resolved recently**. See the
[live closure evidence](mysql-exporter-recovery-closure-proof-2026-09-07.json) and
[board capture](mysql-exporter-recovery-closed-2026-09-07.png).

The remaining incidents still require their specific evidence, supported actions,
and policies described below. No blanket closure or generic restart was applied.

## What the screenshot represented

The resolution consumer was running, but 408 old context messages remained in
its dead-letter queue. The active resolution queue was empty with two consumers.
A worker restart does not automatically replay failed messages. Several visible
incidents already had completed RCA recommendations whose status was
`insufficient_evidence`; the board still called those attempts `Generating RCA`.
The diagnostic CLI also wrongly treated every binding other than `current` as
`RCA_NOT_CURRENT`, including legitimate `grounded` and `insufficient_evidence`
outcomes. The detailed database inspection corrected the initial interpretation:
these records were not simply missing or stale RCA snapshots.

## Repairs and recovery performed

- Added a tenant-scoped, batched compact read of current recommendation outcomes,
  completion timestamps, execution-readiness blockers, and evidence gaps. Full
  evidence payloads are not loaded into the compact incident list.
- The board now distinguishes completed-but-blocked analysis from active RCA
  generation. It shows Action required, the blocked stage, and specific reasons.
  Earlier analysis does not override approval, execution, validation, or closure.
- Fixed a projection helper that could incorrectly advance an insufficient-evidence
  RCA to rca_ready because its projection update lacked the grounded guard.
- Corrected the diagnostic CLI's UUID normalization and RCA status classification.
- Corrected PolicyEngineUnavailable: absence of an event counter before the first
  event is not a service outage. The rule now uses the independently scraped
  orchestrator target and identifies its service and environment.
- Rebuilt and deployed monitoring-adapter, resolution-agent, and the UI. Validated
  and reloaded all 64 Prometheus rules.

Three explicit fresh analysis requests were submitted through the authenticated
regeneration API and observed to complete with new recommendation events:

| Incident | Analysis request | New recommendation |
| --- | --- | --- |
| 28316068-c6ab-4ac3-8d4b-caba8f92d638 | d9df94f3-42c1-4cde-870b-afff091abf21 | fd2ce0f1-63dc-5eff-9704-8957b58712ea |
| 4e0efeed-3c9c-47bc-ae9d-6e89e2212474 | 95c05831-b3d7-4e75-9fde-ee70f52eed5c | 21d5e3ea-35a9-5b95-96ee-69d56314e64c |
| 6d716f52-c67d-41fa-ac55-7d73a120da37 | 821dbfb8-7fab-49df-8cde-f859ccb51556 | d894116f-5f67-5571-8511-42f2b235d5a9 |

All three emitted new incident.recommendation.generated records. This verifies
analysis-to-recommendation flow; it does not prove execution or closure.

## Remaining incident-specific prerequisites

- **MySQL alert-table row count:** retention_days is unspecified; archive_database_rows
  has no implemented Docker executor operation or executable rollback. The current
  RCA is also inconclusive. A retention policy and reviewed archival implementation
  are required before database cleanup can be offered for execution.
- **MySQL exporter authentication: completed.** The repaired exporter passed a
  separate observed-recovery assessment and the incident is closed. The generic
  recommendation was not executed or promoted to grounded. Recovery checks bind
  the assessment, not a fictional remediation action.
- **Policy engine unavailable:** the false idle-worker alert rule is fixed. The
  current recommendation remains inconclusive and has no supported restart plan,
  rollback, or matching observer profile. No unnecessary restart was performed.
- **Latency incidents:** current plans contain unsupported scaling/rollback choices
  and require explicit replica/revision parameters plus corroborated causal evidence.
- **External httpbin failure lab:** this target deliberately requests /status/503;
  local KaiMS cannot repair a third-party application by restarting itself.

The registry now covers twenty service-down profiles for ten KaiMS
jobs plus the exact MySQL exporter connection-failure profile. It does not cover every alert in the screenshot. Missing profiles must not
be substituted with unrelated checks or healthy constants.

## Verification

23 repository tests passed, including compact outcome visibility and tenant
isolation. Nine incident-route tests and TypeScript checks passed. The production
UI build and bundle budget checks passed. Ruff F checks passed for changed Python
files. A real authenticated browser, with project KaiMS selected, showed ten
Action required badges and ten Analysis completed; resolution blocked captions.
See [the live board capture](incident-flow-live-2026-09-07.png).

The initial investigation did not manually close incidents, bypass approvals, delete alert history, or
purge dead-letter queues. The remaining evidence, capability, and approval gates
are explicit rather than disguised as perpetual RCA generation.


## Implemented observed-recovery path

- Gateway-authenticated assessment requests derive operator identity and tenant
  server-side. The internal route independently checks the service token and role.
- Exact profiles opt in with `allow_operator_verified_closure`; the default is
  false. Only the MySQL exporter profile is opted in locally.
- Requests and their start time survive closure-service restarts. The background
  evaluator requires a complete post-request five-minute window, 11 samples per
  check at 30-second intervals, and all six checks passing. Missing or failed
  observations keep the incident open; requests expire after an hour.
- Incident membership, recommendation, both lifecycle bindings, execution work,
  and profile/source digests are checked before collection and again under the
  closure transaction lock. Superseded work cannot close a newer incident state.
- The audit outcome, report, normalized observations, canonical closure and event
  outbox commit together. The verified closure also advances the separate
  incident lifecycle projection with an explicit observed-recovery transition.
  It does not manufacture intervening grounded-RCA, approval, or execution states.
- A closure/status retry can repair a legacy lifecycle projection using only the
  matching persisted assessment, report checksum and normalized observations.
  This is idempotent and does not run a corrective action.
- Compact inbox reads preserve the canonical resolution lifecycle through a
  scoped JSON-path read, avoiding full context payloads. Closed rows show closure
  as their current stage while keeping inconclusive analysis visible in history.
- No runbook success is learned from a repair KaiMS did not execute. Linked-ticket
  cases remain gated on their coordinated ticket workflow.

See [the API and operator contract](independent-recovery-observers.md#recovery-after-a-repair-outside-the-executor).


## Final implementation verification

- Full backend suite: **1,169 passed** on the final Python implementation.
- Incident-route unit tests: **10 passed**; TypeScript passed.
- Production UI build and bundle budgets passed; Ruff F checks passed.
- Authenticated live browser verified CLOSED, the independent-recovery caption,
  and Jira Not linked in KaiMS > Incidents > Resolved recently.
- Both closure and lifecycle outbox events reached published status. The exporter
  remained healthy (`mysql_up=1`). All eight affected application services were
  running after deployment.

The existing recommendation remains inconclusive. Technical closure proves the
registered recovery signals for this incident; it does not retroactively prove
the cause or turn the external repair into an approved executor action.


## Follow-up: latest 50 incident batch

The user approved activating the eight recovery profiles limited to 25 demo
incident IDs. The registry and closure service are deployed. **20 demo incidents
closed**, each with 66 passing independent observations across five minutes,
a CLOSED lifecycle projection, and published closure/lifecycle events. The
UI-facing API confirms those closed states.

The selected batch now has **23 closed and 27 open incidents**. Five demo
incidents remain open because new RCA recommendations superseded both their
initial and restarted recovery assessments. The other 22 retain their documented
incident-specific blockers. No approval remains pending for the demo registry.

See [the full batch results and remaining work](latest-50-recovery-batch-2026-09-07.md)
and [durable closure evidence](demo-recovery-closure-proof-2026-09-07.json).

## UI visibility repair verified

The incident queue loaded its own unified feed, but Refresh queue refreshed only
other runtime datasets. Backend closures therefore stayed invisible in an
already-open queue until its filters or route changed. The displayed feed now
refreshes on the queue button, after local closure, every 30 seconds while
visible, and on browser focus/visibility return. Failed refreshes are displayed;
stale responses from a prior filter cannot overwrite the current rows.

The Resolved recently tab now persists `inbox_view=resolved` in the URL. The UI
was rebuilt and deployed. Four new refresh tests plus ten existing incident
route tests passed; TypeScript and the production build/bundle checks passed.

A real authenticated browser confirmed three CLOSED rows in KaiMS > Incidents >
Resolved recently (two exporter recovery rows and one pre-existing administrative
closure). It also confirmed the Robot Shop payment recovery row
`c10d39a5-cd6d-43e2-89ee-741cdbdcd778` under project `robot-shop-payment`.
The refresh button made another successful request to the displayed feed.

Project filters and canonical incident grouping mean the 23 closed raw batch
records are not 23 rows in the KaiMS project list. Select the relevant project
and Resolved recently; reload an existing tab once to load this deployed fix.

- [KaiMS closed rows screenshot](closed-incidents-visible-2026-09-07.png)
- [Robot Shop closed row screenshot](closed-robot-shop-visible-2026-09-07.png)
- [Browser verification](closed-incidents-ui-verification-2026-09-07.json)

## Incident details layout update

The screenshot identified the details page's expanded evidence record list.
Resolution gates now precede the evidence library. The library is collapsed by
default and supports search across all records, category filtering, and eight
records per page; open evidence requirements stay visible. Evidence IDs,
citations, and accepted-for-RCA markers are retained without deduplicating or
promoting attached context into verified evidence. Narrow screens stack the
layout and wrap long references.

Deployed after 12 focused tests, TypeScript validation, and production bundle
checks passed. Browser verification on incident
`55705c30-a2b9-4d69-b0d6-9eb532c1a719` confirmed section order, collapsed defaults,
and no details-container overflow at 980px. Pagination/search tests used a
145-record dataset. The live response during verification supplied zero attached
records, so live pagination could not be verified against that incident's older
145-record snapshot.

[Updated details screenshot](incident-details-compact-2026-09-07.png)

## Closed-history access and compact inbox

The dedicated Closed Incidents page was hidden from navigation. It is now
visible in the sidebar and linked directly from the inbox as Closed incident
history. This tenant-wide history lists each closure separately across projects,
whereas the inbox applies project scope and canonical grouping. A live browser
verified 26 history rows including all 23 closed records in the fixed batch.
None of those 23 incidents has a linked Jira ticket.

The interrupted inbox change is also complete: full blocker text expands on
demand, default rows remain compact, and narrow tables adapt into cards. Live
verification found no horizontal inbox overflow at 1100px. Twenty focused tests,
TypeScript, and the production build/bundle checks passed. Both changes are
deployed.

- [Closed history with batch records](closed-history-visible-2026-09-07.png)
- [Compact inbox](compact-inbox-visible-2026-09-07.png)
- [Browser verification](closed-history-browser-verification-2026-09-07.json)


## KaiMS runtime repair (7 September, afternoon)

Reproduced and deployed three resolution-worker fixes: evidence refresh now
retains the original analysis-request identity; redeliveries reuse an already
committed RCA and retry its downstream handoff; new investigations reserve
unique RCA versions in a durable table before processing. The additive
`20260907_rca_version_reservations.sql` migration was applied with the migration
runner. Immutable binding and independent recovery guards remain enforced.

Dead-letter replay now publishes with broker confirmation before acknowledging
the source delivery; malformed records and failed publications remain queued.
The resolution context dead-letter queue fell from 443 to zero after replay.
This is delivery recovery, not proof that every investigation has completed.
The normal queue continues processing those records. A subsequent check found
34 distinct reserved generations and no duplicate reserved versions.

Removed unused large query payloads from operations-state reads (3.61 seconds
before, 0.40?0.45 seconds after). Reduced repeated JSON extraction and history
reads in compact incident lists; deployed reads measured 0.76, 0.18 and 0.10
seconds. Fifty-eight handoff/reservation/context/replay tests and 37 read-model
contract tests passed. Promtool validated all 64 monitoring rules.

Robot Shop MySQL, RabbitMQ, Redis and Mongo rules now use their own scrape jobs.
The old queue rule incorrectly counted 571 KaiMS messages when Robot Shop had
zero. Corrected the alerts-table description to match its existing 300-row
threshold; the threshold itself was not changed.

Activated six additional recovery profiles restricted to ten named KaiMS
incidents in the fixed batch: gateway latency (four), policy engine (two), and
platform dead letters (four). These require current independent measurements,
original-alert clearance, dependencies, critical-alert clearance and the full
stability window. Gateway checks use actual request latency; platform checks
require no recent dead-letter events and no ready broker backlog. Missing or
failed measurements cannot close an incident. Both policy incidents started
fresh assessments at 07:41 UTC. Four exact gateway alert-family assessments
started at 07:46 UTC after every instant check passed (p95 below one second).
The registry accepts repeated primary-alert keys only for disjoint, explicit
incident batches; execution lookups fail closed when they cannot disambiguate.
Forty-nine observer/assessment tests passed, including overlapping-scope rejection.
Results are recorded separately below.

The fixed batch still contained 23 closed and 27 investigating records when
checked after replay; no previously closed batch record was reopened. MySQL
archiving remains blocked on a retention policy and an executable governed
archive/restore path. The external httpbin /status/503 target remains an actual
failing endpoint and has not been replaced with a successful URL.

- [Scoped KaiMS registry](../../backend/config/recovery-observers.kaims-repair.proposed.json)
- [Policy recovery assessments](kaims-policy-recovery-run-2026-09-07.json)

- [Gateway recovery assessments](kaims-gateway-recovery-run-2026-09-07.json)


### Confirmed closures and remaining automatic work

Two policy incidents and all five previously superseded demo incidents are now
closed with independent proof: the fixed batch increased from 23 to **30/50**.
The first four gateway assessments were falsely labelled superseded by a
persisted-proof rejection, not an actual binding change. Reproduced MySQL JSON
shortening `0.9874999999999999` to `0.9875`, changing the proof hash. Observers now
preserve measured and expected decimal text while still evaluating thresholds
numerically. The exact historical window retains its checksum through MySQL
with the deployed fix. Fifty observer/assessment tests passed.

Four fresh gateway assessments remain pending automatic reconciliation because
the shared critical-alert check saw additional dead letters from expired old
ParaBank snapshots. Their availability, latency, error and dependency checks
pass. Added and tested strict refresh of expired requests against a newer valid
snapshot; collected new context for both affected subjects and retried the four
messages. Original evidence lifetimes were not extended.

Replayed 141 older raw-alert schema failures and one context-event duplicate
after trial replays passed. A bounded local watcher (PID 10348, at launch)
checks the four exact platform incident IDs every 30 seconds, for at most two
hours from 08:03 UTC. It creates server-side recovery assessments only after all
six prerequisites pass, including an empty ready backlog. The server still
requires the complete independent stability window. Registry changes stop the
watcher; failed/superseded terminal results require review.

The remaining policy-dependent or externally failing incidents are four MySQL
row-count alerts, four intentional httpbin `/status/503` incidents and four
ParaBank incidents. The alert table has 3,672 records, all less than three days
old; neither seven-day nor thirty-day retention would reduce it. Its existing
300-row threshold and the retention/archive policy require an operator choice.
No alert records were deleted and no external failure URL was replaced.

- [Current fixed-batch proof](kaims-runtime-repair-proof-2026-09-07.json)
- [Completed demo assessments](demo-recovery-followup-2026-09-07.json)
- [Fresh gateway assessments](kaims-gateway-recovery-confirmation-2026-09-07.json)
- [Platform watcher state](kaims-platform-recovery-watch-2026-09-07.json)
- [Bounded watcher implementation](../../scripts/watch_kaims_platform_recovery.py)


### Retention choice and current KaiMS recovery (14:15 IST update)

Selected 30 days for unlinked raw alerts. Incident, occurrence, event, analysis,
investigation-binding and context-snapshot references prevent removal. Archived
copies are retained at least 365 days; automatic archive deletion is disabled.
The reversible archive tool defaults to dry-run and validates a full-record
checksum before restoration. Eleven offline safety tests pass. The deployed
image dry-run found **zero eligible alerts**: today's row-count warning cannot
be fixed by deleting old data because all current records are recent.

Changed the capacity warning from 300 to 100,000 rows, allowing headroom above
30 days of the observed roughly 1,000 alerts/day. This is an operational warning,
not a measured MySQL storage limit. The table currently occupies about 62 MB.
All 64 Prometheus rules validated and the updated rules were reloaded.

Automatic approval review rejected wiring daily destructive archival into the
monitoring service because choosing retention did not authorize ongoing deletion.
No recurring archival worker was enabled and no production alert rows were deleted.
The prepared tool requires explicit `--execute`; its archive-and-remove action
still needs operator approval before scheduling.

The current recovery selection contains 99 exact open KaiMS incident IDs across
API gateway (43), dead letters (32), MySQL (19), policy engine (4), and the resolution
worker (1). Nine exact-family profiles replace the earlier limited KaiMS cohort;
other reviewed application profiles remain present. Old watcher scope is obsolete
and stops on the registry change. Each new assessment requires independent
measurements over its complete stability window. No corrective execution is
invented and no closed state is set directly.

- [Retention policy](../../backend/config/alert-retention.json)
- [Archive and restore tool](../../scripts/manage_alert_retention.py)
- [Fixed current selection](kaims-current-recovery-cohort-2026-09-07.json)
- [Current assessment results](kaims-current-recovery-run-2026-09-07.json)


At 14:15 IST all 19 current MySQL assessments reached **closed**, including
`efe55195-6b42-40cb-a19b-b1cf1f2cd12c` from the screenshot. Browser verification
found all 19 records in Closed Incidents (52 total records at that check), with
no inbox overflow at 1100px. Fixed the closed-history route to use the shared
UTC-aware IST formatter; naive stored UTC dates previously displayed 5.5 hours
earlier while labelled IST. UI build and bundle checks passed and were deployed.

The final stale Robot Shop context message was retried after the competing
backlog drained. All broker queues then had zero ready and unacknowledged
messages. The recent-dead-letter alert cleared and all other 80 current KaiMS
assessments started between 08:45:03 and 08:45:56 UTC, each requiring at least
360 seconds before closure.

Retention passed an additional real-MySQL test using **connection-local temporary
tables only**: six reference paths, fresh records and other tenants were protected;
one synthetic unlinked old alert was archived and restored. Nine synthetic source
records were present after restoration. No production data was deleted.


### Confirmed current KaiMS outcome (14:30 IST)

**All 99 selected KaiMS incidents are now closed with persisted independent
recovery proof**: 43 gateway, 32 dead-letter, 19 MySQL, four policy-engine and
one resolution-worker incidents. Browser verification found all 99 in Closed
Incidents, and a newly closed incident's guided detail page displayed Recovered.
The original fixed 50-ticket batch is now **42 closed / eight still open**.
Those eight are four deliberate httpbin 503 failures and four ParaBank latency
incidents; ParaBank currently responds but its approximately 0.31-second probe
still exceeds the original 0.2-second latency threshold. Availability alone
cannot close those latency incidents.

The gateway briefly failed its first observation window. Read-only profiling
identified repeated JSON extraction in compact 100-record lists; removed
unnecessary string-conversion extraction and nested lifecycle extraction.
The standard histogram's 1-to-2.5-second bucket also interpolated a single
1.1-second request as p95=2.425 seconds. Added boundaries at the existing 1.5,
2 and 3-second alert thresholds; no alert threshold was raised. After deployment,
three 100-record gateway reads measured 1.219, 1.054 and 0.838 seconds. Later
complete windows passed and all 43 gateway incidents closed.

Validation: 61 recovery/retention tests, seven canonical/bucket tests, and 61
compact-list/persistence/event tests passed, plus the isolated MySQL retention
integration and live browser checks. Two additional external profiles cover
only the two displayed GitHub Status incidents and one OpenTelemetry incident.
They require original-target 2xx responses, all linked alerts clear, no recent
probe failures, the existing 200ms latency boundary, observed DNS/HTTPS/certificate
health, and critical-alert clearance. These checks concern the monitored external
endpoint, not unobserved internal application dependencies. GitHub's recent
intermittent probe failure currently prevents starting its assessments.

- [99 confirmed recovery results](kaims-current-recovery-run-2026-09-07.json)
- [Browser verification](current-kaims-closures-browser-2026-09-07.json)
- [Closed detail verification](current-kaims-closed-details-2026-09-07.json)
- [External recovery results](external-recovered-run-2026-09-07.json)


### Closed-history completeness and external follow-up

Removed the silent 120-record cutoff from the history flow by adding bounded
API pagination and a **Load older closures** control. Ordering uses closure time
and incident ID to handle timestamp ties. Tenant filtering and the closed/resolved
status filter apply to every page. Empty authoritative history no longer falls
back to failed incident attempts. Refresh and failed page fetches preserve useful
state, and appended pages deduplicate incident IDs.

Sixteen persistence/history tests passed (including tenant-safe pagination with
identical closure times), TypeScript passed, and UI build/bundle checks passed.
The deployed browser loaded **133 closures over two pages**, including all 99
current KaiMS results and the older records hidden by the previous cutoff.
OpenTelemetry incident `ac38a842-83cd-4a3b-baea-10888b611dc4` also completed its
independent stability window and closed. GitHub's two assessments started after
its clean-probe prerequisite passed and remain under full-window verification.


Final check: **100 new confirmed closures** (99 selected KaiMS plus OpenTelemetry).
All 100 have matching closed incident projections. Both GitHub assessments are
blocked by an observed sample above their unchanged 200ms latency requirement;
the server can continue evaluating later clean windows until their assessment
expiry. Their successful HTTP response alone is insufficient. Automatic retention
remains disabled pending explicit approval; the policy and tested reversible
archive tool are ready, and the production dry-run found no eligible records.
See [the final verified counts](current-kaims-recovery-final-proof-2026-09-07.json).


### Detail-page correction after contradictory OpenTelemetry screenshot

The screenshot exposed a real command-workspace defect. Observed-recovery
reports were excluded because the operations read model required an approved
execution lineage; consequently a closed incident still showed validation not
started. The closed lifecycle also retained a historical human-evidence next
action. The earlier browser check merely found the word Recovered in the journey,
which is present even for open incidents; it did not prove the page was coherent.

The operations read now selects the exact report named by the committed recovery
assessment, checks tenant/incident/assessment/checksum lineage, and returns its
independent observations without fabricating an execution. Closed next-actions
point to closure review. The cockpit leads with recovery proof, six sampled
checks and provenance. Earlier RCA and evidence are collapsed as historical;
obsolete resolution, human-evidence, claim-amendment and manual-close controls
are removed after closure. Observed recovery has four honest milestones rather
than marking RCA and execution complete. Closures without technical proof are
not labelled Recovered. Timestamps use the UTC-aware IST formatter; detail data
refreshes every 30 seconds and on focus.

Validation: 29 lifecycle tests passed, including invalid report lineage cases;
TypeScript and UI build/bundle checks passed. The exact screenshot incident
`ac38a842-83cd-4a3b-baea-10888b611dc4` passed browser assertions for six checks,
collapsed history, no obsolete controls, no execution milestone and focus refresh.
See [browser assertions](opentelemetry-corrected-recovery-page-2026-09-07.json).


### Platform detail follow-up and stale-tab detection

Verified the user's exact URL:
`http://localhost:8501/incidents/4b1bcd2f-04b4-42ff-82d8-4f35bdc5a10a`.
A fresh browser showed six independently verified recovery checks; the supplied
screenshot retained the older component layout. Expanded the recovery panel with
the recorded observation span, operator note, target/observer identities and
expandable timestamped sample tables. All details come from the persisted report.

Added a global update notice comparing the loaded module entry with uncached
index HTML on focus and every minute. A newer build offers a reload button;
it never reloads automatically or discards drafts. Tabs predating this notice
need one full reload to receive it.

TypeScript, production build and bundle checks passed. Browser verification of
the exact platform incident passed: six checks, 11 visible samples in an expanded
check, collapsed historical investigation, no obsolete execution/evidence controls,
four observed-recovery milestones and focus refresh. A simulated newer index
produced the update notice without an automatic reload.


### Incident endpoint 503: cancelled event streams (2026-09-07)

The user reported `database_temporarily_unavailable` while opening incident
`4b1bcd2f-04b4-42ff-82d8-4f35bdc5a10a`. MySQL was healthy (65 connected,
3 running, maximum 450). Gateway logs showed AnyIO cancellation during aiomysql
connection termination, unreturned connections, and subsequent CircuitOpenError.
SQLAlchemy marks cancelled operations as disconnects; the database breaker counted
these as database outages. The supplied trace ID was not independently correlated.

The database breaker now excludes asyncio cancellation while retaining genuine
connection-failure protection. Event-stream polling shields its finite database
work and session cleanup from request cancellation, has a separate ten-second
deadline, selects notification columns only, and closes cleanly on dependency
failure after streaming headers have already been sent. The gateway image was
rebuilt and deployed; MySQL was not restarted.

Validation: six regression cases passed, including cancelled disconnect versus
real disconnect, AnyIO cancellation with completed session cleanup, and both
outage and deadline handling after stream headers. Forty live SSE disconnects
interleaved with ten requests to this exact incident command endpoint produced
ten HTTP 200 responses. Browser verification at localhost:8501 confirmed six
recovery checks, the recorded sample table, the observed-recovery journey ending
in Closed, and collapsed historical investigation. Post-deployment gateway logs
contained no connection-GC warnings, termination errors, CircuitOpenError, or
response-already-started errors during this verification window.
