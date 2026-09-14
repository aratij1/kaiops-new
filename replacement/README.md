# KaiMS replacement - incident pipeline preview

Status: running local replacement preview on port 8502, not a production cutover. RabbitMQ remains the pipeline transport. The full rewrite scope is tracked in PIPELINE.md.

## Implemented and verified

- Authenticated single-tenant onboarding API. Registration and its discovery request commit atomically, even while the broker is down.
- Scoped discovery of configured UTF-8 Markdown, text and JSON documents, with size/count limits and separate collected/empty/missing/failed/partial source outcomes. Reference documents never acquire invented observation timestamps.
- Discovery -> context -> ready/blocked progression. Context messages carry immutable artifact references. An incomplete required document source blocks baseline readiness explicitly.
- Incident admission validates registered service membership and a timezone-aware window of at most 24 hours. Admission waits durably for the baseline notification; both already waiting and subsequently admitted incidents are handled. Blocked context is explicit.
- Parallel, bounded HTTP collection from server-configured normalized telemetry endpoints. Freshness and service checks reject stale, undated, unrelated and ingestion-artifact records. Outcomes distinguish collected, partial, no matches, unconfigured, failed and timed out.
- Independent deterministic RCA and impact assessment. Measured error ratios establish observed service errors; dependency failures remain hypotheses. Customer/business impact and a confirmed cause are never inferred from those signals alone. Resolution remains blocked pending verification and approval.
- Durable inbox/outbox, duplicate protection, application-scoped artifact access, publisher confirmations and mandatory routing.
- Three-attempt stage budget, timeout, persisted exhausted-stage failure and confirmed quarantine before acknowledgment. Retries are durably queued and forwarded with publisher confirmation to only the original consumer.
- 72 passing local tests. The real broker test passes onboarding through actual test-file discovery to context readiness, unroutable publication, duplicate redelivery, confirmed retry relay, sibling isolation and quarantine. It also releases a waiting incident, collects timestamped telemetry over a real local HTTP fixture endpoint, and completes separate RCA/impact assessments. It uses synthetic data in isolated queues; it does not prove live RCA accuracy.

## Run locally

Set NEXT_API_TOKEN (random, at least 32 characters), NEXT_TENANT_ID, NEXT_RABBITMQ_URL and NEXT_DOCUMENT_ROOTS_FILE. The roots file maps connector root names to absolute allowed directories. NEXT_DATABASE_URL defaults to an isolated SQLite file; MySQL is supported by the handoff core but this preview has not been concurrency-qualified on MySQL. Do not point it at the legacy schema.

```powershell
$env:PYTHONPATH = (Resolve-Path replacement).Path
.venv\Scripts\python.exe -m uvicorn kaims_next.runtime:create_app --factory --host 127.0.0.1 --port 8502
```

Alternatively, set NEXT_API_TOKEN, NEXT_TENANT_ID, NEXT_BROKER_PASSWORD (URL-safe) and NEXT_DOCUMENT_DIRECTORY, then run:

```powershell
docker compose -f replacement/compose.yaml up -d --build
```

The optional Compose preview is a separate project with its own broker/state and loopback-only API port. It is now deployed locally. It does not modify the legacy database or queues.

Send a Bearer-authenticated POST /applications:

```json
{"application_id":"payments","services":["gateway"],"telemetry_sources":["metrics"],"document_sources":[{"id":"runbooks","root":"application-documents","path":".","required":true}]}
```

