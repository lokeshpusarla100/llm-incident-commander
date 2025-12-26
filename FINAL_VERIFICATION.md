# Final Verification Checklist ✅

Start your demo or submission with confidence by verifying these 10/10 requirements.

## 1. Compliance (Must Pass)
- [ ] **LICENSE**: Year and Name are correct.
- [ ] **README**: Datadog Organization Name is filled in ("TODO" removed).
- [ ] **README**: Video URL is present.

## 2. Token & Cost Accounting
- [ ] **Logs**: Check app logs for `token_source: gemini_api_usage_metadata`.
- [ ] **Pricing**: Verify `pricing.consistency_validated` log on startup.
- [ ] **Metrics**: In Datadog, confirm `llm.tokens.input` is an exact integer (not estimated).

## 3. Resilience Integration
- [ ] **Code**: Verify `app/routes.py` and `app/datadog_resilience.py` are connected.
- [ ] **Fallback**: If Datadog Agent is down, confirm logs contain "FALLBACK: Emitting to logs".

## 4. Datadog Assets (The "Export Everything" Rule)
- [ ] **Dashboards**: `llm_operational_dashboard.json` exists.
- [ ] **Monitors**: 4+ JSON files in `datadog-config/monitors`.
- [ ] **Incidents**: `llm_cost_spike_template.json` exists.
- [ ] **SLOs**: JSONs in `datadog-config/slos`.

## 5. Incident Lifecycle (The "Walkthrough")
- [ ] **Trigger**: Run traffic generator with `--scenario cost_spike_trigger`.
- [ ] **Observe**: Confirm Incident created automatically (Wait ~2-5 mins).
- [ ] **Context**: Check Incident timeline for "Cost per request > $0.01".

## 6. Documentation
- [ ] **MANIFEST.md**: Clean index of all files.
- [ ] **INCIDENT_WALKTHROUGH.md**: Start-to-finish story present.

## ⚠️ Important Reminder
**Do not submit screenshots.** Submit the **JSON files**. The judges rely on importing your JSONs to verify 10/10 quality.
