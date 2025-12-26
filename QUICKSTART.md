# Quick Start Guide - LLM Incident Commander

**Get up and running in 15 minutes!**

---

## Prerequisites (5 min)

```bash
# 1. Install gcloud CLI (if not installed)
# https://cloud.google.com/sdk/docs/install

# 2. Authenticate with Google Cloud
gcloud auth application-default login

# 3. Get Datadog API key from https://app.datadoghq.com
# Navigate to: Organization Settings → API Keys → New Key
```

---

## Setup (5 min)

```bash
# Clone repository
git clone <your-repo-url>
cd llm-incident-commander

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
export GCP_PROJECT_ID="forms-e5771"  # Or your project ID
export DD_API_KEY="your-datadog-api-key-here"
export DD_SITE="datadoghq.com"
export DD_SERVICE="llm-incident-commander"
export DD_ENV="production"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION="true"
```

---

## Run (2 min)

```bash
# Terminal 1: Start application
ddtrace-run uvicorn app.main:app --reload

# Terminal 2: Test it
curl http://localhost:8000/health

# Terminal 3: Generate traffic
source venv/bin/activate
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 300
```

---

## Verify Datadog (3 min)

1. Open https://app.datadoghq.com
2. Go to **APM** → **Services**
3. Look for `llm-incident-commander`
4. Check **Metrics** → Explorer for:
   - `llm.requests.total`
   - `llm.latency.ms`
   - `llm.cost.usd`

---

## Next Steps

1. **Configure Monitors:** Follow `datadog-config/CONFIGURATION_GUIDE.md`
2. **Create Dashboard:** Use guide to create comprehensive dashboard
3. **Trigger Monitors:** Use traffic generator scenarios
4. **Capture Screenshots:** Follow `screenshots/README.md`
5. **Record Video:** Use `VIDEO_SCRIPT.md` as guide

---

## Quick Commands Reference

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the status of incident #1?"}'

# Test traffic generator
python3 traffic-generator/advanced_traffic_generator.py --test-connection

# Generate normal traffic
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 300

# Trigger latency alert (7 min)
python3 traffic-generator/advanced_traffic_generator.py --scenario slow_query --rps 3 --duration 420

# Trigger error rate alert (6 min)
python3 traffic-generator/advanced_traffic_generator.py --scenario invalid_input --rps 2 --duration 360

# Trigger hallucination alert (11 min)
python3 traffic-generator/advanced_traffic_generator.py --scenario hallucination_trigger --rps 2 --duration 660
```

---

## Troubleshooting

**No Datadog data?**
- Check `DD_API_KEY` is set
- Verify running with `ddtrace-run`
- Wait 2-3 minutes

**Vertex AI errors?**
```bash
gcloud auth application-default login
```

**Module not found?**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Full Documentation

- **Complete setup:** `DEPLOYMENT.md`
- **Datadog config:** `datadog-config/CONFIGURATION_GUIDE.md`
- **Video guide:** `VIDEO_SCRIPT.md`
- **Project info:** `README.md`

---

**Need help?** Check the full DEPLOYMENT.md guide!
