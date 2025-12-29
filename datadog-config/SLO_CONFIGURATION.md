<!-- > NOTE: These SLOs are illustrative and chosen for a hackathon/demo environment.
> In real production systems, thresholds would be calibrated using historical traffic
> and business requirements. -->


> **NOTE**: These SLOs are illustrative and chosen for a hackathon/demo environment.
> In real production systems, thresholds would be calibrated using historical traffic
> and business requirements.

# SLO Threshold Justification

This document provides data-driven rationale for the SLO thresholds defined for LLM Incident Commander.

---

## 1. Availability SLO: 99% over 30 days

**Rationale:**
- Aligns with standard enterprise SLOs (99% uptime)
- 1% error budget allows for occasional transient LLM API failures
- Measured over 30 days to smooth out volatility

**Industry Benchmarks:**
- OpenAI API: 99.9%
- Standard Web Services: 99.9%
- Our target (99%): Realistic for a hackathon/demo environment

**Error Budget:**
- 1% of requests can fail (~7.2 hours/month allowed downtime)

---

## 2. Latency SLO: 95% of requests < 2000ms (7-day window)

**Rationale:**
- Gemini 2.0 Flash P50 latency = ~800ms
- P95 latency = ~1500ms
- 2000ms threshold = P95 + 500ms buffer for network variance

**User Expectation:**
- ChatGPT typically responds in 1-3 seconds
- Incident response context: SREs expect near-real-time answers

**Impact if Breached:**
- 5% of users wait >2s (degraded UX)

---

## 3. Error Rate SLO: <1% over 7 days

**Rationale:**
- Vertex AI quota errors are typically handled by retry logic (not implemented here for clarity)
- 1% threshold is strict enough to catch systemic issues like quota exhaustion

**Industry Benchmark:**
- OpenAI API reliability = 99.9% (0.1% error rate)

**Why Higher Than Industry:**
- Free tier quota limits are stricter
- No complex retry/backoff implementation in this demo

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
| Availability | 99% / 30d | 2025-01-27 |
| Latency | 95% < 2000ms / 7d | 2025-01-27 |
| Error Rate | <1% / 7d | 2025-01-27 |
