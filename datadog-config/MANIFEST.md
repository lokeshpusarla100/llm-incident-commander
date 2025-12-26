# Datadog Configuration Manifest 📦

This directory contains the export-ready JSON configurations for the LLM Incident Commander.
All assets are production-ready and follow Datadog best practices.

## 📊 Dashboards
| File | Description | ID |
|------|-------------|----|
| [`llm_operational_dashboard.json`](dashboards/llm_operational_dashboard.json) | **Operational Status** - "Safe to Run?" decision support | `llm-incident-commander-ops` |

## 🚨 Monitors (LLM-Specific)
| File | Description | Query Logic |
|------|-------------|-------------|
| [`llm_cost_spike_monitor.json`](monitors/llm_cost_spike_monitor.json) | **Cost Spike** - >50% increase & floor condition | `avg(5m) > avg(1h) * 1.5` |
| [`llm_token_explosion_monitor.json`](monitors/llm_token_explosion_monitor.json) | **Token Explosion** - 2x baseline increase | `avg(5m) > avg(24h) * 2.0` |
| [`llm_hallucination_score_monitor.json`](monitors/llm_hallucination_score_monitor.json) | **Quality Degradation** - High hallucination score | `avg(5m) > 0.7` |
| [`llm_pricing_drift_monitor.json`](monitors/llm_pricing_drift_monitor.json) | **Pricing Drift** - Config mismatch vs official | `log_pattern` |

## 📝 Incident Management
| File | Description | Severity |
|------|-------------|----------|
| [`llm_cost_spike_template.json`](incident_templates/llm_cost_spike_template.json) | Cost spike incident template | SEV-2 |
| [`llm_hallucination_template.json`](incident_templates/llm_hallucination_template.json) | Hallucination quality incident | SEV-3 |

## 🛠 SLOs
| File | Description | Target |
|------|-------------|--------|
| [`llm_latency_slo.json`](slos/llm_latency_slo.json) | P95 Latency < 2s | 99% |
| [`llm_error_rate_slo.json`](slos/llm_error_rate_slo.json) | Error Rate < 1% | 99% |

## Import Instructions
1. **Dashboards**: Dashboards -> Import -> Upload JSON
2. **Monitors**: Monitors -> New Monitor -> Import JSON (via API or manually)
3. **Incidents**: Settings -> Incident Settings -> Templates (requires Incident Management)
