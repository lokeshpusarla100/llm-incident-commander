# LLM Incident Commander: Production LLM Observability & Governance

**A Datadog-native control plane for governing, monitoring, and scaling Large Language Model applications.**

---

## Executive Summary

Large Language Models (LLMs) introduce new classes of failure that traditional APM cannot detect: semantic hallucinations, token cost explosions, nondeterministic latency spikes, and prompt injection attacks.

**LLM Incident Commander** demonstrates how to solve these problems by treating the LLM not as a magic box, but as a governed dependency.

The core philosophy of this project is:
> **"The most important signal is not what an LLM outputs, but when and why the system decides to use or skip it."**

This system enables Datadog to observe the full lifecycle of an LLM interaction—from the decision to execute, to the cost incurred, to the semantic quality of the result. It treats "skipping the LLM" (due to cost, safety, or policy) as a first-class operational signal, not a failure.

---

## What Problem This Solves

Enterprises deploying GenAI face four specific operational risks that this project addresses:

1.  **Silent Cost Explosions**: A looped script or malicious user can generate thousands of dollars in token costs in minutes without triggering standard CPU/Memory alerts.
2.  **Semantic Hallucination**: Models often return 200 OK responses that are factually incorrect or dangerous.
3.  **Quota Exhaustion**: API rate limits are hard stop failures that look like standard 429s but require specific remediations (backoff, fallback).
4.  **Unsafe Execution**: Running LLMs on untrusted input without governance exposes the system to prompt injection.

This project implements a **Control Plane** that governs these risks before, during, and after execution.

---

## How Datadog Is Used

Datadog is not just an observer here; it is the **decision verification layer**. The application emits specialized telemetry that allows Datadog to track the "Control Plane" logic.

### 1. Decision Governance
The application reports *why* it did or did not call the LLM.
- **Metric**: `llm.decision.skipped` (tagged with `reason:cost_limit`, `reason:safe_mode`, `reason:policy`)
- **Metric**: `llm.requests.total` (tagged with `status:success` vs `status:governed_block`)

### 2. Cost & Token Observability
Every request reports authoritative usage metadata.
- **Metric**: `llm.tokens.total` (Input vs Output split)
- **Metric**: `llm.cost.usd` (Estimated real-time cost derived from Gemini pricing models)
- **Monitor**: **Cost Spike Alert** triggers if cost/minute exceeds safety thresholds.

### 3. Semantic Quality (LLM-as-a-Judge)
We implement the Datadog "LLM-as-a-Judge" pattern.
- A secondary, asynchronous LLM evaluates user responses for hallucination.
- **Metric**: `llm.judge.hallucination_score` (0.0 - 1.0)
- **Case Management**: High scores (>0.7) automatically open a **Datadog Case** for human review.

### 4. Incident Management
Monitors are wired directly to Datadog Incident Management.
- **Latency > 2s** → Creates SEV-3 Incident
- **Error Rate > 5%** → Creates SEV-2 Incident
- **Quota Exhaustion** → Creates SEV-1 Incident

---

## Architecture Overview

The system follows a strict separation between the **Control Plane** (Application) and the **Execution Plane** (Model).

### Control Plane (Always On)
- **Component**: FastAPI Application + Datadog Tracer
- **Responsibility**: Auth, Rate Limiting, Cost Calculation, Safety Checks, Decision Logging.
- **Behavior**: Always reliable. Even if the LLM is down, the Control Plane responds with degradation signals.

### Execution Plane (Governed)
- **Component**: Google Vertex AI (Gemini 2.0 Flash) + Vector Search (RAG).
- **Responsibility**: Embeddings, Retrieval, Generation.
- **Behavior**: Usage is optional. The Control Plane can cut off the Execution Plane (e.g., in `SAFE_MODE`) to prevent runaway costs.

### Observability Pipeline
1.  **Application** emits StatsD metrics + JSON Logs.
2.  **Datadog Agent** aggregates and forwards to Datadog.
3.  **Datadog Backend** evaluates Monitors and SLOs.
4.  **Alerts** trigger Incidents or can trigger Jira/PagerDuty flows.

---

## LLM Governance Model

This application treats LLM execution as a **controlled resource**, not a default right.

### Operation Modes
The system supports three explicit modes to balance utility and risk:

