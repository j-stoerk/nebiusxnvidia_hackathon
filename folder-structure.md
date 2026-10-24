# ChargeWise AI — Project Folder Structure

## Files present after documentation/data setup

```text
nebiusxnvidia_actual/
  README.md
  CONTRIBUTING.md
  LICENSE
  .gitignore
  .gitattributes
  .env.example
  ChargeWise AI — Project Workflow and Technology Stack.md
  folder-structure.md
  data_sources.txt                  # pointer to verified source registry
  docs/
    hackathon-rules.md
    blueprint-decisions.md
    dataset-format.md
    data-sources.md
    forecasting.md
    operating-policy.md
    storage.md
  data/
    demo/                           # synthetic CSV/JSON inputs + hashes
    reference/                      # small NLR/NASA slices + notices/hashes
    acquisition-report.json         # actual acquisition/access status
    external/                       # ignored downloads; reproducible
  scripts/
    prepare_data.py
    validate_data.py
  workflow-templates/               # inactive; enable through GitHub when desired
    validate-data.yml
    fetch-reference-data.yml
```

The blueprint PDF was retired after its useful decisions were integrated. No backend, frontend, optimizer, forecast service, or database has been implemented. The tree below is the target application layout; create modules when implementing their behavior.

## Target application layout

```text
chargewise-ai/
│
├── README.md
├── .gitignore
├── .env.example

│
├── docs/
│   ├── project-overview.md
│   ├── workflow.md
│   ├── dataset-format.md
│   └── api-documentation.md
│
├── data/
│   └── sample_charging_sessions.csv
│
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── upload.py
│       │   ├── analytics.py
│       │   ├── optimization.py
│       │   ├── simulation.py
│       │   └── agent.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── vehicle.py
│       │   ├── station.py
│       │   ├── schedule.py
│       │   └── events.py
│       │
│       ├── services/
│       │   ├── csv_validator.py
│       │   ├── analytics_service.py
│       │   ├── baseline_scheduler.py
│       │   ├── optimizer.py
│       │   ├── schedule_validator.py
│       │   ├── cost_calculator.py
│       │   ├── simulation_service.py
│       │   └── schedule_service.py
│       │
│       ├── ai/
│       │   ├── nemotron_client.py
│       │   ├── agent.py
│       │   ├── prompts.py
│       │   └── tools.py
│       │
│       └── utils/
│           ├── datetime_utils.py
│           └── response_utils.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── Dockerfile
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   └── client.js
│       │
│       ├── components/
│       │   ├── FileUpload.jsx
│       │   ├── MetricCard.jsx
│       │   ├── EnergyChart.jsx
│       │   ├── CostComparison.jsx
│       │   ├── ChargingTimeline.jsx
│       │   ├── RiskList.jsx
│       │   ├── StationSettings.jsx
│       │   ├── EventSimulator.jsx
│       │   └── AgentChat.jsx
│       │
│       ├── pages/
│       │   └── Dashboard.jsx
│       │
│       ├── hooks/
│       │   └── useChargingData.js
│       │
│       ├── utils/
│       │   └── formatters.js
│       │
│       └── styles/
│           └── global.css
│
├── tests/
│   ├── test_csv_validator.py
│   ├── test_analytics.py
│   ├── test_optimizer.py
│   ├── test_baseline.py
│   ├── test_simulation.py
│   └── test_agent_tools.py
│
└── deployment/
    └── deployment-guide.md
```

## What each part does
Folder/file
Responsibility
data/
Sample CSV for testing and demonstration
api/
Receives frontend requests
models/
Defines vehicles, station settings, schedules, and events
csv_validator.py
Validates uploaded CSV data
analytics_service.py
Calculates dashboard metrics
baseline_scheduler.py
Calculates first-come-first-served comparison
optimizer.py
Uses Google OR-Tools to create charging schedules
cost_calculator.py
Calculates schedule costs
simulation_service.py
Simulates price changes and charger failures
ai/
Connects NVIDIA Nemotron through Nebius and defines agent tools
components/
Dashboard charts, metrics, upload, simulation, and chat UI
tests/
Tests the core features
deployment/
Instructions for publishing the application

How the modules connect
CSV Upload
    ↓
CSV Validation
    ↓
Analytics + Station Settings
    ↓
Baseline Scheduler + OR-Tools Optimizer
    ↓
Dashboard Results
    ↓
Nemotron AI Agent
    ↓
Simulated Event
    ↓
Updated Station/Price Conditions
    ↓
OR-Tools Re-optimization
    ↓
Updated Dashboard + AI Explanation
Recommended implementation order
Create the project and sample CSV.
Build CSV upload and validation.
Implement analytics and station configuration.
Build the OR-Tools optimizer and baseline comparison.
Build the React dashboard and charging timeline.
Integrate Nemotron through Nebius with approved backend tools.
Add simulated events and re-optimization.
Test, deploy, and complete the README and demo.
Important: This is the target structure, not a requirement to create every file immediately. Start with the core files and add modules as their functionality is implemented. Keep uploaded data and schedules in memory for the MVP; a database is unnecessary initially. Never commit real API keys to GitHub.

Preserve the planning tree as a guide. In particular, keep the independent schedule validator separate from optimizer calculations, and add a forecasting adapter only after selecting/testing the model and input contract. See [workflow](ChargeWise%20AI%20%E2%80%94%20Project%20Workflow%20and%20Technology%20Stack.md), [forecasting](docs/forecasting.md), and [blueprint decisions](docs/blueprint-decisions.md).
