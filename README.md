# ChargeWise AI

ChargeWise helps **fleet and depot managers** plan shared EV charging within a limited site power supply. See which vehicles a plan can charge before departure, what it costs, and how it handles a charger outage.

Compare **FCFS, earliest-deadline-first (EDF), least-laxity-first (LLF), and OR-Tools** using installed charger ratings, fixed plugs, vehicle limits and shared site power. See which vehicles will be ready, then check the smallest configuration that covers the roster. Capacity proof remains available under a short result; no avoided capex is claimed without site data and quotes.

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

1. Open **Guided demo**: four-vans depot day → optimize → outage → price change → duplicate replay. The fixed-plug fixture meets all energy targets. All three greedy policies peak at 22 kW; OR-Tools reduces the peak to 8 kW with the illustrative demand tariff.
2. Verify replay keeps the state and schedule versions unchanged. Advance time to preserve completed charging, then change station capacity.
3. Load the **100-session stress case**: unserved energy must remain visible. Upload an invalid CSV to check actionable errors, then the downloadable sample to recover.
4. With Nebius configured, ask **AI operations** to explain the comparison or risks. Enable simulation changes only when testing agent actions. No AI key is required for steps 1–3.
5. Inspect the four-strategy comparison, then **Check capacity**. The result is **two fixed plugs and 8 kW** for this synthetic roster. Expand **Show capacity proof** for independent checks, minimum-power proof and any time limits. Station settings accept a verified demand price, billing period and prior peak.
6. The fixture uses the published €15.20/kW/month capacity component with synthetic energy prices and no earlier billing peak. It demonstrates a demand-cost tradeoff, not a measured depot saving. The retained 50/100-session legacy fixtures explicitly assume vehicles can be moved; uploads and saved operator settings use fixed connections. The 50-session fixture cannot meet every target on ten fixed plugs.

CSV contracts and retained dataset provenance: [dataset-format.md](docs/dataset-format.md), [data-sources.md](docs/data-sources.md). Downloads are available in the app. External/reference datasets are retained; the default demo uses the small synthetic fixtures.

To acquire the real-world inputs mapped to the original design, run `uv run python scripts/acquire_required_data.py`. The [field-by-field coverage](docs/data-sources.md#original-designs-required-inputs) distinguishes recorded request parameters, published equipment limits, actual German prices and missing vehicle/fault telemetry. The six-month pack stays outside Git and uses about 2.3 MB.

## Implementation

- `frontend/src/`: small React views, shared controls, and `useWorkspace.ts` for API transactions.
- `backend/app/api/`: HTTP routes; `models.py`: validated contracts.
- `backend/app/services/`: CSV ingestion, analytics, FCFS/EDF/LLF/OR-Tools, taper, tariffs, capacity studies, independent validation, and versioned state.
- `backend/app/ai/`: bounded Nemotron tool loop through Nebius.

The optimizer first minimizes unserved battery energy, then energy plus incremental demand cost without worsening shortfall. Demand uses 15-minute meter averages and local month/year boundaries (Europe/Berlin by default), including prior billing peaks. Optional capacity/SoC fields enable a conservative two-stage CC/CV envelope valid throughout each constant-power interval. Missing telemetry retains a constant-power model. Schedules activate only after independent validation. Fixed plugs are the default; optional CSV `charger_id` records an actual physical binding. A charger outage never authorizes moving a bound vehicle. No physical charger is controlled.

Workspaces are separate, memory-only simulations (up to 16, four-hour idle expiry). Use one backend process; restarting loses sessions. Dispatch timestamps are UTC, prices EUR/kWh, and the 15-minute grid is refined at availability/event boundaries. Capacity studies and typed roster/counterfactual tools are read-only; changing a proposal's source text is never treated as a validated semantic interpretation.

## Real-data evaluation

[Evaluation protocol and hypotheses](docs/evaluation.md) distinguish the implemented planning demo from outstanding research/control work. The proposed niche is **auditable depot capacity decisions**, rather than generic smart charging already offered commercially.

The [ACN website](https://ev.caltech.edu/dataset) offers JSON exports separately from its authenticated API. Import a website export without installing the client or supplying a token:

```powershell
uv run python scripts/fetch_acn.py --json PATH_TO_EXPORT.json --site office001 --output data/external/acn/office001.csv
```

For the official Python client, configure `ACN_API_TOKEN` in `.env`, then fetch six months without raw time series, personal IDs, or permanent extra demo dependencies:

```powershell
uv run --with acnportal==0.3.3 python scripts/fetch_acn.py
uv run python scripts/evaluate.py --sessions data/external/acn/caltech_2019_h1.csv --prices PATH_TO_MATCHING_EUR_PRICES.csv --station PATH_TO_VERIFIED_STATION.json
```

Acquisition writes a small normalized CSV into ignored `data/external/`. A 131 KB Office 1 snapshot (1,481 visits, 2019–2021) is available locally from a public research mirror; direct Caltech connections timed out. Its provenance distinguishes the mirror from an official download. The evaluator requires a clean Git revision, acquisition checksum and matching prices; it records protocol/input hashes, chronological splits, conformal coverage/widths/pinball loss, and paired seven-day-block bootstrap intervals. Replay preserves overnight energy and separate billing peaks. ACN workplace delivered energy/unplug times are retrospective proxies, not depot duty cycles or online inputs. Conformal bounds are an offline baseline; calibrated chance-constrained MPC, OCPP, PV/storage and V2G are not implemented. No 95% readiness claim is made.

The [first exploratory replay](docs/evaluation.md#first-exploratory-result) is complete: 188 held-out calendar days, paired FCFS/EDF/LLF comparisons, seven-day-block confidence intervals and prediction evaluation. It does **not** establish mean daily peak reduction or equal-energy cost savings; prediction intervals are too wide for a useful readiness promise. Full daily output stays ignored; the compact evidence summary is tracked.

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
