# Latest 50 incident recovery batch, 2026-09-07

## Verified outcome after approved activation

- **23 of 50 incidents are closed**: one previously closed, two exporter closures from the initial run, and **20 demo closures from this approved run**.
- **27 remain open**: five demo incidents blocked by repeated RCA recommendation changes, plus the 22 previously identified incident-specific blockers.
- The exact eight-profile proposal was explicitly approved by the user, activated, and deployed in closure-service. No registry approval remains pending.
- All 20 new demo closures have 66 passing observations each over five minutes (**1,320 observations total**), CLOSED lifecycle projections, and two published events each (**40 events**).
- The authenticated UI-facing incident API agrees with all 25 demo database states: 20 closed, five investigating.
- Validation: **48 focused tests passed**; Ruff F checks passed for the batch tooling.

## Restored applications and approved scope

Restored 27 Robot Shop and Online Boutique application/exporter containers. Corrected Robot Shop exporter DNS to explicit rs-* service names and added independent HTTP/TCP health probes. The active registry matches the approved proposal SHA256 `a41decb3d9c6807934123dddd8442fa43048ae6ba16d7210ffb82a0b825e3903`.

The eight added profiles require exact alert families, target labels, and explicit incident-ID allowlists totaling 25 records. They do not grant closure to other incidents. The frontend profile covers all three linked alert families.

| Activated target | Allowed incidents | Alert family coverage |
| --- | ---: | --- |
| robot-shop-redis | 4 | RobotShopServiceDown |
| robot-shop-mysql | 3 | RobotShopServiceDown |
| robot-shop-mongodb | 3 | RobotShopServiceDown |
| robot-shop-rabbitmq | 3 | RobotShopServiceDown |
| robot-shop-cart | 3 | RobotShopServiceDown |
| robot-shop-payment | 3 | RobotShopServiceDown |
| ob-paymentservice | 3 | OnlineBoutiquePaymentServiceDown |
| blackbox | 3 | OnlineBoutiqueFrontendDown, HighNetworkLatency, HighNetworkPacketLoss |

## Five demo incidents still blocked

Each received new RCA recommendations during its original observation window. Fresh assessments were requested against the updated recommendations, but another recommendation change superseded each second attempt. The binding guard correctly prevented closure using stale incident context. No closure criterion or binding check was relaxed.

Next work: coordinate context enrichment/RCA refresh with recovery assessment so a current incident binding can remain stable for a complete window, then request fresh assessments. Health preflight alone is insufficient closure proof.

## Evidence

- [Approved requests, retries, and API assessment results](demo-recovery-approved-run-2026-09-07.json)
- [Durable reports, observation counts/windows, lifecycle states, and published events](demo-recovery-closure-proof-2026-09-07.json)
- [UI-facing API verification](demo-recovery-api-verification-2026-09-07.json)
- [Full fixed selection and audit](latest-50-recovery-batch-2026-09-07.json)

## Selected records

Selection was fixed before processing: latest 50 default-tenant incidents by created_at DESC, id DESC. No selected incident has a linked Jira ticket. Original gate results remain in the JSON audit as historical attempts.

