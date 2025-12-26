# Screenshots Checklist

Capture these screenshots for the Datadog hackathon submission.

## Required Screenshots

### 1. Dashboard View
**Filename:** `dashboard.png`

**What to capture:**
- Full Datadog dashboard showing all widgets
- All metrics should have data (run traffic first)
- Include: request rate, latency, errors, tokens, cost, hallucination score
- SLO status widgets visible
- Active incidents widget (if any)
- Time range: Last 1 hour or Last 4 hours

**How:**
1. Navigate to **Dashboards** → "LLM Incident Commander - Observability"
2. Ensure data is visible in all widgets
3. Full-screen browser (F11)
4. Take screenshot
5. Save as `screenshots/dashboard.png`

---

### 2. Monitors List
**Filename:** `monitors.png`

**What to capture:**
- List of all 4 monitors
- Show monitor names, status, and last triggered time
- At least one should show as "Triggered" or "Alert"

**How:**
1. Navigate to **Monitors** → **Manage Monitors**
2. Filter by tag: `service:llm-incident-commander`
3. Screenshot showing all 4 monitors
4. Save as `screenshots/monitors.png`

---

### 3. SLO Status
**Filename:** `slo_status.png`

**What to capture:**
- All 3 SLOs in one view
- Show current status percentage
- Error budget remaining
- Time window

**How:**
1. Navigate to **Service Management** → **SLOs**
2. Filter or scroll to show all 3 LLM Incident Commander SLOs
3. Screenshot
4. Save as `screenshots/slo_status.png`

---

### 4. Incident Example
**Filename:** `incident_example.png`

**What to capture:**
- Full incident details page
- Must show:
  - Incident title and severity
  - Description with context
  - Runbook section
  - Timeline of events
  - Linked APM traces
  - Metrics that triggered it

**How:**
1. Navigate to **Service Management** → **Incidents**
2. Click on a triggered incident (preferably High Latency or Error Rate)
3. Scroll to show full context
4. Take multiple screenshots if needed, or use browser zoom-out
5. Save as `screenshots/incident_example.png`

---

### 5. APM Traces
**Filename:** `apm_traces.png`

**What to capture:**
- APM Service page for llm-incident-commander
- Show traces list with latency breakdown
- Click into one trace to show spans (LLM operation, Vertex AI call)
- Custom span tags (request_id, tokens, cost, etc.)

**How:**
1. Navigate to **APM** → **Services** → `llm-incident-commander`
2. Click **Traces** tab
3. Click on a specific trace to expand spans
4. Screenshot showing span waterfall and tags
5. Save as `screenshots/apm_traces.png`

---

### 6. Error Logs *(Bonus)*
**Filename:** `error_logs.png`

**What to capture:**
- Log stream filtered for errors
- JSON-formatted logs with trace correlation
- Show error type tags

**How:**
1. Navigate to **Logs** → **Live Tail** or **Log Explorer**
2. Filter: `service:llm-incident-commander status:error`
3. Expand one log entry to show full JSON
4. Screenshot
5. Save as `screenshots/error_logs.png`

---

## Before Taking Screenshots

### Generate Traffic and Trigger Monitors

```bash
# 1. Run normal traffic for 2 minutes
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 120

# 2. Trigger latency monitor (7 minutes)
python3 traffic-generator/advanced_traffic_generator.py --scenario slow_query --rps 3 --duration 420

# Wait 5 minutes for monitor to evaluate and trigger

# 3. Trigger error rate monitor (6 minutes)
python3 traffic-generator/advanced_traffic_generator.py --scenario invalid_input --rps 2 --duration 360

# Wait 5 minutes

# 4. Trigger hallucination monitor (11 minutes)
python3 traffic-generator/advanced_traffic_generator.py --scenario hallucination_trigger --rps 2 --duration 660

# Wait 10 minutes
```

**Total time needed:** ~45 minutes (traffic + evaluation windows)

---

## Screenshot Tips

1. **Resolution:** Use 1920x1080 or higher
2. **Browser:** Chrome/Firefox, full-screen mode (F11)
3. **Zoom:** 100% zoom level
4. **Dark/Light Mode:** Consistent across all screenshots (preferably dark mode)
5. **Annotations:** Add arrows or highlights if needed (use tool like Snagit, Greenshot)
6. **File Format:** PNG (high quality, no compression)

---

## Quality Checklist

- [ ] All screenshots are high resolution (not blurry)
- [ ] All text is readable
- [ ] Timestamps visible showing data freshness
- [ ] No sensitive information visible (API keys, personal data)
- [ ] Consistent theme (dark/light) across all screenshots
- [ ] At least one monitor shown as triggered
- [ ] At least one incident visible with full context
- [ ] Dashboard shows meaningful data (not empty widgets)

---

## Usage in Submission

These screenshots will be used for:
1. **Devpost submission** - Visual proof of implementation
2. **README.md** - Embedded examples
3. **Video walkthrough** - Screen recordings or references
4. **Judges' review** - Evidence of working solution

---

## Troubleshooting

### No data in dashboard
- Ensure application is running with ddtrace-run
- Run traffic generator for at least 5 minutes
- Wait 2-3 minutes for data to appear in Datadog

### Monitors not triggered
- Ensure you ran the specific scenario long enough
- Check monitor query in Datadog (Metrics Explorer)
- Wait for evaluation window (typically 5-10 minutes after traffic ends)

### No incidents visible
- Check Incident Management is enabled
- Verify monitor notification includes `@incident-*`
- Check monitor triggered (in Monitors page first)

---

## After Capturing

1. Review all screenshots for quality
2. Rename if needed for clarity
3. Add to git: `git add screenshots/`
4. Commit: `git commit -m "Add demonstration screenshots"`
5. Push to repo for submission

---

**Good luck with your screenshots!** 📸
