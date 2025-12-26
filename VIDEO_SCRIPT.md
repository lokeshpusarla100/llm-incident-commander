# LLM Incident Commander - Video Script

**Total Duration: 3 minutes**

---

## Opening (0:00 - 0:20)

**[Screen: Dashboard Overview]**

> "Hi! I'm presenting LLM Incident Commander for the Datadog Challenge. This is an intelligent incident management system powered by Vertex AI with end-to-end observability. Let me show you what makes this solution innovative."

---

## Part 1: The Problem & Solution (0:20 - 0:50)

**[Screen: Architecture Diagram]**

> "LLM applications face unique challenges: unpredictable latency, quota limits, and most critically - quality degradation through hallucinations. My observability strategy addresses all three."

**[Screen: Application Code showing hallucination detection]**

> "I've implemented custom metrics including a hallucination score that analyzes response uncertainty, real-time cost tracking per request, and comprehensive error categorization."

---

## Part 2: Detection Rules (0:50 - 1:30)

**[Screen: Monitors Page]**

> "I've configured four detection rules, each with detailed runbooks:"

1. **High Latency Monitor** *(0:55)*
   > "First, latency monitoring. When average response time exceeds 2 seconds for 5 minutes, it triggers an incident with full APM trace context."

2. **Error Rate Monitor** *(1:05)*
   > "Second, error rate tracking. Above 5% error rate triggers a critical incident with error logs and type classification - quota, timeout, or API errors."

3. **Hallucination Score Monitor** *(1:15)*
   > "Third - and this is unique - quality monitoring. High hallucination scores create a case for AI engineering review, not an urgent incident, because it needs analysis not immediate action."

4. **Quota Exhaustion** *(1:25)*
   > "Finally, proactive quota monitoring prevents service outages."

---

## Part 3: Incident Management (1:30 - 2:00)

**[Screen: Incident Example]**

> "When monitors trigger, they don't just send alerts - they create actionable incidents in Datadog with rich context."

**[Click through incident details]**

> "Each incident includes the triggering metric values, direct links to APM traces showing exactly which requests were slow, relevant error logs, and most importantly - a detailed runbook telling engineers what to check and how to mitigate."

**[Show incident timeline]**

> "This turns monitoring into action - engineers can start investigating immediately with all the context they need."

---

## Part 4: Dashboard & SLOs (2:00 - 2:30)

**[Screen: Dashboard]**

> "The dashboard provides a single pane of glass view. Real-time metrics, token usage, cost per hour, and that custom hallucination score trend."

**[Scroll to SLO widgets]**

> "I've defined three SLOs: 99% availability over 30 days, 95th percentile latency under 2 seconds over 7 days, and less than 1% error rate. These track error budgets so we know when we're at risk of violating our reliability targets."

**[Show traffic generator results]**

> "The advanced traffic generator I built can trigger each monitor on demand with different scenarios - slow queries, invalid inputs, hallucination-prone prompts - perfect for demonstrating the full observability stack."

---

## Part 5: Innovation & Closing (2:30 - 3:00)

**[Screen: Code showing custom metrics]**

> "What sets this apart? First, LLM-specific telemetry - not just generic monitoring but metrics that matter for AI applications. Cost tracking, quality scoring, token usage."

**[Screen: Incident with runbook]**

> "Second, intelligence in the incident creation. Different severities and response types - incidents for urgent issues, cases for quality reviews."

**[Screen: SLO summary]**

> "And third, business alignment through SLOs. We're not just tracking metrics, we're measuring service level objectives that tie to user experience."

**[Screen: Dashboard again]**

> "This is production-ready observability for LLM applications. Thank you!"

---

## Recording Tips

1. **Screen Recording**: Use OBS Studio or similar
2. **Resolution**: 1920x1080 minimum
3. **Frame Rate**: 30 FPS
4. **Audio**: Clear microphone, quiet environment

### Timeline Checklist

- [ ] 0:00-0:20: Hook + overview
- [ ] 0:20-0:50: Problem statement + innovation
- [ ] 0:50-1:30: Detection rules deep dive
- [ ] 1:30-2:00: Incident management demo
- [ ] 2:00-2:30: Dashboard + SLOs
- [ ] 2:30-3:00: Innovation summary + close

### Screens to Prepare

1. Datadog Dashboard (full screen, data loaded)
2. Monitors page showing all 4 monitors
3. Example triggered incident with full context
4. SLO summary page
5. APM traces page
6. Code snippet of hallucination detection
7. Traffic generator running with statistics

### Practice Run

1. Record a practice version
2. Check timing (must be ≤3 minutes)
3. Verify all screens are readable
4. Ensure audio is clear
5. Check that innovation points are clear

### Upload

- Platform: YouTube (unlisted or public)
- Title: "LLM Incident Commander - Datadog Observability Challenge"
- Description: Include GitHub repo link
- Add to README.md after upload
