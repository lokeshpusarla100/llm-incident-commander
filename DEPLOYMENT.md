# Deployment Guide

Complete step-by-step deployment instructions for LLM Incident Commander.

---

## Prerequisites Checklist

- [ ] Python 3.12 or higher installed
- [ ] Git installed
- [ ] Google Cloud account with billing enabled
- [ ] Datadog account (14-day free trial available)
- [ ] Terminal/command line access

---

## Step 1: Google Cloud Setup (10 minutes)

### 1.1 Create/Select Project

```bash
# Install gcloud CLI if not already installed
# Download from: https://cloud.google.com/sdk/docs/install

# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create YOUR-PROJECT-ID --name="LLM Incident Commander"

# Set as active project
gcloud config set project YOUR-PROJECT-ID
```

### 1.2 Enable Required APIs

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable other required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
```

### 1.3 Configure Authentication

```bash
# Set up application default credentials
gcloud auth application-default login

# This will open a browser for authentication
# Select the account associated with your project
```

### 1.4 Verify Access

```bash
# Test Vertex AI access
gcloud ai models list --region=us-central1

# Should list available models (including gemini models)
```

---

## Step 2: Datadog Setup (15 minutes)

### 2.1 Create Datadog Account

1. Go to https://www.datadoghq.com/free-trial/
2. Sign up for a 14-day free trial
3. Select region (US or EU)
4. Complete email verification

### 2.2 Get API Keys

1. Log into Datadog: https://app.datadoghq.com
2. Navigate to **Organization Settings** → **API Keys**
3. Click **New Key**
   - Name: "LLM Incident Commander"
   - Copy the API key (you'll need this)

### 2.3 Get Application Key

1. Still in **Organization Settings** → **Application Keys**
2. Click **New Key**
   - Name: "LLM Incident Commander App Key"
   - Copy the application key

### 2.4 Enable Integrations

1. Navigate to **Integrations**
2. Search for and install:
   - **APM** (Application Performance Monitoring)
   - **Logs**
   - **Incident Management**
   - **Case Management**

---

## Step 3: Clone and Install (5 minutes)

### 3.1 Clone Repository

```bash
# Clone the repository
git clone <YOUR_REPO_URL>
cd llm-incident-commander
```

### 3.2 Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### 3.3 Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
pip list | grep ddtrace  # Should show ddtrace version
pip list | grep datadog  # Should show datadog version
```

---

## Step 4: Configure Environment (2 minutes)

### 4.1 Environment Variables (Required vs Optional)

The application adheres to 12-factor app principles. Configuration is strictly via environment variables.

| Variable | Status | Description |
|----------|--------|-------------|
| `GCP_PROJECT_ID` | **REQUIRED** | Your Google Cloud Project ID. App will **fail** without this. |
| `DD_API_KEY` | **REQUIRED** | Your Datadog API Key. |
| `DD_SITE` | Optional | Datadog site (default: `datadoghq.com`). |
| `DD_ENV` | Optional | Environment tag (default: `production`). |
| `DD_SERVICE` | Optional | Service name (default: `llm-incident-commander`). |
| `VERTEX_AI_MODEL`| Optional | Model to use (default: `gemini-2.0-flash`). |
| `GOOGLE_APPLICATION_CREDENTIALS` | **REQUIRED (Local)** | Path to service account JSON (not needed in Cloud Run). |

### 4.2 Local Setup (.env)

```bash
# Create .env file (optional, or export directly)
cat > .env << EOF
# Google Cloud
export GCP_PROJECT_ID="YOUR-PROJECT-ID"
export GCP_LOCATION="us-central1"
export VERTEX_AI_MODEL="gemini-2.0-flash"

# Datadog
export DD_API_KEY="your-datadog-api-key-here"
export DD_SITE="datadoghq.com"
export DD_SERVICE="llm-incident-commander"
export DD_ENV="production"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION="true"

# Application
export APP_HOST="0.0.0.0"
export APP_PORT="8000"
EOF

# Load environment variables
source .env
```

### 4.2 Set Variables Directly

