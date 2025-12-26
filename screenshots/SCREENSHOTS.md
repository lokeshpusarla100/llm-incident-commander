# Submission Screenshots

## Required Screenshots

### 1. Dashboard Overview
![Dashboard](./dashboard_main.png)
- Request rate, latency, token usage, cost tracking
- Hallucination score (keyword + judge)
- SLO status widgets

### 2. Judge Evaluation Results
![Judge Metrics](./judge_metrics.png)
- Hallucination score over time
- Grounding coverage trend
- Contradiction vs unsupported breakdown

### 3. Monitor Triggering
![Monitor Alert](./monitor_triggered.png)
- High hallucination risk detected
- Judge reasoning displayed
- Case created automatically

### 4. APM Trace with Judge Context
![APM Trace](./apm_trace.png)
- Full request lifecycle
- Judge span showing evaluation

### 5. Security Alert
![Security Detected](./security_prompt_injection.png)
- Prompt injection attempt blocked

### 6. SLO Burn-Down
![SLO Chart](./slo_burndown.png)
- Availability SLO tracking
- Error budget consumption

## To Capture These:
1. Generate traffic for 15 minutes
2. Wait for monitors to trigger
3. Screenshot each dashboard/alert
4. Save as .png files in this directory
