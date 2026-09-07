# Local KaiMS recovery observer activation ? 2026-09-07

## Activated scope

The user selected KaiMS. The local Docker Compose project `kaims` now uses
`backend/config/recovery-observers.json`. The example registry is unchanged.

Twenty exact profiles cover `KaiOpsServiceDown` and `ServiceDown` for these ten
Prometheus job identities: `kaiops-api-gateway`, `kaiops-monitoring-adapter`,
`kaiops-alert-intelligence`, `kaiops-orchestrator`, `kaiops-context-agent`,
`kaiops-model-router`, `kaiops-resolution-agent`, `kaiops-approval-service`,
`kaiops-remediation-engine`, and `kaiops-closure-service`.

Profiles use tenant `default` and alert environment `prod`, matching the local
monitoring adapter's normalization of these alerts. This is a local deployment:
`AUTH_MODE=local` and `DEPLOYMENT_PROFILE=cloud-neutral` authorize the existing
local tenant identity. `prod` here is the incident label, not evidence that a
production deployment was configured. These profiles must not be reused for
another tenant or Prometheus installation.

Each profile requires six independently collected checks:

- HTTP health endpoint probe success and the actual service metrics scrape.
- Original alert clearance and the underlying scrape recovery.
- Zero synthetic health endpoint failures.
- Synthetic health endpoint duration at most 1.5 seconds.
- TCP probes to MySQL, RabbitMQ, and Redis, plus the MySQL exporter's authenticated connection check. All three TCP series must exist.
- No critical alerts for the service or core MySQL, message-bus, and workflow components.

The error and latency checks measure health endpoint probes. They do not measure
business request errors or business operation latency. Accordingly these profiles
cover service-down incidents only, not application error/latency incidents,
Fault Lab, or Online Boutique. Unregistered mutating plans remain blocked.

Prometheus scrapes every 15 seconds. The observer samples every 30 seconds,
requires eleven samples spanning 300 seconds, and allows a 120-second grace
period. Missing samples cannot pass. No alerts is explicitly zero only for
alert counts; availability and dependency checks remain required.

## Deployment

Added `observability/recovery-kaims-http-targets.json`, two scrape jobs in
`observability/prometheus.yml`, and a read-only target-file mount in Compose.
The existing Blackbox exporter probes the ten service health endpoints and the
three core dependency ports. No faults were injected.

The local `.env` now sets `RECOVERY_OBSERVER_REGISTRY_PATH` to the actual registry
and `RECOVERY_OBSERVATION_GRACE_SECONDS=120`. Existing credentials were preserved.
The registry is baked into rebuilt service images. Recreated closure-service,
resolution-agent, orchestrator, monitoring-adapter, monitoring-ingestion-worker,
remediation-engine, approval-service, temporal-pilot-worker, and Prometheus.

All plan producers and closure use the same registry path. Changing the registry
requires rebuilding these images and generating new plans. Already-approved
plans are not rewritten, and no incident was manually approved or executed.

For an offline check using the same local identity policy in PowerShell:

```powershell
$env:AUTH_MODE = 'local'
$env:DEPLOYMENT_PROFILE = 'cloud-neutral'
.\.venv\Scripts\python.exe scripts/check_recovery_observers.py backend/config/recovery-observers.json
```

## Initial activation verification

- Promtool accepted the configuration and all 64 existing rules. Its only warning was the already-empty generated-target wildcard.
- Registry validation: one source, twenty profiles, 120 validators.
- All ten independent service probes returned success. All redeployed services were running, with configured Docker health checks healthy and other service health endpoints returning HTTP 200.
- Unsaved plan compilation inside resolution-agent for all twenty supported profiles bound the exact registered validator specs and reported no readiness blocks. This did not submit an incident or execute a plan.
- The 47 focused runtime-observer and closure-handoff tests passed.
- Live query evaluation returned one numeric series for every distinct query. The deployed adapter subsequently collected all 120 checks with eleven samples each spanning 300 seconds; none were unavailable. Eighty checks passed. The remaining forty checks (dependency health and critical alerts in each profile) correctly failed. Health, alert-clearance, synthetic error and latency checks passed.
- `mysql_up` was zero: the configured `mysql_exporter` account did not exist and the exporter had no password. This is a monitor authentication failure; it does not prove MySQL itself is down.
- `KaiOpsDeadLettersIncreasing` was firing from a recent resolution-agent `handler_failed` event. Recreated resolution-agent logs did not show a new corresponding error. The observer will require the critical alert to clear before closure.

Live end-to-end incident closure has not been demonstrated. The observer runtime
and its monitoring probes are active, but these measured blockers prevent a
recovery pass. [The live preflight artifact](recovery-observers-local-preflight-2026-09-07.json) records collection results separately
from incident validation; it is not execution or closure evidence.

## Approved repair and current status

The user subsequently approved the monitoring-account change. Created
`mysql_exporter` limited to host mask `172.19.0.0/255.255.0.0`, with a maximum
of three connections. Verified grants are PROCESS and REPLICATION CLIENT on
`*.*`, plus SELECT on `performance_schema.*`. No application-table SELECT or
write privileges were granted. A generated password is stored in the local
`.env`; it is not recorded in this report. Recreated only mysql-exporter for
this repair. Both its direct metrics and Prometheus now report `mysql_up = 1`.

The recent resolution-agent failure was traced to a mismatch between its
configurable source corroboration policy and the evidence-bound claim contract.
A hypothesis could be marked confirmed with one supporting item, then crash
when converted into a GROUNDED claim requiring two distinct items. The shared
investigation stopping check now also requires two distinct, nonempty support
IDs and no unresolved contradictions. Insufficient causal corroboration is
reported separately from missing telemetry planes, yields INSUFFICIENT_EVIDENCE,
and keeps the causal claim a HYPOTHESIS. The configurable source-diversity policy
is preserved. Regression coverage includes a single item, duplicate references,
and two distinct items. All 61 investigation/contract tests passed, as did the
F-class Ruff checks. Rebuilt and redeployed resolution-agent; its HTTP and Docker
health checks passed.

[The repair verification artifact](recovery-observers-local-repair-2026-09-07.json)
records the latest current measurements: 100 of 120 checks passed. The twenty
critical-alert checks still detect the dead-letter alert, which re-fired while
recent pre-fix handler failures remained in its ten-minute lookback. All other
checks, including authenticated dependency health, pass. An earlier instantaneous
check briefly showed all 120 passing before that alert re-fired; it is not the
final state. A healthy full stability window and critical-alert clearance are
still required before recovery can pass. This repair did not replay dead-letter
messages, approve or execute incident plans, or manually close incidents.

If the alert persists beyond the lookback window, inspect new resolution-agent
handler failures. Existing queued failures require normal reviewed recovery;
do not clear queues or silence alerts to make closure checks pass. Live
end-to-end incident closure has not been demonstrated by this work.