```bash
# If not using .env file, export variables directly:

# Google Cloud
export GCP_PROJECT_ID="YOUR-PROJECT-ID"
export GCP_LOCATION="us-central1"
export VERTEX_AI_MODEL="gemini-2.0-flash"

# Datadog
export DD_API_KEY="your-datadog-api-key-here"
export DD_SITE="datadoghq.com"
export DD_SERVICE="llm-incident-commander"
export DD_ENV="production"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION="true"
```

---

## Step 5: Run Application (2 minutes)

### 5.1 Start the Server

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run with Datadog tracing
ddtrace-run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 5.2 Test the Application

Open a new terminal and test:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Should return:
# {
#   "status": "healthy",
#   "service": "llm-incident-commander",
#   "version": "1.0.0",
#   "vertex_ai": "connected",
#   "uptime_seconds": ...
# }

# Test LLM endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the status of incident #1?"}'
```

### 5.3 Access API Documentation

Open browser:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Step 6: Verify Datadog Integration (5 minutes)

### 6.1 Check APM

1. Log into Datadog: https://app.datadoghq.com
2. Navigate to **APM** → **Services**
3. Look for `llm-incident-commander` service
   - May take 1-2 minutes to appear after first request

### 6.2 Check Metrics

1. Navigate to **Metrics** → **Explorer**
2. Search for metrics:
   - `llm.requests.total`
   - `llm.latency.ms`
   - `llm.tokens.total`
   - `llm.cost.usd`

### 6.3 Check Logs

1. Navigate to **Logs** → **Live Tail**
2. Filter by: `service:llm-incident-commander`
3. You should see JSON-formatted logs

---

## Step 7: Generate Traffic (5 minutes)

### 7.1 Test Traffic Generator

```bash
# In a new terminal
source venv/bin/activate

# Test connection
python3 traffic-generator/advanced_traffic_generator.py --test-connection

# Should output:
# ✓ Service is healthy
#   Service: llm-incident-commander
#   Version: 1.0.0
#   Vertex AI: connected
```

### 7.2 Run Mixed Traffic

```bash
# Generate 5 minutes of mixed traffic
python3 traffic-generator/advanced_traffic_generator.py --rps 5 --duration 300

# Watch the output for:
# - Success rate
# - Average latency
# - Token usage
# - Cost per request
```

---

## Step 8: Configure Datadog Monitors (30 minutes)

Follow the detailed guide: `datadog-config/CONFIGURATION_GUIDE.md`

**Quick summary:**
1. Create 4 monitors (latency, error rate, hallucination, quota)
2. Create 3 SLOs (availability, latency, error rate)
3. Create dashboard with all widgets
4. Configure incident management
5. Export all configurations as JSON

---

## Step 9: Test Monitor Triggers (20 minutes)

### 9.1 Trigger Latency Monitor

```bash
# Run slow queries for 7 minutes (5 min threshold + 2 min evaluation)
python3 traffic-generator/advanced_traffic_generator.py \
  --scenario slow_query --rps 3 --duration 420
```

Wait 5-10 minutes, then check **Monitors** page in Datadog.

### 9.2 Trigger Error Rate Monitor

```bash
# Generate errors for 6 minutes
python3 traffic-generator/advanced_traffic_generator.py \
  --scenario invalid_input --rps 2 --duration 360
```

### 9.3 Trigger Hallucination Monitor

```bash
# Generate uncertain responses for 11 minutes
python3 traffic-generator/advanced_traffic_generator.py \
  --scenario hallucination_trigger --rps 2 --duration 660
```

### 9.4 Verify Incidents Created

1. **Monitors** → Check triggered monitors
2. **Incidents** → Verify incidents created with context
3. **Cases** → Check hallucination case
4. **Dashboard** → See visual representation

---

## Step 10: Capture Screenshots (15 minutes)

Create `screenshots/` directory and capture:

```bash
mkdir -p screenshots
```

1. **Dashboard** (full view showing all metrics)
   - Save as: `screenshots/dashboard.png`

2. **Monitors List** (showing all 4 monitors)
   - Save as: `screenshots/monitors.png`

3. **SLO Status** (showing all 3 SLOs)
   - Save as: `screenshots/slo_status.png`

4. **Incident Example** (with full context, runbook, traces)
   - Save as: `screenshots/incident_example.png`

5. **APM Traces** (showing LLM operation spans)
   - Save as: `screenshots/apm_traces.png`

6. **Error Logs** (filtered error logs with context)
   - Save as: `screenshots/error_logs.png`

---

## Step 11: Export Datadog Configurations (10 minutes)

### 11.1 Export Monitors

Using Datadog API or UI:

```bash
# Install jq for JSON formatting
# On Ubuntu/Debian: sudo apt-get install jq
# On Mac: brew install jq

