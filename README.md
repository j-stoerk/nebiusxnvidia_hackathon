# ChargeWise AI

**For fleet and depot managers: get every van ready using less shared site power.** Compare charging policies, check the smallest configuration that serves a roster, and replan when a charger fails or prices change.

React/Vite, Tailwind, Recharts, FastAPI, Pandas and OR-Tools SCIP. Optional NVIDIA Nemotron uses typed tools; an independent validator certifies every plan before it is shown. No physical charger is controlled.

[Architecture film and downloads](https://j-stoerk.github.io/nebiusxnvidia_hackathon/) · [Prebuilt app](https://github.com/j-stoerk/nebiusxnvidia_hackathon/releases/tag/submission-review-2026-10-25). The film explains components, data flow and workflows with animated diagrams. The site walkthrough is recorded separately; the complete editable planner runs from the test build or source below.

## Run the demo

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ or 24+. No API key, model download or payment is needed for the planning demo or local computed summaries.

```powershell
uv run --locked python scripts/run_demo.py
```

Open **http://127.0.0.1:8000** and click **Start guided demo**. The launcher builds the frontend when needed. Stop with Ctrl+C; restart with the same command. Use `--no-browser` or `--port 8001` as needed. API documentation: `/docs`.

**Edit inputs** opens the full scenario editor: add/remove vehicles, edit their UTC windows, energy, SoC, connector and bindings; edit every price interval; configure individual charger kW/availability, site power, efficiency, tariff calendar/prior peaks and cost/peak objective. **Apply & recalculate** validates the complete draft atomically, starts a new simulation, and clears its events/history. Invalid edits preserve the prior scenario and the draft. Calculated outputs remain derived from inputs.

Optimization streams actual baseline/solver/check stages to the browser. Completed baselines appear first; a short browser presentation pause makes fast runs readable. No artificial delay is added to the solver, and reported solver runtime remains actual. The final plan is published after independent validation. The original synchronous `/api/optimize` remains available for tools and batch use.

For development, run `uv run uvicorn backend.app.main:app --port 8000` and `npm run dev --prefix frontend` in separate terminals.

## What to demonstrate

1. **Optimize:** four vans, two fixed 11 kW plugs, 84 kWh requested and 90% efficiency. FCFS, EDF and LLF each peak at 22 kW; OR-Tools meets the same targets at **8.89 kW**.
2. **Check capacity:** the fixture needs both bound ports and **8.89 kW**. Expand **Show capacity proof** for the independently checked candidate and exclusion of the smaller configuration.
3. **Simulate an outage:** CH-01 is unavailable 08:00–12:00 UTC. The planner keeps every target and raises the required peak to **10 kW**.
4. **Change prices and replay:** apply an afternoon price increase, then replay the identical event. Costs are recomputed once; duplicate delivery leaves the plan/version unchanged.
5. **Summarize:** the assistant explains the computed state. Without a model it explicitly says **Local computed summary — no AI model call**.

The synthetic fixture's initial cost is EUR355.87 for each greedy policy versus EUR159.20 optimized. Energy cost increases from EUR21.47 to EUR24.09; incremental demand cost falls from EUR334.40 to EUR135.11. This uses an illustrative EUR15.20/kW/month component, zero prior peak and synthetic EUR energy prices. It is a partial-period scenario calculation, not measured depot savings, an annual bill or evidence of avoided capex.

## Planning contracts

All policies use the same vehicle/charger ratings, connector compatibility, fixed occupancy, availability, site budget, efficiency and optional taper. Vehicles retain their plugs until departure, including idle time. Explicit port bindings and zero-energy occupied sessions remain binding. Constant interval power satisfies a conservative terminal-SoC CC/CV envelope when battery capacity/initial SoC are supplied; this is not a calibrated chemistry model.

The optimizer first minimizes unserved energy, then **energy plus incremental demand cost**. Station settings also offer **lowest peak, then cost**. Demand uses 15-minute mean kW, the declared local month/year and prior peaks. Capacity search uses installed hardware only; incomplete searches are not declared infeasible or proven minimum.

Replanning preserves completed delivery and its original efficiency. `/api/advance` freezes a checked plan up to a selected time. Per-browser workspaces use in-memory state, a four-hour idle expiry and a maximum of 16 workspaces. Mutations use versions; stale writes return 409. Use one backend worker/replica; restarting clears simulations.

CSV formats: [dataset-format.md](docs/dataset-format.md). Original five-column export: [data/charging_sessions.csv](data/charging_sessions.csv). Ready-to-upload fixture: [data/demo/prepared/](data/demo/prepared/). Real datasets: [vehicle/operator measurements](data/external/real/), [Caltech requests and German prices](data/external/required/), [Office 1 sessions](data/external/acn/). [Source notices and limits](docs/data-sources.md) distinguish measured observations, configured equipment and synthetic assumptions. Private operator uploads stay ignored.

## Optional NVIDIA Nemotron

To avoid inference API tokens, run Nemotron on the **same GPU host** and set `NEMOTRON_BASE_URL=http://127.0.0.1:8001/v1` and the exact NVIDIA `NEMOTRON_MODEL`. Only loopback self-hosted endpoints are accepted; no Authorization token is sent. See [Nebius GPU deployment](deployment/deployment-guide.md).

For live Token Factory inference, the launcher asks for a hidden key and keeps it in process memory:

```powershell
uv run --locked python scripts/run_live_demo.py --budget 0.05 --requests 12
```

Open `http://127.0.0.1:8017`. Stop with Ctrl+C to discard the key. **Cloud inference is off by default even when a key is present.** The cumulative allowance is reserved before each request and persists in `.cache/cloud-inference-budget.json`; do not delete/reset it. This is a conservative local guard, not an account-wide provider cap. Only `nvidia/Nemotron-3_5-Lightning` has verified prices; other cloud models/providers fail closed. An ignored `.env` is an alternative for a private server; see `.env.example`. Never bundle a key in a public build. The agent mutates the simulation only when **Allow simulation changes** is enabled.

[Actual runtime evidence](docs/runtime-evidence.json) records a real NVIDIA Nemotron schedule read and authorized outage replan through Nebius Token Factory on 26 October 2026, with no network mocks. The replan passed independent validation, met every target and peaked at 10 kW. Full-app hosting on Nebius is optional when using Token Factory, as the [organizers confirm](https://nebiusglobalaihackathon.devpost.com/details/faqs). The credential-free local summary is always labelled separately. No Nebius GPU VM was provisioned.

## Verify and deploy

```powershell
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/validate_data.py --external
```

The root `Dockerfile` packages the full app on port 8080. `docker build -t chargewise .` then `docker run --rm -p 8080:8080 chargewise`. Native tests and the extracted application build are verified; a Docker engine was unavailable for a container smoke test. Use one worker/replica; keep any inference ledger on persistent storage. [Hosting details](deployment/deployment-guide.md).

The [historical evaluation](docs/evaluation.md) is exploratory and revision-specific; it does not establish current fleet savings or a 95% readiness guarantee. Calibrated chance-constrained MPC, live forecasting, OCPP actuation, PV/storage and V2G are not implemented.

The separate [forecasting experiment](docs/forecasting.md) and [results](docs/forecast-results.json) compare yesterday/week seasonal forecasts with ridge autoregression on 37 held-out days of 2019 German prices. Ridge improves price MAE by 7.4%; in the synthetic four-van replay it improves mean realized energy-only cost by EUR0.0287/day versus yesterday-repeat, or EUR0.0088 with the illustrative demand component. This does not establish current-market performance. Use already published day-ahead prices directly; forecasting is relevant to unpublished horizons. This lightweight run needs no model weights: `uv run python scripts/forecast_benchmark.py`.

The [pretrained-model follow-up](docs/forecast-models.md) actually ran **TimesFM 2.5, Chronos-Bolt Tiny and Small** locally on CPU, then replayed their forecasts through the physical optimizer. Chronos Small lowers price MAE by 29.2% versus ridge; TimesFM improves this fixture's demand-inclusive scenario cost by only EUR0.0025/day versus ridge. Native uncertainty intervals under-cover, and pretraining overlap with the old test period is unknown. Optional model weights/cache stay outside Git on D:; ML libraries remain isolated from the app environment. Live model forecasting is not enabled in the dashboard, and none of these Google/Amazon models substitutes for NVIDIA model use on Nebius.

Application code/generated fixtures: [MIT](LICENSE). External datasets keep their own notices and terms. Python/frontend dependencies are locked; model weights, credentials and private uploads are excluded from Git.
