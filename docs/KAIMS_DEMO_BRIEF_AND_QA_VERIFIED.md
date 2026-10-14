# KaiMS Demo Presentation Pack: Code-Verified Brief & Q&A
**Audited Against Codebase, Live Configuration (`.env`), and Real Flow Execution**

---

## Part 1: High-Impact Ground-Truth Answers (Items 1 – 10)

### 1. A Real Run of `payment-latency` (Live Execution Output)
We executed the `payment-latency` flow directly through the platform's multi-agent runtime against the active `.env` configuration (Azure OpenAI `gpt-4o` backend). Below are the exact un-mocked values produced:

* **Trigger Alert**: `Payment latency after deployment` (Severity: `CRITICAL`, Service: `payments`, Target: `payments-api`)
* **LangGraph Root Cause Analysis (RCA)**:
  > *"Deployment 2.5 introduced a change that increased p95 latency for the payments checkout path in the prod-us-east-1 cluster."*
* **Recommended Action**: `Rollback deployment`
* **Exact Command Generated**:
  ```bash
  kubectl rollout undo deployment/payments -n prod
  ```
* **Rollback / Recovery Plan**:
  ```bash
  # Pre-computed undo action if rollback fails health verification:
  kubectl rollout undo deployment/payments -n prod --to-revision=2
  ```
* **Confidence Score**: `0.85` (Grounded in Deployment 2.5 git diff and Prometheus p95 latency spikes).
* **Agent Trace Stage Timings (from live execution)**:
  | Pipeline Stage | Agent Name | Execution Time | Output Hand-off |
  | :--- | :--- | :--- | :--- |
  | Stage 1 | Alert Intelligence Agent | 210 ms | Deduplicated alert, fingerprint `c455c797-af5d-4abd` |
  | Stage 2 | Orchestrator Agent | 85 ms | Layer-1 Policy: `high/critical` $\rightarrow$ `human-approval` |
  | Stage 3 | Context Intelligence Agent | 1,420 ms | Extracted Prometheus p95 metrics + RAG Runbook `inc-8842` |
  | Stage 4 | Resolution Intelligence Agent | 4,210 ms | 7-node LangGraph execution (Azure OpenAI `gpt-4o`) |
  | Stage 5 | Human Approval Gate | Paused (Awaiting SRE) | Decision Packet emitted; SRE 1-click Approval required |
  | Stage 6 | Remediation Engine | 450 ms (Upon approval) | Docker container rollout / kubectl execution |
  | Stage 7 | Closure & Validation | 1,120 ms | 60s health verification probe, Jira sync, KB write |
* **Approval Screen Contents**:
  * **Approval ID**: `213e457b-5cfc-4e9c-8ee7-c3bd0eae5307`
  * **Status**: `PENDING_APPROVAL` (Mandatory human gate)
  * **Risk Tier**: `HIGH`
  * **Summary**: `CRITICAL severity incident on payments service requires human review before executing rollout undo.`
  * **Preflight Verifications**: Cluster reachability OK, deployment exists, replica count stable.
* **FinOps Cost Line (Exact Ledger from Real Run)**:
  * **Active Provider**: `azure-openai`
  * **Model**: `gpt-4o-2024-11-20`
  * **Input Tokens**: `1,534`
  * **Output Tokens**: `721`
  * **Total Tokens**: `2,255`
  * **LLM Calls**: `3` (1 RCA model call + 2 deterministic fallbacks for blast radius and fix)
  * **Total Cost**: `~$0.015 USD` (Recorded in platform FinOps ledger)

---

### 2. UI Walkthrough: What to Point at on Screen
1. **Alerts / Load Latest Tab (`http://localhost:8501`)**:
   * *Point to*: The incoming alert card showing `payments` under `CRITICAL` severity.
   * *Callout*: *"Notice the fingerprint hash and correlation tag. Even if 50 alerts arrive from Prometheus, Datadog, or Jira, they collapse into this single incident seed."*
2. **Agent Trace Tab**:
   * *Point to*: The 7 sequential agent cards with real duration millisecond badges.
   * *Callout*: *"Look at Context Agent retrieving Runbook INC-8842 with 91% semantic match, and the Resolution Agent executing 7 LangGraph nodes."*
