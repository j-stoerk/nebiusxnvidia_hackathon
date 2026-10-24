# Review of the retired PDF blueprint

Reviewed 2026-10-24 against the newer workflow. The old three-page `ChargeWise_AI_Project_Blueprint.pdf` was a planning document, not evidence of implemented features. Useful decisions are preserved here and in the workflow/dataset documents before deleting the PDF.

Retired source SHA-256: `e37a60948b6565706fc80fb3c8c973401749a5e94d4de95e827f501eb14665da` (35,824 bytes). The binary is not retained in Git history.

| Original topic | Decision and destination |
| --- | --- |
| Problem, audience, scope | Keep fleet/workplace/campus/operator problem and 50–100 vehicle demo scale in the workflow. Begin with one configurable station; 3–5 stations are an extension. |
| Dashboard and operator workflow | Keep schedule, cost/peak/target metrics, evidence-based agent panel, and disruption demonstration in the workflow. |
| SoC and battery inputs | Keep optional schema and energy conversion in dataset-format.md. Five-column energy-based CSV remains the core input. |
| Architecture | Keep React, FastAPI, OR-Tools, Nemotron and an independent schedule validator. PostgreSQL, Redis, and WebSockets are deferred; memory and HTTP are enough initially. |
| Forecasting | Preserve the forecasting role; evaluate NVIDIA Kumo-Forecast as the alternative in forecasting.md. Correct attribution: TimesFM is Google Research and cannot fulfill the NVIDIA model requirement. Training remains optional. |
| Model roles | Preserve separation: forecasting predicts, Nemotron coordinates, OR-Tools schedules, deterministic validation enforces limits. |
| Dataset plan | Preserve synthetic sessions/station/events/prices and add small, attributed historical slices; documented in data-sources.md. Solar/carbon remain optional. |
| Optimization | Keep slot-based rolling horizon, compatibility, per-connector assignment, capacity, energy shortfalls, fair baseline, optional peak/carbon objectives. |
| Distributed services and resilience | Keep modules in one app; preserve event IDs, schedule versions, duplicate handling, stale update rejection, and outage recovery acceptance criteria. Brokers and distributed deployments are deferred. |
| Evaluation | Keep computed cost, peak, target success, shortfall, optimizer runtime, event recovery; emissions only with matching carbon data. No fixed savings promise. |
| Build phases | Keep core end-to-end flow first. Forecasting is after working optimization and Nemotron, rather than a prerequisite. |
| Four-person split | Preserve as optional work areas in CONTRIBUTING.md; do not assume team size or require four people. |
| Demo and submission | Keep baseline → optimize → explain → outage → replan story. Replace older event assumptions with verified current requirements. |

TimesFM attribution and checkpoint-specific licensing: [official Google Research repository](https://github.com/google-research/timesfm). No checkpoint is selected or downloaded.

No database, local GPU, forecast model, physical charger, multiple-station deployment, or distributed message broker is required for the current MVP. These older aspirations remain documented as extensions rather than silently becoming mandatory work.
