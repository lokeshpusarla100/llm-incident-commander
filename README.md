# LLM Incident Commander 🚨

> **AI Accelerate: Google Cloud Partnerships - Datadog Challenge**  
> End-to-end observability monitoring strategy for an LLM application powered by Vertex AI with comprehensive Datadog integration.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Datadog](https://img.shields.io/badge/Datadog-632CA6?logo=datadog&logoColor=fff)](https://www.datadoghq.com/)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-4285F4?logo=googlecloud&logoColor=fff)](https://cloud.google.com/)

## 📖 Overview

LLM Incident Commander is a minimal LLM-powered assistant designed to demonstrate how Datadog detects, explains, and escalates failures in production LLM workloads.

> **The application is intentionally simple (a chatbot/assistant); the innovation lies in how Datadog observes, detects, and responds to LLM failures, not in UI complexity.**

The system demonstrates enterprise-grade LLM monitoring:

- **🔍 Full-Stack Observability**: APM traces, structured logs, custom metrics
- **📊 4 Detection Rules**: Monitors for latency, errors, hallucination, and quota
- **🎯 3 SLOs**: Availability (99%), Latency P95 (<2s), Error Rate (<1%)
- **⚡ Incident Management**: Auto-create incidents/cases with rich context
- **💰 Cost Tracking**: Real-time token and cost estimation

---

## 🧑‍💻 User Flow (Minimal by Design)

1. User submits a natural-language request to the assistant (e.g., "Plan a 3-day trip" or "How do I troubleshoot high latency?")
2. FastAPI backend calls Gemini via Vertex AI
3. Datadog traces the full request lifecycle
4. If latency, errors, cost, or quality degrade:
   - A monitor triggers
   - An incident or case is created in Datadog with trace context

---

## 🧠 Why This Is an LLM Application

The core functionality of this system depends on a Large Language Model hosted on Vertex AI (Gemini).
Every user interaction results in an LLM inference whose **latency, cost, reliability, and output quality**
directly affect user experience.

**If the LLM is removed, the application ceases to function.**

Observability is therefore centered on LLM behavior rather than traditional backend metrics.

---

## 🏗️ Architecture

```
┌─────────────────┐
│  User / Traffic │
│   Generator     │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│   FastAPI + ddtrace │ ◄──────── Datadog APM
│  (LLM Application)  │
└────────┬────────────┘
         │
         ├──► Vertex AI (Gemini 2.0 Flash)
         │
         ├──► StatsD ────────► Datadog Metrics
         │
         └──► JSON Logs ─────► Datadog Logs
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Datadog Platform   │
                    ├─────────────────────┤
                    │ • Monitors (4)      │
                    │ • SLOs (3)          │
                    │ • Dashboard         │
                    │ • Incident Mgmt     │
                    │ • Case Management   │
                    └─────────────────────┘
```

> The architecture is intentionally linear to make LLM latency, cost, and failure modes directly observable in Datadog.

---

## ✨ Key Innovations

### 1. **Semantic Hallucination Detection via LLM-as-a-Judge** 🧠 ⭐ NEW

Unlike keyword-based heuristics, we implement **Datadog's recommended LLM-as-a-Judge pattern**:

- **Dual-LLM Architecture**: A secondary Gemini 2.0 Flash instance semantically evaluates every response for accuracy, uncertainty, contradictions, and evasiveness
- **Asynchronous Evaluation**: Zero user-facing latency impact - judge runs in background via `asyncio.create_task()`
- **Structured Output**: Gemini's JSON mode (`response_mime_type: "application/json"`) ensures reliable score extraction
- **Production-Grade Cost Tracking**: Judge tokens and costs tracked separately with dedicated metrics

**Metrics Emitted:**
- `llm.judge.hallucination_score` (0.0-1.0): Semantic accuracy score from judge LLM
- `llm.judge.cost.usd`: Cost of running background evaluations
- `llm.judge.tokens.total`: Token usage for judge prompts + responses
- `llm.judge.high_risk_detected`: Counter incremented when score ≥ 0.7

**How It Works:**
1. User submits question → receives answer immediately (no wait)
2. In parallel, judge LLM analyzes the response with structured criteria
3. Judge emits metrics to Datadog 1-2 seconds later
4. If score ≥ 0.7, creates a **Case** (quality issue, not incident)

**Innovation:**
This aligns with Datadog's LLM Observability product vision ([blog post](https://www.datadoghq.com/blog/ai/llm-hallucination-detection/)), proving enterprise-grade quality monitoring is achievable using Vertex AI alone. The async architecture ensures production-grade performance.

**Legacy Metric:** We kept the original `llm.hallucination.score` (keyword-based) for comparison purposes.

### 2. **Cost Tracking** 💰
Per-request cost estimation based on token usage and Gemini pricing.

### 3. **Context-Rich Incidents** 📝
Auto-created incidents include APM traces, error logs, and runbooks.

### 4. **Traffic Generator** 🎭
Test scenarios for latency, errors, and quality degradation.

### 5. **SLOs with Error Budgets** 🎯
Availability, latency, and error rate SLOs with burn rate tracking.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud account with Vertex AI API enabled
- Datadog account (free trial: https://www.datadoghq.com/free-trial/)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd llm-incident-commander

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Google Cloud

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Set project ID
export GCP_PROJECT_ID="project_id"
```

### 3. Configure Datadog

```bash
# Set Datadog credentials
export DD_API_KEY="your-datadog-api-key"
export DD_SITE="datadoghq.com"  # or datadoghq.eu for EU
export DD_SERVICE="llm-incident-commander"
export DD_ENV="production"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION="true"
```

### 4. Run the Application

```bash
# Start with Datadog tracing
ddtrace-run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

### 5. Generate Traffic

In a new terminal:

```bash
# Activate virtual environment
source venv/bin/activate

# Test connection
python3 traffic-generator/advanced_traffic_generator.py --test-connection

# Generate mixed traffic (normal + scenarios to trigger monitors)
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 600

# Or trigger specific scenarios:

# Trigger latency alert
python3 traffic-generator/advanced_traffic_generator.py --scenario slow_query --rps 3 --duration 400

# Trigger error rate alert
python3 traffic-generator/advanced_traffic_generator.py --scenario invalid_input --rps 2 --duration 300

# Trigger hallucination alert
python3 traffic-generator/advanced_traffic_generator.py --scenario hallucination_trigger --rps 2 --duration 600
```

---

## 📊 Datadog Configuration

### Datadog Organization

**Organization Name**: `TODO: Add your Datadog org name`  
_Note: Update this with your actual Datadog organization name_

### Detection Rules (Monitors)

We have configured **7 monitors** to detect LLM-specific issues:

1. **High Latency Alert** (`monitors/high_latency_monitor.json`)
   - Triggers when avg latency > 2000ms for 5 minutes
   - Creates **Incident** with SEV-3

2. **Error Rate Threshold** (`monitors/error_rate_monitor.json`)
   - Triggers when error rate > 5% in 5 minutes
   - Creates **Incident** with SEV-2

3. **Hallucination Score Alert** (`monitors/hallucination_score_monitor.json`)
   - Triggers when hallucination score > 0.7 for 10 minutes
   - Creates **Case** (not incident) for AI team review
   - ⚠️ *Note: Uses uncertainty phrases as a proxy signal, not a claim of factual correctness*

4. **Quota Exhaustion Alert** (`monitors/quota_exhaustion_monitor.json`)
   - Triggers on 10+ quota errors in 15 minutes
   - Creates **Incident** with SEV-1 (critical)

5. **Prompt Explosion Alert** (`monitors/prompt_explosion_monitor.json`) *[NEW]*
   - Triggers when avg input tokens > 2000 over 5 minutes
   - Detects potential abuse or runaway automation

6. **Cost Spike Alert** (`monitors/cost_spike_monitor.json`) *[NEW]*
   - Triggers when cost per request > $0.01 (30x baseline)
   - Economic protection for budget overruns

7. **LLM Judge Quality Alert** (`monitors/llm_judge_hallucination_monitor.json`) *[NEW] [INNOVATION]*
   - Triggers when Judge AI detects semantic hallucination (score > 0.7)
   - true semantic quality check using Datadog's LLM-as-a-Judge pattern

### Service Level Objectives (SLOs)

1. **Availability SLO** - 99% over 30 days
   - Target: 99% of requests successful
   - Error budget: 1% (~7.2 hours/month)

2. **Latency SLO** - P95 < 2s over 7 days
   - Target: 95% of requests under 2000ms
   - Error budget: 5% (~8.4 hours/week)

3. **Error Rate SLO** - < 1% over 7 days
   - Target: 99% error-free requests
   - Error budget: 1%

### Dashboard

**"LLM Incident Commander - Observability"** includes:
- Request rate, success rate, latency metrics
- Token usage, cost tracking
- Hallucination score trends
- SLO status widgets
- Active incidents list
- APM traces and log streams

See `datadog-config/CONFIGURATION_GUIDE.md` for detailed setup instructions.

---

## 📁 Project Structure

```
llm-incident-commander/
├── app/
│   ├── main.py              # FastAPI application with Vertex AI integration
│   ├── config.py            # Configuration and pricing constants
│   └── logging_config.py    # Structured JSON logging for Datadog
│
├── traffic-generator/
│   ├── advanced_traffic_generator.py  # Advanced traffic generator
│   └── generate_traffic.sh            # Simple bash traffic generator
│
├── datadog-config/
│   ├── monitors/            # Monitor JSON exports (4 monitors)
│   ├── slos/                # SLO configurations (3 SLOs)
│   ├── dashboards/          # Dashboard JSON export
│   ├── CONFIGURATION_GUIDE.md  # Step-by-step Datadog setup
│   └── README.md
│
├── screenshots/             # Screenshots for submission
│   └── (Datadog dashboards, traces, monitors, incidents)
│
├── requirements.txt
├── LICENSE                  # MIT License
└── README.md               # This file

> **Note**: Screenshots focus on Datadog dashboards, traces, monitors, and incidents rather than application UI.
```

---

## 🔬 Observability Strategy

### LLM-Specific Telemetry

Our observability strategy focuses on metrics that matter for LLM applications:

#### **Performance Metrics**
- `llm.latency.ms` - End-to-end latency per request
- `llm.requests.total` - Total request count (by status)
- percentiles (p50, p95, p99) for latency distribution

#### **Cost & Usage Metrics**
- `llm.tokens.input` - Input token count (estimated)
- `llm.tokens.output` - Output token count (estimated)
- `llm.tokens.total` - Total tokens per request
- `llm.cost.usd` - Estimated cost based on Gemini pricing

#### **Quality Metrics**
- `llm.hallucination.score` - Custom metric (0.0-1.0) detecting uncertainty
- `llm.hallucination.high_score` - Counter for responses exceeding threshold

#### **Error Metrics**
- `llm.errors.total{error_type}` - Errors by type (quota, timeout, api_error)

### APM Integration

- **Custom spans** for LLM operations with detailed tags
- **Distributed tracing** showing full request lifecycle
- **Error tracking** with stack traces and context

### Structured Logging

- **JSON logs** with automatic trace correlation
- **Request IDs** for full request tracking
- **Cost and token data** in every log entry

---

## 🧪 Testing Monitors

### Trigger All Monitors

Run this sequence to demonstrate all detection rules:

```bash
# 1. Baseline traffic (1 minute)
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 60

# 2. Trigger latency alert (7 minutes for threshold + evaluation)
python3 traffic-generator/advanced_traffic_generator.py --scenario slow_query --rps 3 --duration 420

# 3. Trigger error rate alert (6 minutes)
python3 traffic-generator/advanced_traffic_generator.py --scenario invalid_input --rps 2 --duration 360

# 4. Trigger hallucination alert (11 minutes for threshold)
python3 traffic-generator/advanced_traffic_generator.py --scenario hallucination_trigger --rps 2 --duration 660
```

Wait 5-10 minutes after each test for monitors to evaluate and check:
- **Monitors** page for triggered alerts
- **Incidents** page for created incidents
- **Cases** page for the hallucination case
- **Dashboard** for visual confirmation

---

## 📹 Demo Video

**Video URL**: `TODO: Add your 3-minute YouTube video URL`  
_3-minute walkthrough covering:_
1. Observability strategy overview
2. Detection rules and rationale
3. Dashboard demonstration
4. Incident creation with full context
5. Innovation highlights

---

## 🏆 Challenge Requirements Checklist

- [x] **LLM Application** powered by Vertex AI (Gemini 2.0 Flash)
- [x] **3+ Detection Rules** (4 monitors configured)
- [x] **3+ SLOs** with error budgets
- [x] **Incident Management** - Auto-create incidents with context
- [x] **Case Management** - Quality issues create cases
- [x] **Dashboard** - Comprehensive observability view
- [x] **JSON Exports** - All Datadog configs in `/datadog-config`
- [x] **Traffic Generator** - Multiple scenarios to trigger monitors
- [x] **README** - Complete deployment instructions
- [x] **Public repo** with MIT License
- [ ] **Video walkthrough** (3 minutes)
- [ ] **Screenshots** showing dashboard, monitors, SLOs, incidents

---

## 🔧 API Reference

### POST `/ask`

Send a question to the LLM.

**Request:**
```json
{
  "question": "What is the status of incident #42?",
  "temperature": 0.7,    // Optional, default: 0.7
  "max_tokens": 512      // Optional, default: 512
}
```

**Response:**
```json
{
  "request_id": "uuid-here",
  "question": "What is the status of incident #42?",
  "answer": "LLM response here...",
  "latency_ms": 1234,
  "tokens": {
    "input": 25,
    "output": 128,
    "total": 153
  },
  "cost_usd": 0.000038,
  "hallucination_score": 0.33
}
```

### GET `/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "llm-incident-commander",
  "version": "1.0.0",
  "vertex_ai": "connected",
  "uptime_seconds": 3600
}
```

---

## 💡 Design Decisions

### Why Gemini 2.0 Flash?
- Fast response times (typically <500ms)
- Cost-effective for production use
- Multimodal capabilities for future enhancements

### Why These Monitor Thresholds?
- **2000ms latency**: Based on user experience research (2s is acceptable for complex queries)
- **5% error rate**: Allows for transient issues while catching systemic problems
- **0.7 hallucination score**: Empirically determined from response analysis

### Why Separate Incidents vs Cases?
- **Incidents** for urgent issues (latency, errors, quota) - require immediate action
- **Cases** for quality issues - need review but not urgent

---

## 🐛 Troubleshooting

### Metrics not appearing in Datadog

**Check:**
1. `DD_API_KEY` is set correctly
2. Application running with `ddtrace-run`
3. Internet connectivity

**Debug:**
```bash
# Check ddtrace debug logs
cat ddtrace-debug.log
```

### Vertex AI authentication errors

```bash
# Re-authenticate
gcloud auth application-default login

# Verify credentials
gcloud auth application-default print-access-token
```

### Monitors not triggering

- Ensure traffic generator has run for sufficient time (5-15 minutes)
- Check metric data is in Datadog (Metrics Explorer)
- Verify monitor query syntax

---

## 📚 Resources

- [Datadog APM Documentation](https://docs.datadoghq.com/tracing/)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini API Reference](https://ai.google.dev/docs)
- [ddtrace Python](https://ddtrace.readthedocs.io/)

---

## 🤝 Contributing

This is a hackathon submission project. Feel free to fork and adapt for your own use cases!

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Lokesh Kumar**  
For the AI Accelerate: Google Cloud Partnerships Hackathon  
Datadog Challenge

**Datadog Organization**: `TODO: Add your Datadog org name`

---

## 🙏 Acknowledgments

- Google Cloud for Vertex AI platform
- Datadog for comprehensive observability platform
- Hackathon organizers and mentors

---

**Built with ❤️ for the AI Accelerate Hackathon**
