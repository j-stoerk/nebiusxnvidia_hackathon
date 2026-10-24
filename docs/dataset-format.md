# Input contracts and provenance

## Charging sessions

UTF-8 CSV, one session per row. Use timezone-aware ISO 8601 timestamps (committed fixtures use UTC `Z`). Intervals are half-open `[arrival, departure)`; reject missing timezone offsets rather than guessing.

| Required field | Meaning | Validation |
| --- | --- | --- |
| `vehicle_id` | Vehicle/session identifier in this upload | Nonempty; core MVP allows one session per ID |
| `arrival_time` | Earliest availability | Valid timestamp before departure |
| `departure_time` | Availability deadline | Valid timestamp after arrival |
| `energy_required_kwh` | Required battery energy | Finite, nonnegative kWh |
| `max_charging_power_kw` | Maximum input rate | Finite, positive kW |

For repeated sessions by one actual vehicle, extend the contract with a unique `session_id`; do not infer persistent identity from a source session identifier. Reject duplicate rows/IDs under the core contract. Validate each row and identify impossible energy requests without pretending they are malformed timestamps.

Optional future fields: `station_id`, `connector_type`, `battery_kwh`, `current_soc`, `target_soc`. SoC is a fraction in `[0,1]`; require `target_soc >= current_soc` and positive capacity. Derive battery energy as `battery_kwh * (target_soc - current_soc)`. Distinguish battery energy from grid energy if efficiency differs from 1.0. Do not require both this representation and energy input without checking consistency.

## Station and price inputs

`station_config.json` defines station cap, slot duration, charger IDs/ratings/availability, and efficiency. Demo configuration: one 80 kW station, ten 11 kW Type 2 chargers, 15-minute slots, efficiency 1.0. This is simulated hardware, unrelated to the real station configuration of any data provider. Every demo EV is assumed Type 2 compatible.

Price CSV: `timestamp,price_eur_per_kwh`. Each timestamp starts a 15-minute slot; exactly cover the optimization horizon with no duplicates/gaps. Allow finite negative market prices. The default fixture is synthetic time-of-use pricing, not a current retail tariff.

The OPSD adapter retains Germany/DE-LU historical observations for `2019-01-07T00:00Z` through `2019-01-14T00:00Z` (exclusive). Divide EUR/MWh by 1000 for EUR/kWh. Repeat each hourly price over four slots; this adds scheduling resolution, not new price observations. Taxes, network charges, demand charges, and retail margins are excluded. National MW load/wind/solar are context, never a depot power limit.

## Acquired optional reference data

- NLR: first 10,080 one-minute observations from one **simulated aggregate DC station** profile, plus 672 quarter-hour means that preserve energy. Original simulated timestamps begin 2020-01-01; timezone is unspecified. Keep this separate from the 2019 UTC series and the 11 kW AC demo. No individual arrivals, EV deadlines, or battery state can be recovered from aggregate power.
- NASA POWER: Berlin hourly solar/weather values for the same UTC week. Retain provider parameter units/metadata; solar resource data are not rooftop PV output without a PV model. Source products combine satellite/reanalysis/models.
- ACN: if an authorized API token is supplied, map connection/disconnection to availability and historical delivered kWh to an explicitly labeled energy proxy; 6.6 kW is an assumed demo power cap, not a measured vehicle limit. Strip user IDs and mobile inputs; assign session pseudonyms. A historical unplug time is not a guaranteed future driver deadline. California sessions must remain a separate scenario from German prices unless clearly labeled a cross-region simulation.

Source details: [data-sources.md](data-sources.md). Dataset terms do not inherit the repository's MIT license.

## Events and reproducibility

`events.json` contains independent scenarios, not one combined event stream: charger outage/recovery; repeated delivery of the identical outage; and a price spike. Use immutable `event_id`, `state_version`, and `schedule_version`; duplicate application must not change state twice. Replanning preserves already-delivered energy and applies changes only to future slots.

`data/demo/manifest.json` stores SHA-256 hashes, row counts, sizes, generator seed, and simulated status. External manifests add source URLs, acquisition timestamps, transformations, provider metadata, and failures. `data/acquisition-report.json` is a small shareable acquisition summary. Only the small NLR/NASA reference subset and notices are exported to `data/reference/`; OPSD/ACN observations and larger corpora are ignored by Git.
