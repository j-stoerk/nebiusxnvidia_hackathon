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

Reject duplicate/unknown columns, invalid rows, missing offsets, NaN/infinity, and horizons over 72 hours. Unsupported SoC/battery fields must be converted into energy requirements before upload; no hidden SoC inference is performed. A physically impossible energy target is valid input and appears as unserved energy.

## Prices CSV

`timestamp,price_eur_per_kwh`. Timezone-aware ISO 8601 timestamps must map to UTC quarter-hour boundaries, with no duplicates and complete coverage of the uploaded session horizon. Maximum 1000 rows/2 MiB. Finite negative prices are supported; range -10 to 100 EUR/kWh. Price upload is optional only when the current series covers the new sessions.

The demo's time-of-use prices are synthetic. The retained OPSD adapter converts wholesale EUR/MWh to EUR/kWh by dividing by 1000, holding each hourly value across four quarters. This is not a current retail tariff.

## Station and scheduling

`data/demo/station_config.json` initializes the station: one 80 kW site, ten 11 kW Type 2 chargers, efficiency 1.0, UTC, 15-minute grid. The station editor supports changing capacity, efficiency, charger ratings, connector types, and administrative availability. A recovery event clears a fault; a charger disabled in settings remains disabled.

Allocations contain vehicle/charger IDs, timezone-aware start/end, grid kW, and efficiency. Battery kWh = kW × duration hours × efficiency. Grid cost = kW × duration hours × EUR/kWh. Availability is half-open `[arrival, departure)`; exact boundaries refine the grid. One vehicle per connector, one connector per vehicle, connector compatibility, ratings, availability, and station capacity are independently checked. Targets may have explicit shortfalls; overcharging is rejected.

## Events and state

`CHARGER_FAILED`: event ID, charger ID, future start/end. `CHARGER_RECOVERED`: event ID, charger ID, recovery time. `PRICE_CHANGED`: event ID, future start/end, additive EUR/kWh adjustment. Events must remain within the scenario horizon.

Mutations require `expected_version`; stale requests return HTTP 409. An identical event replay is ignored, including a retry using the original version. Reusing an ID with different content returns 409. A failed replan retains the prior schedule, visibly stale. Advancing simulation time freezes completed allocations and their efficiency; replanning preserves that ledger.

## Fixtures and provenance

`data/demo/`: deterministic 50-session normal case, 100-session stress case with a deliberately impossible target, station/events, week-long synthetic prices, and SHA-256 manifest. `scripts/prepare_data.py` regenerates these inputs; external acquisitions are opt-in. `scripts/validate_data.py` verifies hashes, schemas, temporal grids, resampling, and available reference data. See [data-sources.md](data-sources.md).
