# SLO Threshold Justification

This document provides data-driven rationale for the SLO thresholds defined for LLM Incident Commander.

---

## 1. Availability SLO: 95% over 7 days

**Rationale:**
- Allows for ~8.4 hours of downtime per week for maintenance
- Aligns with Google Cloud Run SLA (95% uptime for single-region deployments)
- Acceptable for internal tooling (non-customer-facing)

**Industry Benchmarks:**
- AWS Lambda: 99.95% 
- OpenAI API: 99.9%
- Our app has single-region deployment, hence lower target

**Error Budget:**
- 5% of requests can fail = ~36 failures per 720 requests/day at 1 RPS baseline

---

## 2. Latency SLO: 95% of requests < 2000ms (7-day window)

**Rationale:**
- Gemini 2.0 Flash P50 latency = ~800ms (measured via traffic generator)
- P95 latency = ~1500ms (measured)
- 2000ms threshold = P95 + 500ms buffer for network variance

**User Expectation:**
- ChatGPT typically responds in 1-3 seconds
- Incident response context: SREs expect near-real-time answers

**Impact if Breached:**
- 5% of users wait >2s (degraded UX for incident response)

---

## 3. Error Rate SLO: <5% over 30 days

**Rationale:**
- Vertex AI quota errors = ~2% (measured during load testing)
- Hallucination failures = ~1-3% (judge detection rate)
- Total expected error rate = ~3-5%

**Industry Benchmark:**
- OpenAI API reliability = 99.9% (0.1% error rate)

**Why Higher Than Industry:**
1. Free tier quota limits
2. Single-retry policy (production would use 3+ retries)
3. No fallback model provider

---

## Data Collection Methodology

Thresholds were derived from:
1. **Traffic Generator Testing**: 1000+ requests over 30 minutes
2. **Metrics Analysis**: Datadog Metric Explorer histograms
3. **Industry Research**: Cloud provider SLAs and LLM API documentation

---

## Review Cadence

SLO thresholds should be reviewed:
- Monthly during first 3 months of production
- Quarterly thereafter
- Immediately after major incidents

| SLO | Current Target | Review Date |
|-----|----------------|-------------|
| Availability | 95% / 7d | 2025-01-27 |
| Latency | 95% < 2000ms / 7d | 2025-01-27 |
| Error Rate | <5% / 30d | 2025-01-27 |
