# ChargeWise AI

ChargeWise helps **fleet and depot managers** plan shared EV charging within a limited site power supply. See which vehicles a plan can charge before departure, what it costs, and how it handles a charger outage.

The advantage is a checked plan and a fair comparison with first-come-first-served charging: prices, deadlines, and physical limits are considered together, and unavoidable shortfalls remain visible.

Planning demo built with React/Vite, Tailwind CSS, Recharts, FastAPI, Pandas, Google OR-Tools, and NVIDIA Nemotron through Nebius Token Factory.

## Run

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ (or 24+).

One-command guided demo (builds the frontend if needed and opens your browser):

```powershell
uv run --locked python scripts/run_demo.py
```

Use `--no-browser` for a terminal-only launch, `--port 8001` for a different port, or `--host 0.0.0.0` for a Codespaces port forward. The guide uses the existing `data/demo/` inputs and real API/optimizer calls.

Open **http://127.0.0.1:8000**. API documentation: **http://127.0.0.1:8000/docs**.

Stop with **Ctrl+C**. If the browser does not open, use the printed URL. For frontend development, run `uv run uvicorn backend.app.main:app --port 8000` and `npm run dev --prefix frontend` in separate terminals; Vite proxies `/api` to the backend.

## Nemotron

Create an ignored root `.env` using `.env.example`. Set `NEBIUS_API_KEY` and the exact tool-capable NVIDIA Nemotron `NEBIUS_MODEL` available in your Token Factory account. The default base URL is `https://api.tokenfactory.nebius.com/v1`. Restart the backend after configuration changes.

The agent reads state/schedules and can call typed optimization and simulated-event tools when **Allow simulation changes** is enabled. No credentials are sent to the frontend. Without credentials, chat is explicitly unavailable; all deterministic scheduling and simulation features work. Live inference has not been verified without an account key.

## Demo

Suggested story: **a small fleet depot planning charging under limited electrical capacity**. This remains a planning simulation, with no hardware control.

1. Open **Guided demo**: baseline → optimize → outage → price change → duplicate replay. The 50-vehicle fixture meets all energy targets; costs are approximately €166.39 baseline and €164.47 optimized.
2. Verify replay keeps the state and schedule versions unchanged. Advance time to preserve completed charging, then change station capacity.
3. Load the **100-session stress case**: unserved energy must remain visible. Upload an invalid CSV to check actionable errors, then the downloadable sample to recover.
4. With Nebius configured, ask **AI operations** to explain the comparison or risks. Enable simulation changes only when testing agent actions. No AI key is required for steps 1–3.

CSV contracts and retained dataset provenance: [dataset-format.md](docs/dataset-format.md), [data-sources.md](docs/data-sources.md). Downloads are available in the app. External/reference datasets are retained; the default demo uses the small synthetic fixtures.

## Implementation

- `frontend/src/`: small React views, shared controls, and `useWorkspace.ts` for API transactions.
- `backend/app/api/`: HTTP routes; `models.py`: validated contracts.
- `backend/app/services/`: CSV ingestion, analytics, FCFS/OR-Tools scheduling, independent validation, and versioned simulation state.
- `backend/app/ai/`: bounded Nemotron tool loop through Nebius.

The optimizer first minimizes unserved battery energy, then grid electricity cost without worsening that shortfall. It enforces physical limits and reports solver/time-limit status. Schedules activate only after an independent sweep-line validator passes. Savings are reported only when delivered energy matches the baseline. Charging can pause or change compatible connectors at interval boundaries; no physical charger is controlled.

Workspaces are separate, memory-only simulations (up to 16, four-hour idle expiry). Use one backend process; restarting loses sessions. Time is UTC, prices EUR/kWh, and the scheduling grid is 15 minutes, refined at availability/event boundaries. No database, forecasting model, training job, or physical hardware is required for this implementation.

## Forecasting

Use published tariffs directly. Prediction can help for prices beyond the published horizon or future demand. [NVIDIA Kumo-Forecast](https://huggingface.co/nvidia/Kumo-Forecast) is a candidate to evaluate on Nebius against a previous-day baseline using chronological holdouts and realized charging cost. The retained one-week slices are demo inputs, not sufficient evidence of forecast quality. No forecasting model or weights are installed.

## Verify

```powershell
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/validate_data.py
```

Python dependencies are locked in `uv.lock`; frontend dependencies in `frontend/package-lock.json`. Dependencies, model weights, build output, and credentials are ignored by Git.

Project code/generated fixtures: [MIT](LICENSE). Retained external datasets keep their own notices and terms.