# Set your API and APP keys
DD_API_KEY="your-api-key"
DD_APP_KEY="your-app-key"

# List all monitors
curl -X GET "https://api.datadoghq.com/api/v1/monitor" \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  | jq > datadog-config/monitors/all_monitors.json
```

Or manually from UI:
1. Go to each monitor
2. Click **Export** (or copy JSON from browser DevTools)
3. Save to `datadog-config/monitors/`

### 11.2 Export Dashboard

1. Open dashboard in Datadog
2. Click **Configure** (gear icon) → **Export Dashboard JSON**
3. Save to: `datadog-config/dashboards/main_dashboard.json`

### 11.3 Update README

Edit `README.md` and fill in:
- Datadog organization name
- Video URL (after recording)
- Any specific deployment notes

---

## Step 12: Record Video (30 minutes)

Follow `VIDEO_SCRIPT.md` for detailed script and timing.

### Recording Setup:
1. **Screen Recording**: OBS Studio, QuickTime, or similar
2. **Resolution**: 1920x1080 minimum
3. **Audio**: Clear microphone
4. **Screens Ready**:
   - Dashboard with live data
   - Monitors page
   - Example incident  
   - SLO summary
   - Code snippets

### Upload:
1. Upload to YouTube (unlisted or public)
2. Update `README.md` with video URL
3. Add video URL to Devpost submission

---

## Troubleshooting

### Issue: "Module 'ddtrace' not found"

**Solution:**
```bash
# Verify virtual environment is activated
which python  # Should point to venv/bin/python

# Reinstall ddtrace
pip install ddtrace
```

### Issue: "Vertex AI authentication error"

**Solution:**
```bash
# Re-authenticate
gcloud auth application-default login

# Verify credentials
gcloud auth application-default print-access-token
```

### Issue: "No data in Datadog"

**Solution:**
1. Check `DD_API_KEY` is set correctly
2. Verify application is running with `ddtrace-run`
3. Check logs: `cat ddtrace-debug.log`
4. Wait 2-3 minutes for data to appear

### Issue: "Monitors not triggering"

**Solution:**
1. Ensure traffic generator ran for full duration
2. Check metrics exist in Datadog Metrics Explorer
3. Verify monitor threshold configuration
4. Allow 5-10 minutes for evaluation

---

## Deployment Checklist

- [ ] Google Cloud project created and configured
- [ ] Vertex AI API enabled
- [ ] Datadog account created
- [ ] API and Application keys obtained
- [ ] Repository cloned
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Application running successfully
- [ ] Datadog receiving metrics, traces, and logs
- [ ] 4 monitors created and configured
- [ ] 3 SLOs created
- [ ] Dashboard created with all widgets
- [ ] Incident management configured
- [ ] Traffic generator tested
- [ ] All monitors triggered successfully
- [ ] Screenshots captured
- [ ] JSON configurations exported
- [ ] Video recorded and uploaded
- [ ] README updated with org name and video URL

---

## Next Steps

After deployment:
1. ✅ Let system run for 1-2 hours to collect baseline data
2. ✅ Trigger all monitors using traffic generator
3. ✅ Verify incidents created with proper context
4. ✅ Capture all required screenshots
5. ✅ Record video walkthrough
6. ✅ Complete Devpost submission

---

## Support

**Issues with Google Cloud:** https://cloud.google.com/support  
**Issues with Datadog:** https://docs.datadoghq.com/help/  
**Hackathon Questions:** Check hackathon Discord/Slack

---

**Estimated Total Setup Time: 2-3 hours**

Good luck with your submission! 🚀