1.  **Gemini Only Mode (Default)**
    - **Behavior**: Direct calls to Gemini 2.0 Flash. No Vector Search.
    - **Use Case**: Standard text generation.
    - **Governance**: Rate-limited, Cost-tracked.

2.  **Full RAG Mode**
    - **Behavior**: Vector Search retrieval + Gemini Generation.
    - **Use Case**: Knowledge-grounded answers.
    - **Note**: Requires provisioning the Vector Search infrastructure (see "Vector Search" below).

3.  **Safe Mode**
    - **Behavior**: **Hard Block** on all external API calls.
    - **Response**: Returns a structured "Disabled" signal (200 OK with `status:disabled`).
    - **Use Case**: Testing UI/Observability without incurring a single cent.
    - **Activation**: Set `SAFE_MODE=true`.
    - **Intent**: Safe Mode is designed to validate observability, governance, and incident logic without executing any external AI dependencies.

---

## Detection Rules & Incident Types

The project includes 8 pre-configured Datadog Monitors corresponding to real failure modes.

| Monitor | Signal | Incident Severity | Why |
| :--- | :--- | :--- | :--- |
| **High Latency** | P95 > 2000ms | SEV-3 (configurable threshold) | LLM latency degrades UX significantly. |
| **Error Rate** | > 5% Failure | SEV-2 (configurable threshold) | Indicates API outage or broken integration. |
| **Quota Exhaustion** | 10+ Quota Errors | SEV-1 (configurable threshold) | Hard stop on service; requires immediate intervention. |
| **Cost Spike** | > $0.01 / request | SEV-2 | Protects against budget drain loop. |
| **Token Explosion** | Input > 2000 tokens | Warning | Detects prompt stuffing or abuse. |
| **Hallucination** | Score > 0.7 | Case | Quality degradation requires human review, not waking on-call. |
| **Prompt Injection Indicators** | Regex / heuristic signals | SEV-1 | Critical security event. |

All monitors are exported in `datadog-config/monitors/` as JSON.

---

## Datadog Assets Provided

For reproducibility, we include:

-   **Dashboards**: `datadog-config/dashboards/`
    -   *LLM Incident Commander - Observability*: A single pane of glass for Cost, Quality, and Latency.
-   **Monitors**: `datadog-config/monitors/` (8 JSON definitions)
-   **SLOs**: `datadog-config/slos/`
    -   Availability (99%), Latency (P95<2s), Error Rate (<1%).
-   **Incident Templates**: `datadog-config/incident-templates/`

---

## Vector Search (On-Demand Infrastructure)

To align with responsible cost management, **Vertex AI Vector Search infrastructure is not deployed by default**.

Vertex AI charges per-hour for deployed indices, regardless of traffic. Leaving this running 24/7 for a hackathon submission would be financially irresponsible.

**How to Enable:**
Users can provision the infrastructure on-demand using the included script:
```bash
python setup_vector_search.py
```
This script provisions the Index, Endpoint, and Bucket. Once complete, set `VECTOR_SEARCH_ENABLED=true` to activate Full RAG Mode.

**Ideally**, organizations should use this pattern to spin up ephemeral RAG environments for testing and tear them down (`gcloud ai index-endpoints undeploy-index`) to stop billing.

---

## Demo & Deployment

The system is containerized for easy auditing and deployment.

### Prerequisites
-   Google Cloud Service Account (Vertex AI User)
-   Datadog API Key

### Quick Start (Docker)

This is the standard deployment model:

```bash
# 1. Config
cp .env.example .env
# Set GCP_PROJECT_ID and DD_API_KEY in .env

# 2. Run
docker-compose up --build
```

### Traffic Generation

To prove the observability stack works, we include a traffic generator that simulates real-world patterns (bursts, errors, hallucinations):

```bash
python3 traffic-generator/advanced_traffic_generator.py --rps 2
```

This will populate the Datadog Dashboard with live telemetry.

---

## Why This Matters

This project moves beyond the "Hello World" of building a chatbot. It addresses the **Day 2 Operations** problem: How do you sleep at night with an LLM in production?

By using Datadog to govern the Control Plane, we turn nondeterministic AI behavior into deterministic, manageable operational signals. This is the difference between a demo and a production system.

---

**Datadog Organization**: `Lokesh_pusarla`
**License**: MIT
