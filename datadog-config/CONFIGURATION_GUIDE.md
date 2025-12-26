# Datadog Configuration Guide

Complete step-by-step guide for configuring Datadog monitoring, SLOs, dashboards, and incident management for the LLM Incident Commander application.

---

## Prerequisites

- [ ] Datadog account (free trial: https://www.datadoghq.com/free-trial/)
- [ ] Datadog API key and APP key
- [ ] Application running with `ddtrace-run uvicorn app.main:app --reload`
- [ ] Traffic generator sending requests

## Step 1: Configure Datadog Agent

### Environment Variables

Set these before running your application:

```bash
export DD_API_KEY="your-datadog-api-key"
export DD_SITE="datadoghq.com"  # or datadoghq.eu for EU
export DD_SERVICE="llm-incident-commander"
export DD_ENV="production"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION="true"
```

### Verify APM is Working

1. Run application: `ddtrace-run uvicorn app.main:app --reload`
2. Generate traffic: `python3 traffic-generator/advanced_traffic_generator.py --duration 60`
3. Check Datadog UI → **APM** → **Services** → Look for `llm-incident-commander`

---

## Step 2: Create Monitors (Detection Rules)

### Monitor #1: High Latency Alert

**Purpose:** Detect when LLM response times degrade significantly.

**Configuration:**
1. Navigate to **Monitors** → **New Monitor** → **Metric**
2. **Define the metric:**
   - Metric: `llm.latency.ms`
   - From: `llm-incident-commander`
   - Aggregation: `avg`
3. **Set alert conditions:**
   - Alert threshold: `> 2000` (2 seconds)
   - Warning threshold: `> 1500` (1.5 seconds)
   - Evaluation window: `5 minutes`
4. **Configure notifications:**
   - **Title:** `[High Latency] LLM Incident Commander - Response time degraded`
   - **Message:**
   ```
   ## 🚨 High Latency Detected
   
   The LLM Incident Commander is experiencing degraded response times.
   
   **Current Metrics:**
   - Average latency: {{value}}ms (threshold: 2000ms)
   - Service: {{service.name}}
   - Environment: {{env}}
   
   **Context:**
   - [View APM Traces](https://app.datadoghq.com/apm/services/llm-incident-commander)
   - Time range: {{last_triggered_at}}
   
   **Runbook:**
   1. Check APM traces for slow LLM calls
   2. Review Vertex AI quota usage and limits
   3. Verify network connectivity to Vertex AI
   4. Check if model performance has degraded
   5. Consider implementing rate limiting or caching
   
   **Next Steps:**
   - Investigate root cause using trace data
   - Implement mitigation if quota-related
   - Update detection thresholds if needed
   
   @incident-llm-incident-commander
   ```
   - **Notification channels:** Add incident integration (see Step 5)
5. **Tags:** `service:llm-incident-commander`, `severity:warning`, `category:performance`
6. **Save**

**JSON Export:** See `monitors/high_latency_monitor.json`

---

### Monitor #2: Error Rate Threshold

**Purpose:** Detect when error rate exceeds acceptable levels.

**Configuration:**
1. Navigate to **Monitors** → **New Monitor** → **Metric**
2. **Define the metric:**
   - Create a formula:
     - `a`: `llm.errors.total` (sum)
     - `b`: `llm.requests.total` (sum)
     - Formula: `(a / b) * 100`
   - Time window: `5 minutes`
3. **Set alert conditions:**
   - Alert threshold: `> 5` (5% error rate)
   - Warning threshold: `> 2` (2% error rate)
4. **Configure notifications:**
   - **Title:** `[High Error Rate] LLM Incident Commander - Errors exceeding threshold`
   - **Message:**
   ```
   ## 🚨 High Error Rate Detected
   
   The LLM Incident Commander is experiencing elevated error rates.
   
   **Current Metrics:**
   - Error rate: {{value}}% (threshold: 5%)
   - Service: {{service.name}}
   - Environment: {{env}}
   
   **Context:**
   - [View Error Logs](https://app.datadoghq.com/logs?query=service:llm-incident-commander%20status:error)
   - [View APM Errors](https://app.datadoghq.com/apm/services/llm-incident-commander/errors)
   
   **Common Error Types:**
   - `quota_exceeded`: Vertex AI quota limits hit
   - `timeout`: Requests exceeding timeout threshold
   - `api_error`: Vertex AI API failures
   
   **Runbook:**
   1. Check error logs for error types
   2. Verify Vertex AI service status
   3. Check quota limits in Google Cloud Console
   4. Review recent deployments or changes
   5. Validate authentication credentials
   
   **Next Steps:**
   - Identify primary error type
   - Implement mitigation (increase quota, add retry logic, etc.)
   - Monitor recovery
   
   @incident-llm-incident-commander @pagerduty
   ```
   - **Notification channels:** Create incident + PagerDuty (optional)
5. **Tags:** `service:llm-incident-commander`, `severity:critical`, `category:availability`
6. **Save**

**JSON Export:** See `monitors/error_rate_monitor.json`

---

### Monitor #3: Hallucination Score Alert

**Purpose:** Detect when LLM responses show signs of uncertainty or hallucination.

**Configuration:**
1. Navigate to **Monitors** → **New Monitor** → **Metric**
2. **Define the metric:**
   - Metric: `llm.hallucination.score`
   - Aggregation: `avg`
   - Time window: `10 minutes`
3. **Set alert conditions:**
   - Alert threshold: `> 0.7`
   - Warning threshold: `> 0.5`
4. **Configure notifications:**
   - **Title:** `[Quality Alert] LLM Incident Commander - High hallucination score`
   - **Message:**
   ```
   ## ⚠️ LLM Quality Degradation Detected
   
   The LLM is producing responses with high uncertainty indicators.
   
   **Current Metrics:**
   - Hallucination score: {{value}} (threshold: 0.7)
   - Service: {{service.name}}
   
   **What This Means:**
   The LLM responses contain phrases indicating uncertainty such as:
   - "I think", "maybe", "might be wrong"
   - "not sure", "possibly", "could be"
   
   This may indicate:
   - Model degradation
   - Input quality issues
   - Prompt engineering problems
   
   **Context:**
   - [View Recent Requests](https://app.datadoghq.com/apm/services/llm-incident-commander)
   - [View Logs with High Scores](https://app.datadoghq.com/logs?query=hallucination_score:>0.7)
   
   **Runbook:**
   1. Review sample responses with high scores
   2. Analyze prompt patterns
   3. Check if specific question types trigger this
   4. Consider prompt engineering improvements
   5. Evaluate if model fine-tuning is needed
   
   **Next Steps:**
   - Create case for AI engineering review
   - Collect examples for analysis
   - Consider adjusting temperature or generation parameters
   
   @case-llm-quality-team
   ```
   - **Notification channels:** Create case (not incident)
5. **Tags:** `service:llm-incident-commander`, `severity:medium`, `category:quality`
6. **Save**

**JSON Export:** See `monitors/hallucination_score_monitor.json`

---

### Monitor #4 (Bonus): Quota Exhaustion

**Purpose:** Early warning for Vertex AI quota issues.

**Configuration:**
1. Navigate to **Monitors** → **New Monitor** → **Metric**
2. **Define the metric:**
   - Metric: `llm.errors.total`
   - Filter by tag: `error_type:quota_exceeded`
   - Aggregation: `sum`
   - Time window: `15 minutes`
3. **Set alert conditions:**
   - Alert threshold: `> 10` (more than 10 quota errors)
4. **Configure notifications:**
   - **Title:** `[CRITICAL] LLM Incident Commander - Vertex AI quota exhausted`
   - **Message:**
   ```
   ## 🚨 CRITICAL: Vertex AI Quota Exhausted
   
   The application is repeatedly hitting Vertex AI quota limits.
   
   **Current State:**
   - Quota errors: {{value}} in last 15 minutes
   - Service: {{service.name}}
   
   **Immediate Impact:**
   - Users receiving 429 errors
   - Service degraded/unavailable
   
   **Context:**
   - [Google Cloud Console - Quotas](https://console.cloud.google.com/iam-admin/quotas)
   - [Error Logs](https://app.datadoghq.com/logs?query=error_type:quota_exceeded)
   
   **Runbook:**
   1. Check Google Cloud Console quotas
   2. Request quota increase if justified
   3. Implement rate limiting immediately
   4. Consider queuing requests
   5. Review traffic patterns for abuse
   
   **Immediate Actions:**
   - Enable rate limiting
   - Notify stakeholders of degraded service
   - Request emergency quota increase
   
   @incident-llm-incident-commander @oncall-engineering
   ```
5. **Tags:** `service:llm-incident-commander`, `severity:critical`, `category:quota`
6. **Save**

**JSON Export:** See `monitors/quota_exhaustion_monitor.json`

---

## Step 3: Create Service Level Objectives (SLOs)

### SLO #1: Availability (99%)

**Purpose:** Ensure 99% of requests succeed.

**Configuration:**
1. Navigate to **Service Management** → **SLOs** → **New SLO**
2. **Define SLI:**
   - Type: **Metric-based**
   - Numerator (good events): `llm.requests.total{status:success}`
   - Denominator (total events): `llm.requests.total{*}`
3. **Set target:**
   - Target: `99%`
   - Time window: `30 days (rolling)`
4. **Configure details:**
   - Name: `LLM Incident Commander - Availability`
   - Description: `99% of LLM requests should succeed over a 30-day period`
   - Tags: `service:llm-incident-commander`, `slo:availability`
5. **Set error budget alerts:**
   - Burn rate alert: `> 1%` budget consumed in 1 hour
6. **Save**

**Error Budget:**
- 99% target over 30 days = 1% error budget
- Approximately 7.2 hours of downtime allowed per month

**JSON Export:** See `slos/availability_slo.json`

---

### SLO #2: Latency (95th percentile < 2s)

**Purpose:** Ensure 95% of requests complete within 2 seconds.

**Configuration:**
1. Navigate to **Service Management** → **SLOs** → **New SLO next**
2. **Define SLI:**
   - Type: **Monitor-based**
   - Use Monitor: Create new monitor or use latency monitor
   - Threshold query: `llm.latency.ms{*} < 2000`
   - Target: 95% of requests below threshold
3. **Set target:**
   - Target: `95%`
   - Time window: `7 days (rolling)`
4. **Configure details:**
   - Name: `LLM Incident Commander - Latency (P95)`
   - Description: `95% of requests should complete in under 2 seconds`
   - Tags: `service:llm-incident-commander`, `slo:latency`
5. **Set error budget alerts:**
   - Warn: `> 50%` budget consumed
   - Alert: `> 80%` budget consumed
6. **Save**

**Error Budget:**
- 95% target over 7 days = 5% error budget
- Approximately 8.4 hours of slow requests allowed per week

**JSON Export:** See `slos/latency_slo.json`

---

### SLO #3: Quality (99% error-free)

**Purpose:** Maintain low error rate.

**Configuration:**
1. Navigate to **Service Management** → **SLOs** → **New SLO**
2. **Define SLI:**
   - Type: **Metric-based**
   - Numerator (good events): `llm.requests.total{status:success}`
   - Denominator (total events): `llm.requests.total{*}`
3. **Set target:**
   - Target: `99%`
   - Time window: `7 days (rolling)`
4. **Configure details:**
   - Name: `LLM Incident Commander - Error Rate`
   - Description: `99% of requests should be error-free over 7 days`
   - Tags: `service:llm-incident-commander`, `slo:error-rate`
5. **Set error budget alerts:**
   - Alert: `> 90%` budget consumed
6. **Save**

**JSON Export:** See `slos/error_rate_slo.json`

---

## Step 4: Create Dashboard

### Dashboard: LLM Incident Commander - Observability

**Purpose:** Single pane of glass for application health, SLOs, and incidents.

**Configuration:**
1. Navigate to **Dashboards** → **New Dashboard**
2. **Dashboard Settings:**
   - Name: `LLM Incident Commander - Observability`
   - Description: `Comprehensive observability for LLM Incident Commander application`
3. **Add Widgets:**

#### Row 1: Overview (Timeseries)
- **Widget 1:** Total Requests
  - Metric: `llm.requests.total{*}.as_count()`
  - Visualization: Timeseries
  
- **Widget 2:** Success Rate
  - Formula: `(llm.requests.total{status:success} / llm.requests.total{*}) * 100`
  - Visualization: Query Value
  
- **Widget 3:** Average Latency
  - Metric: `avg:llm.latency.ms{*}`
  - Visualization: Timeseries
  
- **Widget 4:** Active Incidents
  - Source: Incident widgets
  - Filter: `service:llm-incident-commander`, `status:active`

#### Row 2: LLM-Specific Metrics
- **Widget 5:** Token Usage
  - Metrics:
    - `llm.tokens.input`
    - `llm.tokens.output`
    - `llm.tokens.total`
  - Visualization: Stacked area
  
- **Widget 6:** Estimated Cost per Hour
  - Metric: `sum:llm.cost.usd{*}.rollup(sum, 3600)`
  - Visualization: Query Value with threshold
  
- **Widget 7:** Hallucination Score Trend
  - Metric: `avg:llm.hallucination.score{*}`
  - Visualization: Timeseries with threshold line at 0.7

#### Row 3: Performance Metrics
- **Widget 8:** Latency Percentiles
  - Metrics:
    - `p50:llm.latency.ms`
    - `p95:llm.latency.ms`
    - `p99:llm.latency.ms`
  - Visualization: Timeseries
  
- **Widget 9:** Request Rate (RPS)
  - Metric: `llm.requests.total{*}.as_rate()`
  - Visualization: Timeseries
  
- **Widget 10:** Error Rate by Type
  - Metric: `llm.errors.total{*} by {error_type}`
  - Visualization: Stacked bar

#### Row 4: SLO Status
- **Widget 11:** Availability SLO
  - Type: SLO widget
  - SLO: "LLM Incident Commander - Availability"
  - Show: Current status + error budget
  
- **Widget 12:** Latency SLO
  - Type: SLO widget
  - SLO: "LLM Incident Commander - Latency (P95)"
  
- **Widget 13:** Error Rate SLO
  - Type: SLO widget
  - SLO: "LLM Incident Commander - Error Rate"

#### Row 5: Infrastructure & APM
- **Widget 14:** APM Traces
  - Type: APM traces list
  - Service: `llm-incident-commander`
  - Show: Recent traces
  
- **Widget 15:** Log Stream
  - Type: Log stream
  - Query: `service:llm-incident-commander status:error`

4. **Save Dashboard**

**JSON Export:** See `dashboards/main_dashboard.json`

---

## Step 5: Configure Incident Management

### Enable Incident Management Integration

**Purpose:** Automatically create incidents when monitors trigger.

**Configuration:**
1. Navigate to **Integrations** → **Incident Management**
2. **Enable** Incident Management
3. **Configure incident creation:**
   - Go to each monitor created in Step 2
   - Edit monitor → **Notify your team** section
   - Add: `@incident-llm-incident-commander`
   - This creates an incident automatically when the monitor triggers

### Create Incident Templates

1. Navigate to **Service Management** → **Incidents** → **Settings** → **Templates**
2. **Create Template: High Latency Incident**
   ```
   Title: [AUTO] High Latency - LLM Incident Commander
   Severity: SEV-3
   Services: llm-incident-commander
   
   Initial Description:
   Automated incident created due to high latency detection.
   
   Investigation required:
   - Review APM traces
   - Check Vertex AI performance
   - Verify network connectivity
   
   See monitor for full context and runbook.
   ```

3. **Create Template: Error Rate Incident**
   ```
   Title: [AUTO] High Error Rate - LLM Incident Commander
   Severity: SEV-2
   Services: llm-incident-commander
   
   Initial Description:
   Automated incident created due to elevated error rates.
   
   Investigation required:
   - Check error logs
   - Verify Vertex AI service status
   - Review quota limits
   
   See monitor for full context and runbook.
   ```

### Configure Case Management (for quality issues)

1. Navigate to **Service Management** → **Case Management**
2. **Enable Case Management**
3. **Configure for quality monitor:**
   - Edit "Hallucination Score Alert" monitor
   - Change notification to: `@case-llm-quality-team`
   - Cases are created instead of incidents (lower severity)

---

## Step 6: Export Configurations

### Export Monitors

```bash
# Use Datadog API to export monitors
curl -X GET "https://api.datadoghq.com/api/v1/monitor/<MONITOR_ID>" \
  -H "DD-API_KEY: ${DD_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" > monitors/monitor_name.json
```

### Export SLOs

```bash
curl -X GET "https://api.datadoghq.com/api/v1/slo/<SLO_ID>" \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" > slos/slo_name.json
```

### Export Dashboard

1. In Datadog UI: Dashboard → **Settings** (gear icon) → **Export Dashboard JSON**
2. Save to `dashboards/main_dashboard.json`

---

## Step 7: Test & Validate

### Generate Test Traffic

```bash
# Run normal traffic for baseline
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 300

# Trigger latency alert (slow queries)
python3 traffic-generator/advanced_traffic_generator.py --scenario slow_query --rps 3 --duration 400

# Trigger error alert (invalid inputs)
python3 traffic-generator/advanced_traffic_generator.py --scenario invalid_input --rps 2 --duration 300

# Trigger hallucination alert
python3 traffic-generator/advanced_traffic_generator.py --scenario hallucination_trigger --rps 2 --duration 600
```

### Verify Monitors Trigger

1. Wait 5-15 minutes for monitors to evaluate
2. Check **Monitors** → View triggered monitors
3. Verify incidents/cases created
4. Check dashboard for data visualization

### Validate Incidents

1. Navigate to **Service Management** → **Incidents**
2. Verify incidents have:
   - Correct title and severity
   - Context (metrics, traces, logs)
   - Runbook information
   - Service tags

---

## Step 8: Documentation

### Screenshot Checklist

Capture screenshots for submission:
- [ ] Dashboard showing all metrics
- [ ] List of monitors with their status
- [ ] SLO summary page
- [ ] Example incident with full context
- [ ] APM traces
- [ ] Log analysis

### Datadog Organization Info

**Organization Name:** `[Your Datadog Org Name]`
**Organization URL:** `https://app.datadoghq.com/organization-settings/`

---

## Troubleshooting

### Metrics not appearing in Datadog

**Check:**
1. `DD_API_KEY` environment variable is set
2. Application running with `ddtrace-run`
3. StatsD is sending metrics (check app logs)
4. Datadog Agent is running (if using Agent)

**Debug:**
```bash
# Check ddtrace logs
cat ddtrace-debug.log
```

### Monitors not triggering

**Check:**
1. Traffic generator is running
2. Metrics are appearing in Datadog (Metrics Explorer)
3. Monitor query is correct
4. Evaluation window has passed

### Incidents not being created

**Check:**
1. Incident Management integration is enabled
2. Monitor notification includes `@incident-*`
3. Monitor has triggered (check monitor history)

---

## Next Steps

After completing configuration:

1. ✅ Let monitors collect data for 1-2 hours
2. ✅ Trigger all monitors with traffic generator
3. ✅ Capture screenshots of triggered incidents
4. ✅ Export all JSON configurations
5. ✅ Update main README with Datadog org name
6. ✅ Record 3-minute video walkthrough

---

## Support Resources

- [Datadog APM Documentation](https://docs.datadoghq.com/tracing/)
- [Monitor Configuration](https://docs.datadoghq.com/monitors/)
- [SLO Setup Guide](https://docs.datadoghq.com/service_management/service_level_objectives/)
- [Incident Management](https://docs.datadoghq.com/service_management/incident_management/)