GET /applications/payments returns authoritative onboarding state. GET /healthz distinguishes API availability from broker readiness and reports whether a configured resolution policy is available. The single server-configured tenant is a development boundary, not the finished multi-user authorization system.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest replacement/tests -q
.venv\Scripts\python.exe replacement/tests/verify_rabbitmq.py
```

The broker test uses the existing gateway container only as a test runner and deletes its uniquely named test queues/exchanges. Results are in rabbitmq-verification.json.

## Remaining rewrite work

Production document services (Git/cloud/wiki/PDF parsers), document change refresh, versioned onboarding updates, full-text retrieval, Tempo trace support, causal RCA/model evaluation, approvals/remediation, verification, production UI rollout, full authorization and migration remain unfinished. Incident admission, normalized HTTP collection, native Prometheus raw samples, native Loki streams and native Jaeger spans are implemented. Native Tempo traces and production connector rollout remain unfinished. No remediation or model calls are enabled by this preview.

A complete live incident evaluation against controlled fault truth remains a cutover requirement. Existing unresolved incidents are not repaired by these isolated changes.

For retry transport design, traditional broker dead-letter forwarding is not assumed lossless; the explicit relay confirms the next publish before acknowledging. See https://www.rabbitmq.com/docs/3.13/dlx for the broker's dead-letter safety limitations.

## Incident collection configuration

Set NEXT_TELEMETRY_SOURCES_FILE to a server-owned JSON file. Its keys are source IDs selected at application registration. Values contain `url` and optional `headers`; keep credentials outside Git. Clients cannot supply endpoint URLs or request headers. The endpoint must enforce the server's tenant boundary; this preview is single tenant.

```json
{"metrics":{"url":"http://telemetry-adapter:8080/records"}}
```

The optional Compose file mounts the empty `telemetry-sources.example.json` by default. Set NEXT_TELEMETRY_CONFIG_PATH to a server-owned file outside the repository for real endpoint configuration. Configure it before onboarding; changed application registration currently requires a future versioned-update implementation.

Collectors send GET query parameters `service`, `window_start`, `window_end`. The normalized response is `{"records":[...]}`. Limits are 8 seconds per source, four concurrent sources, 2 MiB and 2,000 records per source. Redirects are disabled. Supported records require service, timezone-aware observed_at, kind and source_uri. Metrics also require metric (error_rate_ratio in [0,1], latency_p99_ms or request_count) and nonnegative value; logs require message; traces require trace_id and span_id, with optional peer_service, parent_span_id and boolean error. These endpoint adapters are trusted instrumentation, not user assertions of truth. Documentation is retained separately as baseline references.

```json
{"records":[{"service":"gateway","observed_at":"2026-09-01T10:05:00Z","kind":"metric","source_uri":"metric://example/error-rate","metric":"error_rate_ratio","value":0.15}]}
```

POST `/applications/payments/incidents` with Bearer authorization:

```json
{"incident_id":"example-incident","service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:10:00Z"}
```

GET `/applications/payments/incidents/example-incident` returns authoritative state, baseline reference and the latest stage result. GET `/applications/payments/artifacts/{artifact_id}` retrieves scoped evidence or baseline details for inspection. Reusing an incident ID with different input is rejected. Collection results advance to assessment even when all sources are empty or fail; this produces explicit insufficient evidence instead of endless collecting. A stage that exhausts retries persists `failed` before quarantine. No model or remediation calls are made.

## Native Prometheus and Loki collection

The server-owned endpoint map also accepts `type: prometheus` and `type: loki`. See `telemetry-sources.native.example.json` for illustrative configuration; it is not enabled automatically. URLs are service base URLs, including any proxy prefix. Authentication headers remain server-owned. Equality labels such as application and environment must be configured to prevent mixing services with the same name across applications/environments. The application chooses source IDs, not query text.

Prometheus requires a raw `metric_name` and its declared meaning (`metric`). The metric must already express error ratio, p99 latency or a request counter; the adapter does not assume arbitrary latency is p99 or turn a counter into a rate. `multiplier` explicitly converts units, such as seconds to milliseconds. `service_label` defaults to service_name; returned samples must carry that exact label and value plus every configured scope label. Missing service labels are rejected, never filled from the request. Original series labels remain attached to evidence.

The adapter uses an instant range-vector query ending at the incident window end, then checks each raw sample timestamp against the incident window. This avoids treating the evaluation timestamps of query_range as original observations. General PromQL expressions and histogram-derived p99 calculations are deliberately outside this adapter; instrument or configure a properly scoped gauge/recording rule first. Recorded sample time is not proof of causality. Request counters are cumulative readings, not the number of requests inside the incident window.

Loki uses query_range with an exact service selector, configured scope labels, nanosecond bounds, forward order and a bounded limit. Original stream labels and nanosecond identity remain attributable. Filename/path labels pointing at landing or ingested_alerts are rejected as alert-ingestion artifacts. Reaching the limit produces partial collection; pagination is not implemented. A source query warning is also reported as partial, not complete coverage.

Protocol references: [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/) and [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/).

Prometheus/Loki phase verification: 53 automated tests passed; the real RabbitMQ test includes native Prometheus and Loki HTTP fixtures. `tests/verify_prometheus.py` additionally collected 512 real raw request-counter samples from local Prometheus using the actual telemetry-monitoring job label, with no rejects. Its latest report is `prometheus-verification.json`. This infrastructure adapter check does not establish application impact or RCA. No running Loki container was available, so its verification remains fixture-based. The gateway request metric inspected locally had application/environment labels but no service label; a service-specific mapping cannot safely use it until instrumentation or an explicit server-side mapping supplies valid service identity.

## Native Jaeger trace collection

Set a source to `{"type":"jaeger","url":"http://jaeger:16686","tags":{"environment":"prod"}}`. Use actual process/span scope tags for the application and environment; a shared service name alone is not sufficient to isolate multiple deployments. Scope tags are checked again on returned target-service spans, including conflicts between span and process tags. Do not invent missing labels. The example file contains illustrative application/environment tags and is not enabled automatically.

This adapter uses Jaeger's HTTP JSON Query API and was checked against the running `jaegertracing/all-in-one:1.62.0`. Jaeger calls this an internal, version-sensitive API; the stable gRPC API remains a future migration option. See [Jaeger API documentation](https://www.jaegertracing.io/docs/1.76/architecture/apis/). The adapter rejects unsupported response shapes rather than guessing their meaning.

GET /api/traces uses the incident service and microsecond time window, with at most 20 traces. The shared 8-second, 2-MiB and 2,000-span limits still apply. Trace limits and query/span warnings produce partial outcomes. No pagination is implemented. Full returned traces may contain other services; those spans are excluded without relabelling them. Accepted spans must start inside the incident window. Duration and operation are retained, along with trace/span IDs, CHILD_OF parent references, explicit error status and peer.service when present. A network hostname is not inferred to be a dependency service.

The assessment exposes parent-child relationships only for unambiguous same-source/same-trace spans. Self-links, cyclic ancestry, ambiguous duplicates and child timestamps preceding the parent do not produce relationship evidence. Missing parents remain missing. These are observed execution relationships, not a verified causal chain. Related failed spans and peer.service can support hypotheses; they cannot automatically establish customer/business impact or authorize remediation. Cross-service dependency corroboration and root-cause qualification remain unfinished.

Current validation: **66 tests passed**. The real RabbitMQ test now carries a native Jaeger fixture through incident collection and assessment, preserving the parent-child link and the dependency hypothesis while keeping confirmed_cause empty. A separate read-only local Jaeger check accepted **80 api-gateway spans**, found **60 relationships**, and reported partial coverage because it reached the 20-trace limit. No trace contents were written to the verification report. Run `.venv\Scripts\python.exe replacement/tests/verify_jaeger.py` to repeat the live check; counts depend on current traffic. Results are in `jaeger-verification.json` and `rabbitmq-verification.json`.

These changes are still isolated from the legacy application. There is no production cutover, automatic remediation, remote model call or claim of qualified RCA in this phase.

## Investigation workspace UI

The same preview server now serves the investigation workspace at `/` (normally http://127.0.0.1:8502 after starting the preview). Static assets ship inside the existing API image; there is no extra frontend build or runtime dependency. The isolated preview is running locally on port 8502; the legacy application has not been replaced.

Connect using NEXT_API_TOKEN. The token stays in tab memory, is not written to browser storage, and is cleared on disconnect/reload. Application, incident, source-catalog and artifact API reads require authentication and remain scoped to NEXT_TENANT_ID. Source catalog responses contain configured root names and source IDs/types, never endpoint URLs, filesystem paths or authentication headers. Configure the server's real roots and telemetry map before onboarding.

The UI supports application onboarding with a required document root, service registration and telemetry selection; incident submission with local-time inputs converted to UTC; separate impact, RCA and resolution outcomes; source status/failure details; document baseline inspection and discovered document viewing; paginated evidence cards with optional raw records. Configured resolution plans expose approval/rejection, execution status and recovery observations.

Application/incident list reads use bounded keyset pagination and do not load evidence payloads. Active investigations refresh every eight seconds; terminal outcomes stop polling. Evidence artifacts load on request. Failed refreshes preserve the last displayed result with an explicit stale-data message. Switching incidents clears the old evidence view. The API can omit collection records with `include_evidence=false`, which is what the UI polls. A document reference or an error log is never displayed as a confirmed root cause by default.

Verification: 66 backend tests passed, including authentication, list bounds/pagination and catalog shape. `node replacement/tests/verify_ui.cjs` passed in Chromium against the real preview API and isolated SQLite fixtures. It exercised onboarding, incident submission, assessment/evidence rendering, malicious evidence text, tenant separation, credential omission, mobile overflow, disconnect and stale-data handling. RabbitMQ is mocked in that browser fixture; the separate `verify_rabbitmq.py` check covers real transport. Screenshot: `ui-verification.png`; report: `ui-verification.json`. The test server and browser terminate after verification. No live application incident was modified.

A disposable service has now completed controlled failure diagnosis, governed execution and recovery verification; production service policies still require qualification. This UI implementation does not itself qualify live RCA accuracy.

## Deployed application overview

Reload http://127.0.0.1:8502/ and select kaims or telemetry. Each application now has overview counts, registered services, discovered documents readable without an incident, telemetry configuration status, a scoped live-alert check, and incident investigations. Selecting a service prefills the investigation service. Document contents load only when requested. Overview metadata never includes source credentials or document bodies.

Health remains unknown until a qualified health policy exists. A configured source is labelled configured, not connected. The live-alert button reads the configured Prometheus `/api/v1/alerts` endpoint with a two-second per-source budget and bounded payload; only alerts matching registered services and every configured scope label are shown. Missing labels cause exclusion, not inferred ownership. Empty scoped results do not mean all services are healthy. The alert-view endpoint is read-only; the separately enabled background intake now creates incidents for matching firing alerts. Protocol: https://prometheus.io/docs/prometheus/latest/querying/api/#alerts

Validation: 69 backend tests passed and the isolated Chromium workflow passed. The updated image was deployed to the existing preview while preserving the token, broker and SQLite volume. Read-only browser checks verified both real application pages: kaims has 24 registered services and 3 documents; telemetry has 14 registered services and 3 documents. Both are context_ready. Scoped Prometheus alert checks succeeded with no matching alerts at verification time; 11 unrelated alerts were excluded from the KaiMS source. Broker readiness was true. See overview-verification.json for the recorded result. No incident was created or changed during this deployment check.

The deployed source file is replacement/telemetry-sources.local.json. Set NEXT_TELEMETRY_CONFIG_PATH to its absolute path before any future Compose recreation, and preserve the existing API token, tenant and broker password. Ordinary docker start/restart preserves the container configuration.

## Full workspace UI navigation (2026-09-14)

The deployed frontend is now a routed operations workspace, replacing the earlier stacked form layout. Open http://127.0.0.1:8502/ and sign in with the existing token. The sidebar provides:

- Overview: tenant-scoped portfolio totals, context readiness and investigation activity.
- Applications: paginated application cards and dedicated application dashboards.
- Incident inbox: cross-application search, state filtering and bounded pagination.
- Document library: application selection and scoped document contents loaded on demand.
- Telemetry sources: application source views, with server configuration separated from connection status.
- Workspace settings: pipeline status, source catalog, document roots and explicit capability limits.

Each application has Overview, Services, Documents, Telemetry, Live alerts and Investigations tabs. Services can be filtered by name and link to an investigation form with the service preselected. Onboarding is a dedicated screen. Incident details separate the recorded lifecycle, impact, RCA, resolution, source outcomes and paginated evidence. Raw records remain optional. No placeholder approval or execution action is presented as functional.

Routes use URL fragments, including `/#/applications/kaims/overview`, `/#/applications/telemetry/overview` and `/#/inbox`. Deep links resume after authentication; browser back/forward is supported. Tokens stay in memory, with no local/session storage. Navigation rejects stale responses from previously selected views, and a failed incident refresh labels existing information as stale. Active investigations and pending discovery refresh every eight seconds. Portfolio/list reads omit full incident evidence.

