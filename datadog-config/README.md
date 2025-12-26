# Datadog Configuration Guide

This directory contains all Datadog configurations for the LLM Incident Commander project, including monitors, SLOs, dashboards, and incident management setup.

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
