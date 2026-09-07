# Independent recovery observations

The runtime collector now lives in `closure_service/observations.py`. Closure
queries an operator-managed Prometheus source independently of the executor.
It does not accept the executor's recovery assertions as observation evidence.

## Implementation choices

| Approach | Fit | Status |
| --- | --- | --- |
| Pull approved Prometheus queries from closure | Existing monitoring stack; historical windows survive process restarts | Implemented |
| Add HTTP/synthetic probe adapters to the same observation contract | Business transactions and endpoint checks not represented in metrics | Future extension; requires a registered probe definition |
| Add APM-specific read adapters | Services whose authoritative signals live in another monitoring platform | Future extension; requires scoped source credentials and result normalization |

No new service, Temporal workflow, or database migration is required for the
Prometheus path. The closure service's existing reconciliation loop polls
durable successful actions, including actions without executor recovery proof.
Pending validation is retried; terminal validation outcomes and superseded
attempts are excluded. Missing broker delivery or a closure restart does not
discard the observation window: Prometheus is queried again for recent history.

## Register and enable checks

1. Copy `backend/config/recovery-observers.example.json` to a reviewed deployment
   file, such as `backend/config/recovery-observers.json`. The example is not an
   approved production configuration: its tenant, service, labels, metrics,
   dependencies, thresholds, and triggering alert must match the target system.
2. Register the actual Prometheus endpoint and optionally `bearer_token_env`.
   This names an environment variable containing the token; do not put the
   token in the registry. Make that variable available to closure-service.
3. Register a profile for the exact tenant, environment, target resource ID,
   and triggering alert name. Each profile must contain availability, original
   alert clearance, error rate, latency, dependency health, and critical-alert
   checks. Additional supported validation kinds can be added.
4. Each approved PromQL query must aggregate to exactly one numeric series.
   Scope queries to the profile's tenant and target. The alert-clearance query
   must name the original alert. Verify metric labels, scrape cadence, query
   lookback periods, no-traffic behavior, and thresholds against the service's
   actual recovery criteria.
5. After editing queries, print their expected references for review:
   `python scripts/check_recovery_observers.py backend/config/recovery-observers.json --query-references`.
   Update each spec's `check_reference` to the corresponding hash. Then run:
   `python scripts/check_recovery_observers.py backend/config/recovery-observers.json`.
   The tool never rewrites the configuration.
6. Set `RECOVERY_OBSERVER_REGISTRY_PATH=backend/config/recovery-observers.json`
   consistently for plan-producing services and closure-service. Docker Compose
   now forwards this variable through its shared service environment. Files
   under `backend/config` are included by the existing service Dockerfile;
   rebuild/redeploy services after changing a baked-in registry, or mount the
   reviewed file read-only at the same configured path.
7. Regenerate and approve execution plans after registration or query/threshold
   changes. The plan includes the exact registered validator specs in its
   fingerprint. An in-flight plan that no longer matches the registry fails
   closed; the collector does not silently modify its approved plan.

An empty registry-path setting preserves the existing legacy behavior and
does not enable live collection. Once configured, unmatched profiles block
new mutating plans. An invalid configured registry fails closure startup.

## Runtime behavior

The adapter uses the documented Prometheus range-query API with a bounded
timeout, query step, lookback interval, and series limit. It disables redirects
and reads URLs only from operator configuration. Queries and endpoints supplied
in action payloads are not used as executable observer configuration.
See the [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries).

Collection replaces caller-provided observation and registry snapshots with
the matching registered checks and fresh query results. Every observation
records execution ID, plan fingerprint, validator, connector, target, timestamp,
measured value, expected value, comparison result, and a content checksum.

The result must contain one finite numeric value at every requested step.
Empty results, multiple series, gaps, unexpected timestamps, warnings, HTTP
errors, redirects, and missing credentials cannot establish recovery.
No-data is never treated as a passing zero; explicit zero-on-no-alert queries
must be paired with the required availability and other recovery signals.

The first query evaluation occurs after execution completion plus a full
lookback step. Recovery requires the plan's full stability window and each
validator's minimum sample count. Initial warmup and transient unavailability
remain `pending_stability`, without claiming that independent checks passed.
An actual failed measurement produces validation failure. Unavailability beyond
the observation window plus `RECOVERY_OBSERVATION_GRACE_SECONDS` (default 120)
also produces failure and leaves closure unauthorized. Polling cadence is
`CLOSURE_RECONCILIATION_INTERVAL_SECONDS` (default 15); automatic polling
requires `CLOSURE_RECONCILIATION_MODE=apply`.

