# LLM Incident Commander - Video Demo Script

## Section 1: Introduction (30 seconds)
"Hi, I'm Lokesh Kumar and this is LLM Incident Commander - an observability-first AI assistant built for the Datadog AI Accelerate Challenge."

**[Screen: Show Architecture Diagram in README]**

"We built a production-grade FastAPI application using Vertex AI's Gemini 2.0 Flash to help SREs troubleshoot incidents. But the real story is the Observability."

## Section 2: Observability & Dashboards (60 seconds)
**[Screen: Show Datadog Dashboard]**

"Here in Datadog, we have a comprehensive operational dashboard. It's not just basic stats; we track:
- **LLM Health Status**: A unified RAG status indicator
- **Token Efficiency**: Monitoring input/output ratios
- **Cost Per Request**: Real-time economic tracking"

"We implemented 6 different monitors, including detection for **Prompt Explosions** and **Cost Spikes**."

## Section 3: LLM-as-a-Judge Innovation (30 seconds)

**[Screen: Show Datadog dashboard with llm.judge.* metrics]**

"Unlike simple keyword matching, we implemented Datadog's recommended LLM-as-a-Judge architecture."

**[Point to llm.judge.hallucination_score graph]**

"A second Gemini instance runs asynchronously in the background, evaluating every response for semantic accuracy, contradictions, and evasiveness."

**[Show logs with judge reasoning]**

"This creates the `llm.judge.hallucination_score` metric you see here - a true measure of quality, not just linguistic cues."

**[Show monitor triggering]**

"When the judge detects issues, it creates a Case in Datadog for AI team review, including the judge's reasoning."

**[Quick point to Datadog blog reference in monitor]**

"This pattern mirrors what Datadog's own LLM Observability product offers, proving it's achievable with Vertex AI."

## Section 4: Incident Management (30 seconds)
**[Screen: Trigger an incident via traffic generator]**

"Let's simulate a high-latency event. Watch as Datadog automatically declares an Incident, assigning it SEV-3, and pages the on-call engineer with a runbook link."

## Section 5: Conclusion (30 seconds)
"LLM Incident Commander demonstrates that with Vertex AI and Datadog, you can build AI apps that are not just powerful, but reliable, observable, and safe for enterprise production."

"Thank you."
