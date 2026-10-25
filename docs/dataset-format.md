# Input contracts

## Sessions CSV

UTF-8 (optional BOM), 1–100 rows, at most 2 MiB. One unique vehicle/session ID per upload.

| Column | Contract |
| --- | --- |
| `vehicle_id` | Nonblank, unique, at most 80 characters |
| `arrival_time` | ISO 8601 with explicit timezone, before departure |
| `departure_time` | ISO 8601 with explicit timezone, after arrival |
| `energy_required_kwh` | Finite battery energy, 0–1000 kWh |
| `max_charging_power_kw` | Finite grid-side rate, greater than 0, at most 1000 kW |
| `connector_type` | Optional; defaults to `Type2`; must match a charger to receive power |
| `charger_id` | Optional actual plug binding; must identify a compatible installed charger; overlapping bindings are rejected |
| `battery_capacity_kwh` | Optional; finite, positive, at most 2000; requires `initial_soc` |
| `initial_soc` | Optional fraction 0–1; requires capacity; target cannot exceed battery headroom |
| `transition_soc` | Optional fraction strictly between 0 and 1; defaults to 0.8 |

Reject duplicate/unknown columns, invalid rows, missing offsets, NaN/infinity, and horizons over 72 hours. No SoC inference is performed. With capacity/SoC, acceptance power tapers linearly after transition SoC; constant-power intervals satisfy the terminal ceiling, a conservative approximation. An impossible charging-window target appears as unserved energy; a target exceeding declared battery headroom is invalid input.

## Completing a demo or operator roster

```powershell
uv run python scripts/prepare_depot.py --demo
# Replace the generated example inputs with your own exports/policies, then:
uv run python scripts/prepare_depot.py --input uploads/my-depot --output data/external/my-depot
```

A ready-to-upload snapshot is included in `data/demo/prepared/`. The generator creates `data/external/prepared/example-input/` with a complete four-van `roster.csv`, `prices.csv`, and `station.json`. All missing inputs are explicit synthetic choices: 40 kWh packs, 25% initial SoC, requested 70%/85% targets, 11 kW vehicle limits, two fixed Type 2 plugs, a 22 kW charging budget, and 90% efficiency. The 80% taper transition is an uncalibrated model parameter. Synthetic energy prices and the existing illustrative demand-rate component remain a scenario sensitivity. These choices do not overwrite measured data or change the existing guided demo.

For operator input, `roster.csv` uses the session columns above, accepting an extra `target_soc` fraction. Supply either requested `energy_required_kwh`, or capacity + initial SoC + requested target SoC. The converter calculates battery-side kWh as `capacity * (target_soc - initial_soc)` under the app's linear SoC/energy approximation, and rejects inconsistent dual goals. An observed final SoC or a vehicle type's maximum SoC must not be substituted for a requested target. Use pseudonymous, unique session IDs for repeated vehicle visits. Operator inputs are labelled **operator-supplied, unverified**, not certified measurements.

`station.json` must explicitly declare `simulated`, `station_id`, `station_power_limit_kw`, `charging_efficiency`, and `chargers`; each charger needs an ID, power, connector type and boolean availability. The site limit must be the usable **EV charging budget**, allowing for building load; a connection rating in kVA alone is insufficient. Use the existing demand-tariff object for actual contract terms and prior peaks. Missing top-level station defaults are listed in the output manifest. Prices must be matching-horizon EUR/kWh, not relabelled GBP or wholesale prices presented as a customer contract.

Output contains uploadable `sessions.csv`/`prices.csv`, normalized `station.json`, input/output hashes, assumptions and `comparison.json`. FCFS/EDF/LLF/OR-Tools each pass the independent constraint validator; shortfalls remain explicit. **In the dashboard, first match Station settings to `station.json`, then upload the two output CSVs.** The original roster retains requested SoC; the upload uses the existing energy-target contract. Keep private source files in ignored `uploads/`, and generated packs in ignored `data/external/`.