## Verification

`backend/tests/test_recovery_observer_runtime.py` covers registry integrity,
plan compilation, independent measurements, sample gaps and staleness, warmup,
outage deadlines, executor-evidence replacement, and restart reconciliation.
A real local HTTP server test exercises transport and SQLite persistence from
pending stability to closed, then verifies that terminal work is not polled.

These tests do not validate a production Prometheus deployment or its queries.
The local KaiMS deployment is now configured separately as described in
[the activation report](recovery-observers-local-activation-2026-09-07.md).
Incident execution and approval remain gated by the normal workflow. The separate
operator-authorized observed-recovery path below is now verified live for the
local MySQL exporter incident.


## Recovery after a repair outside the executor

`allow_operator_verified_closure` defaults to false. An operator-reviewed profile
can opt in for one exact tenant, environment, service and alert family. The local
registry enables it only for `MySQLExporterDatabaseConnectionFailed` on
`mysql-exporter`. This is a separate observed-recovery assessment; it does not
approve the existing remediation plan or change an inconclusive RCA to grounded.

An authenticated ADMIN or HITL_APPROVER starts the assessment through the gateway:

```http
POST /incidents/{incident_id}/recovery-assessments
Authorization: Bearer <operator access token>
Content-Type: application/json

{"comment":"Describe the repair completed outside the KaiMS executor."}
```

The server derives identity and tenant from authentication. Client-supplied
identity, evidence, queries, timestamps and profiles are rejected. The closure
service separately requires the internal service token and the authorized role.
The response supplies `assessment_id`, `requested_at`, `expires_at`,
`minimum_wait_seconds`, and `status=pending_stability`.

The existing closure reconciliation loop resumes persisted requests after a
restart and evaluates them every reconciliation interval in apply mode. For an
explicit evaluation or status check, use the same authenticated gateway:

```http
POST /incidents/{incident_id}/recovery-assessments/{assessment_id}/evaluate
Authorization: Bearer <operator access token>
Content-Type: application/json

{}
```

A complete passing window closes automatically. Missing, unhealthy, or incomplete
data never closes the incident. A request expires after one hour; a later healthy
full window may pass before expiry. The incident remains open during observation.
Linked-ticket incidents and incidents with unfinished execution or approval work
are not eligible for this path. Changed alert membership, recommendation,
lifecycle, execution work, or observer registration invalidates the assessment;
request a new assessment after reviewing the change.

Closure rechecks these bindings under the incident lock, then commits the audit
outcome, report, 66 normalized observations for the local profile, incident and
projection, and durable outbox event together. Samples bind `assessment_id` and
`profile_digest`, with phase `post_assessment`; they never claim an execution ID.
Reports use `closure_kind=observed_recovery`, `technical_recovery_verified=true`,
and `corrective_execution_performed=false`. No remediation action or successful
runbook attribution is created. The board explicitly identifies independently
verified recovery and a repair outside the executor.

This path verifies the registered recovery signals, not causal proof or every
application SLO. In the exporter profile, the error signal is the sampled database
connection-failure indicator and latency is exporter scrape duration. The other
checks cover scrape/authenticated availability, originating-alert clearance,
database TCP and uptime, and critical alerts scoped to the exporter/database.


## Runtime support for incident-limited and multi-alert assessments

The checkout now supports `required_alert_labels` (exact values),
`additional_alert_names` (an exact family set), and
`operator_verified_incident_ids` (an optional UUID allowlist). When an allowlist
is supplied, any missing or different incident ID is rejected. Unknown alert
families, partial family sets, mismatched target labels, and ambiguous profile
matches are rejected. These fields do not enable closure by themselves.

The [demo batch proposal](../../backend/config/recovery-observers.demo-batch.proposed.json)
was explicitly approved by the user and copied to the active runtime registry.
Its eight profiles are limited to the 25 listed incident IDs. The closure service
was rebuilt and deployed with this support. All 25 fresh assessments were
accepted. The source changes are covered by 48 passing focused tests.

Approved runtime result: 20 of the 25 demo incidents closed with full persisted
recovery proof. Five remained open after two superseded attempts each because
RCA recommendations changed during observation. See the [batch report](latest-50-recovery-batch-2026-09-07.md).