New API reads: authenticated GET /workspace provides tenant-scoped aggregate counts and capability flags; authenticated GET /incidents supports bounded offset pagination, incident/application ID search and state filtering. Search wildcard characters are escaped. No new dependencies, database migrations or legacy application changes were required.

Validation: 69 backend tests passed. The rewritten Chromium fixture journey passed portfolio navigation, service filtering, documents, live-alert unavailability, inbox search, onboarding, incident submission, deep-link login, settings, mobile overflow, evidence XSS handling, tenant separation and stale-state reporting. Fixture screenshots contain synthetic data only. A separate read-only browser check verified the deployed KaiMS and telemetry dashboards, 24/14 services, three documents each, context readiness and broker connectivity. The existing token, database, broker and source mappings were preserved.

Backend limitations remain: production service health is not qualified and independent multi-user authorization is not implemented. Versioned registration and policy-scoped approval, execution and recovery verification are implemented; only the disposable validation target has a configured repair policy. This UI deployment is not a claim that production RCA or automated resolution is qualified.

## Automatic incident intake enabled (2026-09-14)

The running preview enables automatic intake for kaims and telemetry with NEXT_AUTO_INCIDENT_APPLICATIONS=kaims,telemetry and a 30-second polling interval. Its state is available at authenticated GET /incident-intake and shown in the Incident inbox banner. Pending alerts, unrelated services and invalid/missing activation timestamps do not create incidents. Prometheus labels plus activeAt identify an occurrence; polling/restarts preserve the original incident and collection window. A newly activated occurrence can create a new incident. The original alert name, severity, source, activation and fingerprint are stored as request provenance, separate from operational evidence.

