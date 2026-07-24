# Fraud Detection System

A live fraud detection demo built for hackathon presentation.

## What it does

- Scores incoming transactions with explainable rule-based signals.
- Detects organized fraud rings by linking users through shared devices.
- Streams live results to a React dashboard via WebSockets.
- Provides human-readable AI explanations for flagged alerts.
- Lets analysts mark false positives and re-fire alert webhooks.
- sends alert to admin/user on whatsapp or telegram for fraud transactions

## Why it stands out

- **Hybrid detection**: combines per-transaction rules with a graph-based ring detector.
- **Live demo-ready**: synthetic generator creates normal and anomalous traffic instantly.
- **Explainability**: flagged alerts include raw signals plus an optional LLM summary.
- **Analyst workflow**: real-time alerts, feedback tracking, and manual webhook replay.

## Repository layout

- `engine/` - FastAPI backend, fraud rules, ring detection, LLM explainer, API endpoints.
- `FE/` - React dashboard with live feed, alert panel, graph visualization, and feedback buttons.
- `generator/` - Synthetic transaction stream simulator for live demo scenarios. this can be run manually also. but its beging trigger from n8n telegram trigger. so I just send a message on telegram or whatsapp and it generates the transactions

## Setup

1. Clone the repo.
2. Create a Python environment and install backend dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Install frontend dependencies and run the dashboard:
   ```powershell
   cd FE
   npm install
   npm run dev
   ```

## Environment variables

Create a `.env` file in the repository root with the following values:

```text
OPENAI_API_KEY=your_openai_api_key
N8N_WEBHOOK_URL=https://example.com/webhook
ENGINE_URL=http://localhost:8000/transactions
SUPABASE_URL=https://url.supabase.co
SUPABASE_KEY=key
```

- `OPENAI_API_KEY` enables human-like alert explanations.
- `N8N_WEBHOOK_URL` enables webhook alert delivery.
- `ENGINE_URL` can be overridden for the generator.

## Running the backend

From the repo root:

```powershell
uvicorn engine.main:app --reload --port 8000
```

The backend exposes:

- `POST /transactions` - ingest a transaction
- `POST /feedback` - submit analyst feedback
- `POST /alertflag` - re-fire the alert webhook
- `GET /graph` - graph snapshot
- `GET /stats` - runtime metrics
- `GET /health` - status check
- `WS /ws` - live dashboard stream
-  GET /auth/statusAuth Status
-  POST /auth/signin Auth Signin
-  POST /auth/signup Auth Signup
-  GET /auth/me Auth Me
-  POST /demo/ring    Demo Ring Attack
-  GET  /rule-settingsGet Rule Settings Endpoint
-  POST /rule-settingsSave Rule Settings Endpoint
-  POST /demo/anomaly    Demo Anomaly Injection
-  GET /supabase-status Supabase Status
-  GET /transactions/history Transactions History
-  GET / Root - just to show backend is running

## Running the generator

From `generator/`:

```powershell
python generate.py
```

The generator emits a live stream of synthetic users and anomalies, including fraud rings and transaction-level outliers.

## Recommended hackathon demo flow

1. Start the backend and frontend.
2. Start the generator to feed live transactions.
3. Watch the live feed and alert cards appear in real time.
4. Highlight a ring alert and show how multiple users are linked by the same device.
5. Confirm or dismiss alerts to show analyst feedback tracking.
6. Optionally, show `n8n` webhook delivery via `N8N_WEBHOOK_URL`.

## Improvement focus

- Add a summary metrics panel to the dashboard.
- Improve the ring graph with hover details and highlighted clusters.
- Add a demo control panel for one-click anomaly injection.
- Persist feedback history for stronger analyst review metrics.

## Notes

- This project is optimized for live hackathon demos, not production deployment.
- The backend currently uses in-memory state for rules and graph detection.
- The LLM explanation layer gracefully falls back when an API key is not configured.