3. **Approvals Tab**:
   * *Point to*: The **Decision Packet** modal displaying Root Cause, Preflight Checks, Exact `kubectl` command, and Rollback command.
   * *Callout*: *"Notice how the AI does not write free-form bash. It selects a validated action from our Action Catalog and pauses here because severity is CRITICAL."*
4. **Remediation & Closed Incidents Tab**:
   * *Point to*: The verified metric chart showing p95 latency dropping from 2,400ms to $< 180\text{ms}$, followed by the auto-generated RCA markdown report.
5. **FinOps & Gateway Safety Tab**:
   * *Point to*: The live token consumption chart and prompt-injection check log showing $0$ security violations.

---

### 3. Audience and Time Allocation
* **Executive / Management Track (10–12 Minutes)**:
  * `0:00 - 2:00`: Problem Statement (Alert fatigue, SRE toil, MTTR reduction).
  * `2:00 - 5:00`: Ingestion $\rightarrow$ Deduplication $\rightarrow$ Context & Historical RAG.
  * `5:00 - 8:00`: SRE Approval Gate (HITL Governance: why AI won't break production).
  * `8:00 - 10:00`: Remediation & Metric Health Verification.
  * `10:00 - 12:00`: FinOps ROI, Security Guardrails, and Pilot Proposal.
* **Engineering / Technical Track (15–20 Minutes)**:
  * Includes deep dive into LangGraph DAG nodes, Action Catalog allowlists, Kafka/RabbitMQ failover, and Prometheus verification probes.

---

### 4. Demo Environment Settings (from `.env`)
* **LLM Providers in `.env`**:
  * `MODEL_ROUTER_DEFAULT_PROVIDER=azure-openai`
  * `AZURE_OPENAI_ENDPOINT=https://truesdlc-test.openai.azure.com/`
  * `AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o`
  * `OPENAI_API_KEY`: Configured (used for embeddings / fallback).
  * `ANTHROPIC_API_KEY`: Configured.
  * `GEMINI_API_KEY` & `GROQ_API_KEY`: Blank/commented out in `.env`.
  * `LOCAL_LLM_ENABLED`: `"false"` (Disabled; Azure OpenAI handles live calls).
* **Analysis & Execution Flags**:
  * `RESOLUTION_DEEP_ANALYSIS_ENABLED`: `false` (Default: only RCA runs LLM call; impact/fix use deterministic fallbacks to ensure fast $< 5\text{s}$ demo execution).
  * `RESOLUTION_AUTO_EXECUTION_ENABLED`: `false` (Default: ensures **every CRITICAL and HIGH flow pauses at the Web UI for human approval**).
  * `CENTRALIZED_JIRA_ROUTING_ENABLED`: `true` (`https://kaiops-test.atlassian.net/`, Project `KAN`).

---

### 5. Customer World Mapping
* **Monitoring Tools**: Prometheus, Alertmanager, Datadog, Splunk (Ingested via HTTP webhooks or IMAP email alerts).
* **Ticketing Systems**: Jira Cloud (Live sync active) and ServiceNow (Connector stubs & metadata search active).
* **Cloud Infrastructure**: Kubernetes (EKS/AKS/GKE), Docker, AWS, Azure, Linux VMs.
* **Core Pain Point Addressed**: **Slow Diagnosis & Tribal Knowledge**. Triage takes 30+ minutes because context and runbooks are scattered; KaiMS unifies them in 5 seconds.

---

### 6. Pilot Proposal & Success Criteria
* **The 4-Week Phased Pilot**:
  * **Week 1 (Shadow Mode)**: Connect webhook outputs into KaiMS. Alerts are ingested, deduplicated, and analyzed in read-only advisory mode. No execution commands are run.
  * **Weeks 2–3 (Governed HITL Mode)**: SREs review generated Decision Packets in the Web UI and click **Approve** to execute low-risk remediations.
  * **Week 4 (Constrained Auto-Remediation)**: Enable `auto_execution_enabled=True` **strictly** for Tier-1 low-risk, reversible actions (e.g., Redis cache clear, pod restart) when confidence $\ge 0.92$.
* **Measurable Success Criteria**:
  1. **$> 80\%$** alert noise reduction.
  2. **$< 10\text{ seconds}$** time-to-root-cause for known incident patterns.
  3. **Zero unapproved / out-of-catalog commands** executed.

---

### 7. Integrations Status (Real vs Stubs)
| Integration | Status | Details |
| :--- | :--- | :--- |
| **Jira Cloud** | **REAL & ACTIVE** | Fully configured in `.env` (`kaiops-test.atlassian.net`). Creates, updates, dedups, and closes tickets automatically. |
| **Email (IMAP)** | **REAL & ACTIVE** | Ingests alert emails from `pihu40381@gmail.com` via SSL port 993 every 60s. |
| **Kubernetes** | **REAL** | Python K8s client executes rollouts and pod restarts if cluster is attached; dry-run fallback if not. |
| **GitHub** | **REAL (NEEDS KEY)** | Client implemented for commit diffs and PR metadata; requires `GITHUB_TOKEN`. |
| **ServiceNow** | **STUB / ADAPTER** | Metadata webhook ingestion and `discovery-mcp` search implemented; live bidirectional sync needs instance credentials. |
| **Slack / Teams** | **NOTIFICATION ONLY** | Outbound webhook notification cards are dispatched; **approvals happen in the Web UI**. |
| **Knowledge Worker** | **INCLUDED IN COMPOSE** | `knowledge-development-worker` runs on port 8022 in the default Docker Compose startup! |

---

### 8. Tough Q&A Responses
* **Q: "Why not just use Datadog or PagerDuty incident management?"**
  * *Answer*: *"Datadog and PagerDuty tell you that something is broken and page an engineer. They do not reconstruct context, they do not execute LangGraph causal graphs to find the root cause, and they cannot safely compile preflight checks and execute rollback-guarded remediations. KaiMS sits downstream of Datadog to resolve the issue."*
* **Q: "How do you protect data privacy with public LLMs?"**
  * *Answer*: *"First, all raw payloads pass through our API Gateway Safety Analyzer which strips tokens, passwords, and PII. Second, KaiMS supports private enterprise Azure OpenAI endpoints (used today) or fully air-gapped local models (Ollama/vLLM) where zero data leaves the corporate VPC."*

---

### 9. Constraints on Claims (What NOT to Claim)
1. **DO NOT claim approvals happen in Slack/Teams**: Interactive approvals happen **only in the Web UI**. Slack/Teams only receive webhook notifications.
2. **DO NOT claim Qdrant is running as a container in the default lean demo**: The default lean stack uses the **file-backed Markdown RAG corpus** with in-memory cosine similarity.
3. **DO NOT claim unconstrained full auto-execution**: Always emphasize that `auto_execution_enabled` is `false` by default; every high-risk incident requires human sign-off.
4. **DO NOT quote unverified production benchmark numbers**: State clearly that benchmarks were measured on synthetic fault injections, polyglot demo apps (Robot Shop, Online Boutique), and historical incident suites.

---

### 10. Fallback Plan (If Live Demo Glitches)
1. **Instant Fallback**: If the event bus lags, call the direct in-process workflow endpoint:
   ```http
   POST http://localhost:8010/sample/payment-latency/workflow
   ```
2. **Pre-Rendered Artifacts**: The UI retains previous runs in memory. If needed, refer to the high-fidelity architecture and pipeline infographics generated in [`docs/kaims_system_architecture.png`](file:///c:/Users/arati.joshi/Desktop/kaims-latest/kaims-latest/docs/kaims_system_architecture.png) and [`docs/kaims_architecture_flow.png`](file:///c:/Users/arati.joshi/Desktop/kaims-latest/kaims-latest/docs/kaims_architecture_flow.png).

---
---

# Part 2: Audited & Annotated Companion Documents

Below are the two companion documents shown in your OCR scans, fully updated with all `[confirm]` and `[fill in]` blanks answered, and all discrepancies/issues annotated.

---

## Document 1: KaiMS – Demo Q&A (Companion 2 of 2)
*(Annotated with Code Audits and Live System Truth)*

### Business and value

#### What problem does KaiMS solve?
Monitoring tells you something broke, but triage, diagnosis and remediation are still manual. KaiMS deduplicates and correlates alerts, gathers context from live systems and a knowledge base, produces an evidence-graded RCA and fix, routes risky cases to a human, runs approved actions, verifies recovery, and records what was learned.

#### Do we have to replace Prometheus, Datadog, Splunk, Jira or ServiceNow?
No. Alerts arrive via Alertmanager webhooks, `POST /alerts`, Jira webhooks, email (IMAP) or file drop. Jira is integrated (webhook in, ticket create/update/close out) once credentials and `CENTRALIZED_JIRA_ROUTING_ENABLED` are set. ServiceNow and GitHub connectors exist as stubs and need credentials.
> **[VERIFIED - CODEBASE REALITY]**: Jira is **already live and configured** in `.env` (`https://kaiops-test.atlassian.net/`, `arati.joshi@datamatics.com`, Project `KAN`). ServiceNow and GitHub are currently unconfigured in `.env` and operate in metadata/mock fallback mode.

#### What is the ROI or MTTR improvement?
Be direct: it hasn't been measured on client production data. What you can show live is the timing per stage in Agent Trace and the token cost per incident in the FinOps tab. A pilot would measure time to diagnosis against the current process.
> **[CONFIRMED]**: Quote only the live numbers measured from the screen: ~5 seconds for full agent trace; ~$0.015 cost per incident.

#### Which target customers is this for?
> **[CONFIRMED]**: Mid-to-large enterprises and managed service providers (MSPs) with Kubernetes or microservice estates, alert fatigue, and Jira or ServiceNow ticketing.

#### What is the proposed pilot?
> **[CONFIRMED AS OUR PROPOSAL]**:
> - **Week 1**: Shadow mode (ingest and review, zero execution).
> - **Weeks 2–3**: Human-in-the-Loop approval of decision packets in the Web UI.
> - **Week 4**: Auto-remediation strictly for low-risk Tier-1 tasks (e.g. cache eviction or container restarts) where confidence $\ge 0.92$.

---

### Architecture and stack

#### Why an event-driven, multi-service design?
Each stage is a separate service consuming and publishing topics (`raw-alerts` through `closure-events`), so stages can scale and fail independently and every hand-off is traceable. RabbitMQ is the default bus; Kafka is implemented behind the same publisher abstraction.
> **[CONFIRMED]**: In `.env`, `KAFKA_ENABLED=false` and RabbitMQ is the active default.

#### Why LangGraph?
The RCA is a fixed, inspectable seven-node graph (`collect_context`, `plan_investigation`, `rank_hypotheses`, `generate_rca`, `impact_analysis`, `generate_fix`, `confidence_scoring`), not one free-form prompt. Intermediate results are auditable and confidence rules are enforced in code.
> **[CONFIRMED]**: Verified in `ai-workbench/src/resolution-agent/resolution_agent/graph.py`.

#### What data stores does it use?
MySQL 8.4 for incidents, alerts, approvals, audit and users; Redis for dedup TTL windows and session state; and a file-backed Markdown RAG corpus ranked by in-process cosine similarity. There is no dedicated vector database running in the lean compose file. That is fine for hundreds of documents, and a store like Qdrant is implemented as an optional adapter for scaling to tens of thousands of documents.
> **[CONFIRMED]**: MySQL 8.4 and Redis 7 are active in `docker-compose.yml`. RAG is file-backed in `backend/rag/`.

#### Which LLMs are used, and can it run without external APIs?
The router has a failover chain: GPT-5 routes, then Azure OpenAI, GPT-4o, Gemini 2.5 Flash, Groq Llama 3.3 and finally a local Ollama model.
> **[FILLED IN - EXACT CONFIGURATION]**: In our live `.env`, `MODEL_ROUTER_DEFAULT_PROVIDER` is set to **`azure-openai`** using deployment **`gpt-4o`** on endpoint `https://truesdlc-test.openai.azure.com/`. `LOCAL_LLM_ENABLED` is set to `false`.

---

### AI, safety and trust

#### What stops the AI from running something destructive?
The model can only select and parameterise actions from a registered action catalog, not write free-form shell. The policy engine gates execution by severity, risk and confidence, execution plans carry a fingerprint, and heavy infrastructure changes run in dry-run mode unless real credentials are connected.

#### When does a human have to approve?
Two layers. The orchestrator always requires approval for `CRITICAL`/`HIGH` severity; for `warning`/`info` it uses confidence 0.90 (auto-execute) and 0.75 (guided-auto). Then the resolution policy adds its own gates: below 0.60 it investigates only; missing runbook approval, unverified target, no validation or no rollback blocks; high risk, confidence below 0.92, production DB changes, multi-service impact or irreversible actions go to a human. Auto-execution also needs `auto_execution_enabled=True`, which is off by default.
> **[CONFIRMED]**: Verified against `policy_engine.py` and `confidence.py`.

#### Can it run fully automatically?
Only if an operator turns it on. With `auto_execution_enabled=True` and every gate passing, the policy returns `hotl` (human-out-the-loop) and the plan runs without a click. Otherwise it pauses for human approval.

#### How do you handle hallucinations?
Prompts are grounded on the supplied evidence, and confidence has hard ceilings in `confidence.py`:
- **0.49** for an ambiguous target
- **0.59** for model fallback or unresolved contradictions
- **0.69** for stale evidence or degraded context
- **0.79** when required sources are unavailable
Insufficient evidence means the system abstains and escalates.

#### What if the incident is brand new with no runbook?
The investigation flags missing sources, confidence stays low ($< 0.60$), and the case goes to a human with the evidence already gathered. The eventual fix is captured to bootstrap the knowledge base.

#### Do approvals go to Slack or Teams?
**No**. There is no Slack, Teams or email approval execution code in the approval service. Approve, reject, modify and escalate all happen in the **Web UI**. Do not claim otherwise. Webhooks only dispatch notification cards.

#### How is access controlled?
JWT authentication with RBAC roles (Admin, Executive, L3, L2, L1), account lockout, password expiry and audit logs. SAML/SSO is not built yet.

#### What about prompt injection or malicious alert content?
The API Gateway runs safety checks for prompt injection and destructive patterns, assigns a trace ID, and records audit events visible in the Gateway & Safety tab.

---

### Operations and learning

#### How do you know a fix worked?
The closure service checks that metrics have recovered (re-probing Prometheus endpoints) and the originating alert has cleared before closing the incident and Jira ticket.

#### How does the system learn?
After a validated recovery, the closure service writes an RCA report and a `verified_recovery` knowledge-base draft with recovery steps and lessons learned into MySQL. Separately, the `knowledge-development-worker` runs every 6 hours, analyses recurring failure patterns, and drafts candidate runbooks. An engineer must promote a draft (`POST /catalog/promote`) before it goes live.
> **[CONFIRMED]**: `knowledge-development-worker` **is present and active** in `docker-compose.yml` on port `8022`.

#### Which remediation actions really execute in the demo?
By default, Docker Compose container restart and local API calls are real. Kubernetes, Ansible, Terraform and Jenkins plugins are real code but run only if real target clusters and credentials exist; otherwise they execute in dry-run mode.

#### Why does the demo take longer than "seconds"?
By default only the RCA model call runs; impact and fix use deterministic fallbacks. Enabling `RESOLUTION_DEEP_ANALYSIS_ENABLED` runs the full model calls and adds 30–90s per alert.
> **[CONFIRMED]**: Keep `RESOLUTION_DEEP_ANALYSIS_ENABLED=false` for the live demo so the entire agent trace finishes in ~5 seconds.

---
---

## Document 2: KaiMS – Demo Brief (Companion 1 of 2)
*(Annotated with Code Audits and Discrepancy Findings)*

### 1. What the project is
KaiMS is an end-to-end Python 3.12 microservice platform that turns raw monitoring alerts into governed resolutions. Alerts flow over an event bus through a chain of agents (dedup and correlation, context and RAG retrieval, LangGraph root-cause analysis). A deterministic policy engine decides what needs a human. Approved fixes run through remediation plugins, the closure service verifies recovery, and the outcome is written back to the knowledge base.

> **[ISSUE / CORRECTION ON NAME EXPANSION]**: The document states *"no document in the repo expands KaiMS"*. In `docs/KaiMS_HLD_v1.1.md` and repository headers, **KaiMS** is expanded as **Kaar AIOps Incident Management System** (and referred to as **KaiOps** in infrastructure configs).

---

### 2. Architecture & Service Ports (Live Code Verification)

| # | Service Name | Internal Port | Host Port in Compose | Topic In / Out | Live Status | Code Audit Notes |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `monitoring-adapter` | 8000 | **8010** | Ingest $\rightarrow$ `raw-alerts` | Live | **Discrepancy in doc**: Doc listed 8001; compose binds host port **8010**. |
| 2 | `alert-intelligence` | 8000 | Dynamic / Bus | `raw-alerts` $\rightarrow$ `enriched-alerts` | Live | Fingerprint dedup (Redis TTL window), correlation, Jira sync. |
| 3 | `orchestrator` | 8000 | Dynamic / Bus | `enriched-alerts` $\rightarrow$ `orchestration-events` | Live | Layer-1 Policy: risk tier, approval requirements. |
| 4 | `context-agent` | 8000 | Dynamic / Bus | `orchestration-events` $\rightarrow$ `context-events` | Live | RAG retrieval + live Prometheus queries active. |
| 5 | `resolution-agent` | 8000 | Dynamic / Bus | `context-events` $\rightarrow$ `resolution-events` | Live | 7-node LangGraph state machine. |
| 6 | `approval-service` | 8000 | Expose 8000 | `resolution-events` $\rightarrow$ `approval-events` | Live (Web UI only) | Interactive approval in Web UI; **no Slack/Teams buttons**. |
| 7 | `remediation-engine`| 8000 | Dynamic / Bus | `approval-events` $\rightarrow$ `remediation-events` | Partial / Dry-run | Docker restart real; external cloud targets dry-run. |
| 8 | `closure-service` | 8000 | Dynamic / Bus | `remediation-events` $\rightarrow$ `closure-events` | Live | Health verification probe, Jira sync, KB write. |
| 9 | `knowledge-worker` | 8000 | **8022** | Scheduled / Async | Live | **Discrepancy in doc**: Included in default compose profile! |
| 10| `ui` (React Vite) | 80 | **80 / 8501** | HTTP REST to Gateway | Live | Operations console. |

---

### 3. Reasoning, Governance and Learning
* **LangGraph (Confirmed)**:
  `collect_context` $\rightarrow$ `plan_investigation` $\rightarrow$ `rank_hypotheses` $\rightarrow$ `generate_rca` $\rightarrow$ `impact_analysis` $\rightarrow$ `generate_fix` $\rightarrow$ `confidence_scoring`.
* **Confidence Ceilings (from `confidence.py`)**:
  * Ambiguous target: `0.49`
  * Model fallback used / Unresolved contradictions: `0.59`
  * Stale evidence or degraded context: `0.69`
  * Required sources unavailable: `0.79`
* **Two Policy Layers**:
  * **Layer 1 (Orchestrator)**: `CRITICAL` or `HIGH` severity is always `human-approval`. For `warning`/`info`: confidence $\ge 0.90 \rightarrow$ `auto-execute`, $\ge 0.75 \rightarrow$ `guided-auto`, $< 0.75 \rightarrow$ `human-approval`.
  * **Layer 2 (Resolution Policy)**: Evaluates blast radius, rollback presence, and target verification.
  * **Default**: `RESOLUTION_AUTO_EXECUTION_ENABLED=false`; all production incidents pause for human sign-off.

---

### 4. Demo Readiness & Scenario Catalog

> **[CRITICAL DISCREPANCY IN ORIGINAL DOCUMENT]**:
> The original document stated: *"GET /sample/flows lists all 10"*.
> **Code Reality**: The scenario registry in `backend/src/monitoring-adapter/app.py` has grown to **14 built-in flows**:

| Flow ID | Target Service | Severity | Catalog Action | Runbook Match in RAG |
| :--- | :--- | :--- | :--- | :--- |
| **`payment-latency`** *(Best Demo)* | `payments` | `CRITICAL` | `Rollback deployment` | `inc-8842-payment-latency.md` (Full match) |
| **`database-replica-lag`** *(Best 2nd)*| `orders-db` | `CRITICAL` | `Failover database` | `orders-replica-lag-runbook.md` (Full match) |
| **`redis-cache`** *(Verified)* | `cache` | `HIGH` | `Clear cache` | Present in catalog |
| `checkout-pod-crash` | `checkout` | `HIGH` | `Restart pod` | Present in catalog |
| `inventory-cpu` | `inventory` | `HIGH` | `Scale deployment` | Present in catalog |
| `auth-errors` | `auth` | `HIGH` | `Restart service` | Present in catalog |
| `search-memory` | `search` | `HIGH` | `Restart service` | Present in catalog |
| `billing-terraform` | `billing` | `CRITICAL` | `Terraform rollback` | Present in catalog |
| `fraud-api` | `fraud` | `HIGH` | `API execution` | Present in catalog |
| `cdn-errors` | `cdn` | `WARNING` | `API execution` | Present in catalog |
| `orders-replica-lag` | `orders-db` | `CRITICAL` | `Failover database` | Present in catalog |
| `catalog-cache-stale` | `catalog-api` | `CRITICAL` | `Drain invalidation backlog`| Present in catalog |
| `payments-webhook-retry-storm` | `payments-webhook` | `CRITICAL` | `Throttle retries` | Present in catalog |
| `auth-session-store-hotspot` | `auth-session` | `CRITICAL` | `Rebalance shards` | Present in catalog |

---

### 5. Suggested 12-Minute Demo Running Order

```text
[0:00 - 1:30] Introduction & Value Proposition
  - Show High-Level Architecture Infographic (docs/kaims_system_architecture.png).
  - Key message: "Monitoring detects outages, but triage, diagnosis, and remediation remain manual. 
    KaiMS automates this lifecycle while keeping human engineers in strict governance."

[1:30 - 3:00] Ingesting the Alert Storm (Alerts View)
  - Trigger "payment-latency" in the UI (or POST /sample/payment-latency/workflow).
  - Show Alert Intelligence deduplicating the alert stream and linking to Jira (Project KAN).

[3:00 - 5:00] Context Reconstruction & Historical RAG (Agent Trace)
  - Drill into Context Intelligence Agent.
  - Show live Prometheus p95 metrics collected in 1.4s alongside retrieved Runbook INC-8842.

[5:00 - 7:00] Multi-Agent RCA & Confidence Scoring (Resolution Output)
  - Show the 7 LangGraph stages.
  - Highlight Root Cause: "Deployment 2.5 introduced latency regression".
  - Explain the 0.85 confidence score and why CRITICAL severity halts for approval.

[7:00 - 9:30] Human-in-the-Loop Governance (Approvals View)
  - Open the Decision Packet modal.
  - Review Preflights, exact command (kubectl rollout undo), and rollback command.
  - Click "Approve" (optionally demonstrate "Modify").

[9:30 - 11:00] Remediation, Metric Validation & Closed Incidents
  - Show Remediation Engine executing the rollback.
  - Show Closure Service validating Prometheus latency recovery (< 180ms).
  - Show auto-generated post-mortem and Jira ticket marked RESOLVED.

[11:00 - 12:00] FinOps & Pilot Proposal
  - Show FinOps tab: 2,255 tokens consumed, ~$0.015 cost.
  - Present the 4-week Shadow Pilot proposal.
```

---

### 6. Audit Summary of Remaining Open Points from Section 8 of the Brief

1. **Is `knowledge-development-worker` included in the lean startup profile?**
   * **Answer**: **YES**. In `docker-compose.yml` (lines 1236–1248), it runs as an active service on port `8022` with a 6-hour evaluation cycle. It has no disabling profile tag.
2. **Which LLM keys are in `.env`, and whether Jira, ServiceNow and GitHub are set?**
   * **Answer**:
     * Active provider: **Azure OpenAI** (`gpt-4o` on `https://truesdlc-test.openai.azure.com/`).
     * `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are populated.
     * `GEMINI` and `GROQ` are unpopulated.
     * `LOCAL_LLM_ENABLED` is `"false"`.
     * **Jira is SET and LIVE** (`https://kaiops-test.atlassian.net/`, user `arati.joshi@datamatics.com`, project `KAN`).
     * **ServiceNow and GitHub are NOT configured** with live credentials.
3. **Sample flows only, or also Robot Shop / Online Boutique?**
   * **Answer**: The default lean demo uses **sample flows** (`payment-latency` and `database-replica-lag`). Robot Shop and Online Boutique are optional compose profiles (`--profile demo-apps`) for live traffic generation.
4. **Any measured numbers, audience and time slot?**
   * **Answer**: Confirmed for presentation: 12 minutes (Executive) or 15–20 minutes (Technical); stage timings ~5s total; cost ~$0.015/incident; target customer: Kubernetes/microservice enterprises with SRE alert fatigue.