## Prices CSV

`timestamp,price_eur_per_kwh`. Timezone-aware ISO 8601 timestamps must map to UTC quarter-hour boundaries, with no duplicates and complete coverage of the uploaded session horizon. Maximum 1000 rows/2 MiB. Finite negative prices are supported; range -10 to 100 EUR/kWh. Price upload is optional only when the current series covers the new sessions.

The demo's time-of-use prices are synthetic. The retained OPSD adapter converts wholesale EUR/MWh to EUR/kWh by dividing by 1000, holding each hourly value across four quarters. This is not a current retail tariff.

## Station and scheduling

`data/demo/prepared/station.json` initializes the current four-van demo: 22 kW available EV power, two 11 kW Type 2 chargers, efficiency 0.9, UTC and a 15-minute meter grid. The retained 50/100-session legacy fixture uses its separate 80 kW/ten-port configuration and matching 2019 prices. The station editor supports capacity, efficiency, per-charger ratings/connectors and administrative availability. A recovery event clears a fault; it never enables a port disabled in settings.

`fixed_connections` defaults to true; uploads and saved operator settings enforce it. A served vehicle reserves one compatible physical plug for its entire availability window, including time after charging completes. An explicit `charger_id` reserves that plug even with a zero energy target, and remains binding through an outage. Only the retained 50/100-session legacy simulations explicitly permit moving vehicles. Capacity sweeps select a subset of the actual installed hardware: ratings, connector types, faults, disabled ports, physical bindings and the existing maximum connection power remain enforced. The independent validator also checks the selected physical charger count. An infeasible candidate is distinct from an unresolved timeout; a minimum is marked proven only when both optimization stages finish optimally, within the stated numerical tolerance. The UI keeps the short decision separate from the expandable proof. No quotation or future-duty feasibility follows from a demo candidate.

`demand_tariff` defaults to zero rate: `eur_per_kw`, `period` (`month`/`year`), `timezone` (`Europe/Berlin`/`UTC`), `prior_peaks_kw` (keys `YYYY-MM`/`YYYY`). Meter demand uses 15-minute averages; cost is rate times the increase above each period's prior peak. `cost_eur` is `energy_cost_eur + demand_cost_eur`, a partial-period incremental cost. See the [verified tariff mechanism and exclusions](evaluation.md#tariff-checks). All policy comparisons use the same tariff, history and physics; the dashboard discloses full-information simulation and occupancy assumptions.

Allocations contain vehicle/charger IDs, timezone-aware start/end, grid kW, and efficiency. Battery kWh = kW × duration hours × efficiency. Grid cost = kW × duration hours × EUR/kWh. Availability is half-open `[arrival, departure)`; exact boundaries refine the grid. One vehicle per connector, one connector per vehicle, connector compatibility, ratings, availability, and station capacity are independently checked. Targets may have explicit shortfalls; overcharging is rejected.

## Events and state

`CHARGER_FAILED`: event ID, charger ID, future start/end. `CHARGER_RECOVERED`: event ID, charger ID, recovery time. `PRICE_CHANGED`: event ID, future start/end, additive EUR/kWh adjustment. Events must remain within the scenario horizon.

Mutations require `expected_version`; stale requests return HTTP 409. An identical event replay is ignored, including a retry using the original version. Reusing an ID with different content returns 409. A failed replan retains the prior schedule, visibly stale. Advancing simulation time freezes completed allocations and their efficiency; replanning preserves that ledger.

## Fixtures and provenance

`data/demo/`: deterministic 50-session normal case, 100-session stress case with a deliberately impossible target, station/events, week-long synthetic prices, and SHA-256 manifest. `scripts/prepare_data.py` regenerates these inputs; external acquisitions are opt-in. `scripts/validate_data.py` verifies hashes, schemas, temporal grids, resampling, and available reference data. See [data-sources.md](data-sources.md).
