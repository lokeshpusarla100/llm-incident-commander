# Canonical Incident Walkthrough: The "Token Explosion" 🧨

**Incident ID**: #38
**Severity**: SEV-2 (High)
**Duration**: 14 minutes
**Status**: RESOLVED

## 1. Detection (T+0s)
**Trigger**: `llm-token-explosion-monitor` fired.
**Signal**: Token usage spiked to **4,500 tokens/request** (Baseline: 800).
**Automation**: Datadog Monitor automatically created Incident #38.

## 2. Notification (T+5s)
**Slack Channel**: `#llm-ops-alerts`
**Message**:
> 🚨 **LLM TOKEN EXPLOSION ALERT**
> - Current: 4,500 tokens/req
> - Baseline: 800 tokens/req
> - Breakdown: 4,000 Input / 500 Output
> - **[View Incident #38](https://app.datadoghq.com/incidents/38)**

## 3. Investigation (T+2m)
Responder @lokesh clicked the Incident link.
**Dashboard Analysis**:
- Checked `llm_operational_dashboard` linked in incident.
- Observed **Input Tokens** were the driver (not output loop).
- **Hypothesis**: Vector Search retrieved too many documents or documents were too large.

**Trace Analysis (APM)**:
- Clicked "View Traces" from the Incident timeline.
- Found Trace ID `6321...`
- Span `retrieve_context` showed `context_length: 15000 chars`.
- **Root Cause Confirmed**: A configuration change increased `TOP_K` from 3 to 10.

## 4. Remediation (T+8m)
**Action**: Reverted `VECTOR_SEARCH_K` environment variable from 10 to 3.
**Verification**:
- Redeployed service.
- Watched "Token Throughput" widget on Operational Dashboard.
- Input tokens dropped back to ~800.

## 5. Resolution (T+14m)
**Monitor Status**: Recovered (Green).
**Incident State**: Resolved.
**Metric Cost**: The 14-minute spike cost approx $4.50 (vs $0.80 baseline).

---

## 💡 Why This Matches Production Standards
1.  **Metric-Driven**: Not a user report. Machine detected it.
2.  **Context-Rich**: Incident contained exact token counts and breakdown.
3.  **Integrated**: One-click jumps from Alert -> Incident -> Dashboard -> Trace.
4.  **Financial Impact**: We calculated the exact cost wastage ($3.70 waste).