Incidents are admitted through the existing transactional store and RabbitMQ outbox. They wait for context when needed, then collect the two minutes preceding first detection and produce independent impact/RCA outcomes. Repeated polls do not rerun an already admitted occurrence. Alert disappearance does not automatically close an incident or establish recovery.

Alert scope may be configured separately with alert_labels. KaiMS metric queries retain application=KaiMS, environment=prod, tenant=default and job=kaims. Its alert rules emit application/environment/service but omit metric-only job/tenant labels; explicit alert_labels={application:KaiMS,environment:prod} now allow those application alerts while rejecting host-only and unrelated external-demo alerts. Service membership is still required. No metric query scope was loosened.

Live verification admitted KaiOpsSSEDisconnected for api-gateway as alert-9aa06a70144eb4e2a0c76bcd39d3d8e6. It reached assessed with 112 accepted metric samples and 80 accepted spans; trace coverage was partial at its limit. RCA remained insufficient_evidence. The real browser check confirmed that incident and its assessment are visible in the inbox. Telemetry had no matching firing alerts at the initial check. No synthetic incident was inserted into the live workspace.

Validation: 72 backend tests passed, the browser workflow passed, and the real RabbitMQ fixture passed automatic alert admission, duplicate-poll protection, context release, collection and assessment. This enables incidents; it does not enable remediation or qualify RCA accuracy.

