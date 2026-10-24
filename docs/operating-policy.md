# Agent and scheduler operating policy

Project-authored demo policy, not a utility tariff, legal standard, or hardware certification.

The backend owns state and validates typed tools. Begin with `get_state`, `get_schedule`, `optimize_schedule`, and `simulate_event`; explanations cite returned metrics, IDs, schedule versions, and relevant slots. `forecast_load` is an optional future tool. Never fabricate successful tool calls or optimizer results. Model/API failure is visible in the UI and does not prevent viewing deterministic results.

The optimizer enforces arrival/departure windows, charger availability/compatibility, per-vehicle and per-charger ratings, one vehicle per connector, one connector per vehicle, and station capacity. Energy shortfalls are explicit variables/outputs. Capacity is never softened to hide infeasibility. Preserve delivery history during re-optimization.

An independent validator checks every resulting schedule before activation. Reject stale state versions and invalid schedules; keep the previous validated schedule marked stale until a valid replacement exists. Apply each event ID once. A request to simulate a price/outage event affects only simulation state; it cannot control real charging equipment.

Compute baseline and optimized metrics with identical vehicle inputs, event state, prices, horizon, capacity, and shortfall accounting. First minimize unmet energy, then charging cost for the MVP; document any additional peak/carbon objective and its weights/units before enabling it. Compare cost only alongside delivered energy so undercharging is never presented as savings.