| Incident | Service | Current status | Result / next action |
| --- | --- | --- | --- |
| 89433e20-b9f1-48da-88a5-9aa1a248eb06 | mysql | investigating | Specify and implement reviewed retention/archive policy. The alert-table row-count alert is still firing; do not delete data just to clear it. |
| e00ea76e-556a-4306-997e-02f65afa83d3 | kaiops-platform | investigating | Register end-to-end message-processing checks and validate new traffic plus dead-letter behavior. An idle interval without new dead letters is insufficient recovery proof. |
| 8ae0a513-3579-4ab6-8c0c-064080618857 | robot-shop-redis | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 512fe8c0-0914-4e56-b276-04e9be24c0d9 | robot-shop-rabbitmq | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| c10d39a5-cd6d-43e2-89ee-741cdbdcd778 | robot-shop-payment | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 1a26fb32-0de5-4f03-b08a-20d6b89c8fc4 | robot-shop-mysql | investigating | Blocked: RCA recommendation changed during both assessment attempts. Coordinate context/RCA updates so the incident binding remains stable for a fresh five-minute window; retain the supersession guard. |
| 94d16482-72d2-4209-a45b-ee3fa45d52da | robot-shop-mongodb | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 69b1118a-7be3-4536-86ac-bc891df1bfc7 | robot-shop-cart | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| d44522fc-7c8d-46ac-9d6a-2484851d1b2a | ob-paymentservice | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| d79b7867-3572-478a-9ed4-02dd41828f70 | parabank-web | investigating | External probe still exceeds its 200ms latency threshold. Investigate network/remote-service latency and establish registered recovery checks. |
| abb9dbe5-3335-4937-9e23-aaf11d14d7cf | blackbox | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| eb92736c-43a4-445d-8f7c-8fa4b63494b4 | httpbin-failure-lab | investigating | The external target intentionally returns HTTP 503. Resolve the fault-test intent with its owner; it currently fails availability and latency probes. |
| 6d716f52-c67d-41fa-ac55-7d73a120da37 | orchestrator | investigating | Register checks for the corrected PolicyEngineUnavailable alert, then run an independent observation window; do not use unrelated service-down authorization. |
| 28316068-c6ab-4ac3-8d4b-caba8f92d638 | mysql | investigating | Specify and implement reviewed retention/archive policy. The alert-table row-count alert is still firing; do not delete data just to clear it. |
| c7b9adea-de2e-4b5d-bd8d-23eec519fccb | api-gateway | investigating | Verify latency under current traffic for every linked alert family; register scoped checks and resolve mixed-family binding before closure. |
| 479adfb0-217b-4ab6-b00b-aa3142c4c3a6 | kaiops-platform | investigating | Register end-to-end message-processing checks and validate new traffic plus dead-letter behavior. An idle interval without new dead letters is insufficient recovery proof. |
| 7aabfd53-54a6-43e3-a592-df3c845715de | parabank-web | investigating | External probe still exceeds its 200ms latency threshold. Investigate network/remote-service latency and establish registered recovery checks. |
| 4e0efeed-3c9c-47bc-ae9d-6e89e2212474 | mysql-exporter | closed | Closed with persisted independent recovery proof; closure and lifecycle events published. |
| 144d4e97-b71b-4961-bc4b-a4b85f35a0f2 | robot-shop-redis | investigating | Blocked: RCA recommendation changed during both assessment attempts. Coordinate context/RCA updates so the incident binding remains stable for a fresh five-minute window; retain the supersession guard. |
| abc0a588-9617-44ab-8db3-06dbb4e5f2c5 | robot-shop-rabbitmq | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 31cf7879-fffb-48f6-a887-015213348f28 | robot-shop-payment | investigating | Blocked: RCA recommendation changed during both assessment attempts. Coordinate context/RCA updates so the incident binding remains stable for a fresh five-minute window; retain the supersession guard. |
| b8d23ba1-9015-4d1b-afd2-486da4c8655c | robot-shop-mysql | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| f49363e8-eb41-46a8-bd66-f8e9eb525ed7 | robot-shop-mongodb | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| d11b7456-8382-42e6-bc4c-bc9cb1d428a4 | robot-shop-cart | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 781593ae-9685-4143-b32b-ede0a5cb08f1 | httpbin-failure-lab | investigating | The external target intentionally returns HTTP 503. Resolve the fault-test intent with its owner; it currently fails availability and latency probes. |
| 1725aaf9-f358-4569-9a09-7504a76ea563 | ob-paymentservice | investigating | Blocked: RCA recommendation changed during both assessment attempts. Coordinate context/RCA updates so the incident binding remains stable for a fresh five-minute window; retain the supersession guard. |
| f4c2ab59-496f-453f-ac67-5a390992224d | blackbox | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 7b31041c-09e4-49ee-96f6-4924de77c43d | mysql | investigating | Specify and implement reviewed retention/archive policy. The alert-table row-count alert is still firing; do not delete data just to clear it. |
| 8d7674c2-e1f9-4c25-ac24-ad7a0c193f5d | robot-shop-redis | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| c0cc4aef-7cb8-475e-a143-32bbbde92719 | robot-shop-rabbitmq | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| e271a12b-ce0f-4ba9-9546-f15a5f43e2f6 | robot-shop-payment | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 6861588c-4dd4-4625-b496-c4679b9280ba | robot-shop-mysql | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 0638d6ef-4a7e-423f-aebb-364f2353fa56 | robot-shop-mongodb | investigating | Blocked: RCA recommendation changed during both assessment attempts. Coordinate context/RCA updates so the incident binding remains stable for a fresh five-minute window; retain the supersession guard. |
| 8bd182fe-4ab4-430b-9afb-f65708c85b6c | robot-shop-cart | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 54287c29-d9a0-4fdd-b778-50429ed275fb | parabank-web | investigating | External probe still exceeds its 200ms latency threshold. Investigate network/remote-service latency and establish registered recovery checks. |
| e6b23087-9cdf-4eeb-9e09-bb0cb2ab229a | ob-paymentservice | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| dab25dd1-99e4-40db-9f4c-afed5b3092b3 | httpbin-failure-lab | investigating | The external target intentionally returns HTTP 503. Resolve the fault-test intent with its owner; it currently fails availability and latency probes. |
| 9eb6f6f8-e4b3-4966-b369-a5c99c09f8fa | blackbox | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
| 24a1985b-a5d6-479f-8634-c4d6034fb6ba | kaiops-platform | investigating | Register end-to-end message-processing checks and validate new traffic plus dead-letter behavior. An idle interval without new dead letters is insufficient recovery proof. |
| 9afd4084-99cb-487f-b6ba-f926cd4f72fa | mysql-exporter | closed | Closed with persisted independent recovery proof; closure and lifecycle events published. |
| a09afa04-d3a6-4eda-929b-d90c97dc8580 | api-gateway | investigating | Verify latency under current traffic for every linked alert family; register scoped checks and resolve mixed-family binding before closure. |
| 5371bbae-8597-45ed-b322-3c223f64db5d | orchestrator | investigating | Register checks for the corrected PolicyEngineUnavailable alert, then run an independent observation window; do not use unrelated service-down authorization. |
| 11bc6cb8-3f0a-48b4-acbe-25f95bf2c909 | api-gateway | investigating | Verify latency under current traffic for every linked alert family; register scoped checks and resolve mixed-family binding before closure. |
| 60bd1028-a0b8-4688-83fa-3e1e06f3c59d | api-gateway | investigating | Verify latency under current traffic for every linked alert family; register scoped checks and resolve mixed-family binding before closure. |
| 79cf85a7-eacd-4af6-a8df-9b555384092d | httpbin-failure-lab | investigating | The external target intentionally returns HTTP 503. Resolve the fault-test intent with its owner; it currently fails availability and latency probes. |
| 6b9f4031-366a-4004-b4e4-5a7d6dd720c2 | mysql | investigating | Specify and implement reviewed retention/archive policy. The alert-table row-count alert is still firing; do not delete data just to clear it. |
| c8a4d863-f394-49ed-bf9a-506b4c0d463b | kaiops-platform | investigating | Register end-to-end message-processing checks and validate new traffic plus dead-letter behavior. An idle interval without new dead letters is insufficient recovery proof. |
| e324b733-0111-4b0a-8c12-c36577f8d828 | mysql-exporter | closed | Closed with persisted independent recovery proof; closure and lifecycle events published. |
| 9a069466-0f28-436b-aac3-3e18294f261f | parabank-web | investigating | External probe still exceeds its 200ms latency threshold. Investigate network/remote-service latency and establish registered recovery checks. |
| 159bb131-6330-4d07-947b-6e5c54e801be | robot-shop-redis | closed | Closed after 66 passing independent observations over five minutes; both closure and lifecycle events published. |