## Governed resolution qualification

See [RESOLUTION_WORKFLOW.md](RESOLUTION_WORKFLOW.md) for the live RabbitMQ discovery-to-recovery verification, executor contract, policy scope and remaining production limitations.


### Unified operations workspace

The navigation now has one Unified inbox at `/#/inbox`; older `/#/alerts` links open the same screen. Live signals are merged with their scoped investigation IDs, while diagnostic/manual investigations and verified recoveries remain visible without an active Prometheus alert. Signal state is presented separately from investigation state.

The overview borrows the earlier application's Detect / Investigate / Decide / Act / Verify workflow navigation and provides context readiness, attention counts, in-progress totals and verified recovery history. The inbox includes attention, automation, critical and recovered views; search by alert/application/service/incident; record, severity and state filters; source details; pagination; decision and recovery links. Counts and filters cover loaded records. Additional records can be loaded; automatic refresh pauses while browsing additional pages. Source failures are marked as partial results.

Existing application registration, document discovery, service investigation, stored evidence, prior assessments, configured plan approval/rejection, execution and recovery verification remain available. Multi-user ownership/watch assignments and unconfigured production remediation are not implemented by this UI update.

Validation: `node replacement/tests/verify_ui.cjs` covers the unified queue, linked-signal deduplication, filters, legacy alert route and existing workspace workflows. `node replacement/tests/verify_container_stop_ui.cjs` checks that the recorded real container-stop recovery is discoverable in the live unified inbox and opens its assessment and recovery details.


### Telemetry bottleneck qualification

The telemetry trace source explicitly follows frontend descendants through product-catalog, payment, checkout, cart, recommendation, frontend-proxy and other registered demo services when the spans share a trace and parent reference. Assessments include per-operation minimum/maximum sampled latency, flagged-error count, and dependency correlations. This preserves identity and timing without treating nested spans as independent requests or claiming causality.

The telemetry/frontend repair policy remains **not qualified**. There is no verified frontend diagnostic and idempotent repair endpoint, so the system deliberately does not authorize a restart based on latency alone. The qualification gap is recorded in `telemetry-policy-qualification.json`.
