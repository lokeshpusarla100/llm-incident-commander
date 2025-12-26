# 🏆 AI Accelerate: Google Cloud Partnerships Hackathon

## Datadog Challenge Submission

---

## 📋 About the Hackathon

**Hackathon**: AI Accelerate: Google Cloud Partnerships Hackathon  
**Challenge Track**: Datadog - LLM Observability  
**Team/Participant**: [Your Name]

---

## 🎯 The Challenge

> Using Datadog, implement an innovative end-to-end observability monitoring strategy for an LLM application powered by Vertex AI or Gemini (new or reused). Stream LLM and/or runtime telemetry to Datadog, define detection rules, and present a clear dashboard that surfaces application health and the observability/security signals you consider essential. When any detection rule is triggered, leverage Datadog to define an actionable item (e.g., case, incident, alert, etc.) with context for an AI engineer to act on.

### Requirements Breakdown

| Requirement | Description |
|-------------|-------------|
| **LLM Application** | Build an app powered by Vertex AI or Gemini |
| **Datadog Integration** | Stream telemetry (metrics, logs, traces) to Datadog |
| **Detection Rules** | Define 3+ monitors to detect issues |
| **Dashboard** | Visual dashboard showing app health & signals |
| **Actionable Items** | Auto-create incidents/cases when rules trigger |
| **Context for Engineers** | Include runbooks and investigation context |

---

## 💡 The Problem We're Solving

### LLM Applications Need Specialized Observability

Traditional application monitoring doesn't capture the unique challenges of LLM applications:

1. **Unpredictable Latency** - LLM response times vary wildly (100ms to 30s+)
2. **Token Costs** - Every request has a real dollar cost that needs tracking
3. **Quality Degradation** - LLMs can "hallucinate" or give uncertain responses
4. **Quota Limits** - API rate limits can silently break production
5. **No Traditional Errors** - A wrong answer isn't an "error" in the HTTP sense

### The Gap

- **DevOps teams** see HTTP 200s but miss quality issues
- **AI Engineers** lack visibility into production model behavior
- **Finance teams** can't track LLM spend
- **Users experience issues** before anyone knows

---

## ✅ Our Solution: LLM Incident Commander

### What We Built

A **simple AI chatbot** powered by **Google Vertex AI (Gemini 2.0 Flash)** with **comprehensive Datadog observability**:

```
┌─────────────────────────────────────────────────────────┐
│                    USER-FACING                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │         LLM Incident Commander                   │   │
│  │         (Clean Chatbot Interface)                │   │
│  │                                                  │   │
│  │   "Ask me about incidents, troubleshooting..."   │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                BEHIND THE SCENES                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Datadog Observability               │   │
│  │  • APM Traces    • Custom Metrics                │   │
│  │  • Structured Logs • 4 Detection Rules           │   │
│  │  • 3 SLOs         • Incident Management          │   │
│  │  • Dashboard       • Case Management             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### How It Works

1. **User** asks a question in the chatbot
2. **FastAPI backend** sends request to Vertex AI (Gemini)
3. **ddtrace** captures APM traces automatically
4. **Custom metrics** emitted via StatsD: latency, tokens, cost, hallucination score
5. **Structured logs** with trace correlation
6. **Datadog monitors** evaluate thresholds continuously
7. **When triggered** → Auto-create Incident or Case with full context

---

## 🔍 Observability Strategy

### LLM-Specific Metrics We Track

| Metric | Why It Matters |
|--------|----------------|
| `llm.latency.ms` | User experience - slow responses frustrate users |
| `llm.tokens.total` | Cost tracking - tokens = money |
| `llm.cost.usd` | Budget monitoring and chargeback |
| `llm.hallucination.score` | Quality - uncertain responses need human review |
| `llm.errors.total` | Reliability - API failures, quota exhaustion |

### 4 Detection Rules (Monitors)

| # | Monitor | Threshold | Action |
|---|---------|-----------|--------|
| 1 | **High Latency** | Avg > 2000ms for 5min | Create SEV-3 Incident |
| 2 | **Error Rate** | > 5% in 5min | Create SEV-2 Incident |
| 3 | **Hallucination Score** | > 0.7 for 10min | Create Case for AI Team |
| 4 | **Quota Exhaustion** | 10+ quota errors in 15min | Create SEV-1 Incident |

### 3 SLOs

| SLO | Target | Error Budget |
|-----|--------|--------------|
| **Availability** | 99% over 30 days | ~7.2 hours/month |
| **Latency P95** | < 2s over 7 days | 5% of requests |
| **Error Rate** | < 1% over 7 days | 1% of requests |

---

## 🚀 Innovation Highlights

### 1. Hallucination Detection Metric 🧠
We built a custom algorithm that scores LLM responses for uncertainty:
- Detects phrases like "I think", "maybe", "I'm not sure", "could be"
- Scores from 0.0 (confident) to 1.0 (highly uncertain)
- Creates **Cases** (not Incidents) for AI team review

### 2. Cost Tracking Per Request 💰
Every request includes estimated cost:
- Based on actual token usage
- Uses Gemini 2.0 Flash pricing
- Enables budget alerts and chargeback

### 3. Context-Rich Incidents 📋
When monitors trigger, incidents include:
- Direct links to APM traces
- Relevant log entries
- Actionable runbooks
- Recent deployment info

### 4. Intelligent Alert Severity 🚨
- **Incidents** for urgent issues (latency, errors, quota)
- **Cases** for quality issues (needs review, not urgent)

---

## 📁 Project Structure

```
llm-incident-commander/
├── app/                    # FastAPI application
│   ├── main.py             # Main app with Vertex AI + Datadog
│   ├── config.py           # Configuration
│   └── logging_config.py   # Structured logging
├── templates/              # Simple chatbot UI
├── static/                 # CSS/JS
├── traffic-generator/      # Test traffic generator
├── datadog-config/         # Exported Datadog configs
│   ├── monitors/           # 4 monitor JSONs
│   ├── slos/               # 3 SLO configs
│   └── dashboards/         # Dashboard JSON
├── screenshots/            # Demo screenshots
├── HACKATHON.md            # This file
└── README.md               # Full documentation
```

---

## ✅ Challenge Checklist

- [x] LLM Application powered by Vertex AI (Gemini 2.0 Flash)
- [x] Datadog integration with ddtrace
- [x] 4 Detection Rules (exceeds 3+ requirement)
- [x] 3 SLOs with error budgets
- [x] Dashboard with health and observability signals
- [x] Incident Management automation
- [x] Case Management for quality issues
- [x] Context-rich actionable items with runbooks
- [x] Traffic generator to demonstrate monitors
- [x] Exported Datadog configurations (JSON)
- [ ] 3-minute demo video
- [ ] Screenshots of dashboard, monitors, incidents

---

## 🏃 Quick Start

```bash
# 1. Clone & install
git clone <repo>
cd llm-incident-commander
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Set credentials
export DD_API_KEY="your-key"
export GCP_PROJECT_ID="your-project"
gcloud auth application-default login

# 3. Run
ddtrace-run uvicorn app.main:app --reload

# 4. Generate traffic to trigger monitors
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 600
```

---

## 🤝 Why This Matters

LLM applications are different. They need:
- **Cost visibility** - every token costs money
- **Quality monitoring** - wrong answers aren't HTTP errors
- **Latency SLOs** - user experience depends on fast responses
- **Quota awareness** - rate limits can break production silently

This solution gives AI Engineers the observability they need to run LLMs in production confidently.

---

**Built for AI Accelerate: Google Cloud Partnerships Hackathon | Datadog Challenge**
