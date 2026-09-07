# KaiMS end-to-end tuning ? 7 September 2026

Deployed a smaller incident command response and corrected browser asset caching.
The command response removes only projection context, context metadata and
recommendation copies that exactly equal the canonical top-level values.
Distinct historical projections, validation samples and stored evidence remain
unchanged. Source objects are not mutated. Regression cases verify both paths.

Removed `Clear-Site-Data: "cache"` from HTML responses, which otherwise evicted
hashed assets on each navigation/reload. HTML still uses no-store; hashed assets
remain immutable and compressed. Browser tests enforce both cache contracts.

## Measurements and verification

- Exact platform incident response: 4,082,359 ? 1,604,925 bytes, a 60.7% reduction
  before transport compression. Five-request latency samples varied; this run
  does not establish a latency improvement.
- 68 services running; two one-shot initialization jobs exited. No unhealthy
  services, and no sampled errors in the seven core pipeline service logs.
- Broker: zero ready and dead-letter messages; one resolution message in flight
  at the sample; that resolution queue returned to zero on follow-up. Absence of Prometheus queue series was cross-checked directly
  with RabbitMQ rather than treated as proof of empty queues.
- 130 lifecycle/recovery/database regression tests and nine command tests pass.
- Two production browser startup/cache tests pass.
- Live history shows all 99 previously verified batch closures among 135 rows;
  pagination works and the inbox does not overflow at 1100px.
- Exact incident detail retains six recovery checks and all 11 sample rows for
  the expanded check, a Closed milestone, and collapsed historical investigation.
- Production gateway/UI builds and bundle budgets pass; git diff --check passes.

No new live failure was injected: lifecycle transitions were exercised in
regression fixtures and existing persisted recovery evidence was verified live.
The intentional httpbin 503 probe and external ParaBank latency alerts remain;
monitoring also reports idle SSE clients and low traffic. These are not evidence
of a stalled closure pipeline. No thresholds were relaxed or tickets force-closed.

Raw measurement summaries: [JSON](kaims-e2e-tuning-2026-09-07.json).
