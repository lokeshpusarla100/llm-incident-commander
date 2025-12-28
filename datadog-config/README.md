# Datadog Configuration Guide

The `datadog-config/` directory contains **IaC-style JSON exports** of the Datadog dashboards, monitors, and SLOs that were manually created and validated in the Datadog UI.

> This approach mirrors real-world enterprise workflows, where application teams emit telemetry while observability teams define detection and reliability policy declaratively.

**Note:** These JSON files are exported representations of Datadog resources created and validated in the Datadog UI. They are not auto-applied by the application.

## 📋 Contents

- **monitors/** - Detection rules (3+ monitors)
- **slos/** - Service Level Objectives (3 SLOs)
- **dashboards/** - Dashboard JSON exports
- **incident-templates/** - Incident management templates
- **CONFIGURATION_GUIDE.md** - Step-by-step setup instructions

## 🎯 Quick Reference

### Monitors
1. **High Latency Alert** - Triggers when avg latency > 2000ms for 5 minutes
2. **Error Rate Threshold** - Triggers when error rate > 5% in 5 minutes
3. **Hallucination Score Alert** - Triggers when hallucination score > 0.7 for 10 minutes
4. **Quota Exhaustion** (Bonus) - Triggers on repeated quota errors

### SLOs
1. **Availability** - 99% of requests successful over 30 days
2. **Latency** - 95% of requests under 2000ms over 7 days
3. **Quality** - 99% error-free requests over 7 days

### Dashboard
- **LLM Incident Commander - Observability** - Comprehensive health overview

## 📦 Export Instructions

All configurations have been exported as JSON and can be imported into any Datadog organization.

See `CONFIGURATION_GUIDE.md` for detailed setup instructions.
