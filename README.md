# ChargeWise AI

**For fleet and depot managers: get every van ready using less shared site power.** Compare charging policies, check the smallest configuration that serves a roster, and replan when a charger fails or prices change.

React/Vite, Tailwind, Recharts, FastAPI, Pandas and OR-Tools SCIP. Optional NVIDIA Nemotron uses typed tools; an independent validator certifies every plan before it is shown. No physical charger is controlled.

## Run the demo

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ or 24+. No API key, model download or payment is needed for the planning demo or local computed summaries.

```powershell
uv run --locked python scripts/run_demo.py
```

Open **http://127.0.0.1:8000** and click **Start guided demo**. The launcher builds the frontend when needed. Stop with Ctrl+C; restart with the same command. Use `--no-browser` or `--port 8001` as needed. API documentation: `/docs`.

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

Alternatively, use an ignored `.env` based on `.env.example` for Nebius Token Factory or Hugging Face. Nebius is preferred over HF; explicitly configured self-hosted inference takes precedence. Keys stay server-side. The agent can only mutate the simulation when **Allow simulation changes** is enabled; OR-Tools produces plans and the validator checks them.

The credential-free demo does **not** establish NVIDIA model execution on Nebius. A qualifying hackathon submission still needs a real NVIDIA model runtime on Nebius, a working public demo/test-build URL and a recording of the actual integration. Cloud GPU execution has not been verified or provisioned from this laptop. The [deployment guide](deployment/deployment-guide.md) includes a key-free cloud-host path.

## Verify and deploy

```powershell
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/validate_data.py --external
```

The root `Dockerfile` packages the full app on port 8080. `docker build -t chargewise .` then `docker run --rm -p 8080:8080 chargewise`. Docker/cloud execution remains to be smoke-tested where an engine/account is available; native app tests and frontend builds are checked locally.

The [historical evaluation](docs/evaluation.md) is exploratory and revision-specific; it does not establish current fleet savings or a 95% readiness guarantee. Calibrated chance-constrained MPC, forecasting, OCPP actuation, PV/storage and V2G are not implemented.

Application code/generated fixtures: [MIT](LICENSE). External datasets keep their own notices and terms. Python/frontend dependencies are locked; model weights, credentials and private uploads are excluded from Git.
