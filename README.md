# ChargeWise AI

EV charging operations demo built with React/Vite, Tailwind CSS, Recharts, FastAPI, Pandas, Google OR-Tools, and NVIDIA Nemotron through Nebius Token Factory.

Upload sessions, compare a first-come-first-served baseline with a validated optimized schedule, inspect costs and deadline risks, and replan after simulated charger or price changes.

## Run

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ (or 24+).

One-command guided demo (builds the frontend if needed and opens your browser):

```powershell
uv run --locked python scripts/run_demo.py
```

Use `--no-browser` for a terminal-only launch, `--port 8001` for a different port, or `--host 0.0.0.0` for a Codespaces port forward. The guide uses the existing `data/demo/` inputs and real API/optimizer calls.

Manual setup:

```powershell
uv sync --locked
npm ci --prefix frontend
npm run build --prefix frontend
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. API documentation: **http://127.0.0.1:8000/docs**.

For frontend development, keep the API running and use `npm run dev --prefix frontend`; Vite proxies `/api` to port 8000.

## Nemotron

Create an ignored root `.env` using `.env.example`. Set `NEBIUS_API_KEY` and the exact tool-capable NVIDIA Nemotron `NEBIUS_MODEL` available in your Token Factory account. The default base URL is `https://api.tokenfactory.nebius.com/v1`. Restart the backend after configuration changes.

The agent reads state/schedules and can call typed optimization and simulated-event tools when **Allow simulation changes** is enabled. No credentials are sent to the frontend. Without credentials, chat is explicitly unavailable; all deterministic scheduling and simulation features work. Live inference has not been verified without an account key.

## Demo

Click **Guided demo** for baseline → optimization → charger outage → price spike → duplicate-event replay. Each step shows actual measured results. AI connection status remains explicit.

Outside the guide, inspect vehicle risks/intervals, advance simulation time to preserve completed charging, configure the station, upload CSVs, or load the 100-session stress case. All simulation controls work without an AI key.

CSV contracts and retained dataset provenance: [dataset-format.md](docs/dataset-format.md), [data-sources.md](docs/data-sources.md). Downloads are available in the app. External/reference datasets are retained; the default demo uses the small synthetic fixtures.

## Implementation

- `frontend/src/`: React dashboard, charts, upload/settings/event forms, and agent panel.
- `backend/app/api/`: HTTP routes; `models.py`: validated contracts.
- `backend/app/services/`: CSV ingestion, analytics, FCFS/OR-Tools scheduling, independent validation, and versioned simulation state.
- `backend/app/ai/`: bounded Nemotron tool loop through Nebius.

The optimizer first minimizes unserved battery energy, then grid electricity cost without worsening that shortfall. It enforces physical limits and reports solver/time-limit status. Schedules activate only after an independent sweep-line validator passes. Savings are reported only when delivered energy matches the baseline. Charging can pause or change compatible connectors at interval boundaries; no physical charger is controlled.

Workspaces are separate, memory-only simulations (up to 16, four-hour idle expiry). Use one backend process; restarting loses sessions. Time is UTC, prices EUR/kWh, and the scheduling grid is 15 minutes, refined at availability/event boundaries. No database, forecasting model, training job, or physical hardware is required for this implementation.

## Verify

```powershell
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/validate_data.py
```

Python dependencies are locked in `uv.lock`; frontend dependencies in `frontend/package-lock.json`. Dependencies, model weights, build output, and credentials are ignored by Git.

Project code/generated fixtures: [MIT](LICENSE). Retained external datasets keep their own notices and terms.
