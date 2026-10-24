# Dataset provenance

All datasets are retained. The running application defaults to `data/demo/`; reference data are not silently mixed into that scenario.

| Data | Contents and origin | Location |
| --- | --- | --- |
| Demo sessions | Deterministic synthetic generator, seed 2026; 50 EVs plus 100-session stress case | `data/demo/` |
| Demo station/events/prices | Simulated 80 kW station, ten 11 kW chargers, outages/recovery/duplicate delivery/price changes, synthetic EUR prices | `data/demo/` |
| NLR charging load | Simulated aggregate two-port 150 kW DC station; first 10,080 one-minute points plus 672 quarter-hour means | `data/reference/` |
| NASA POWER | Berlin solar/weather, 168 hours, 2019-01-07 through 2019-01-13 UTC; units/location metadata retained | `data/reference/` |
| OPSD | Historical Germany/DE-LU load, wind/solar and wholesale prices; 168 hours and 672 derived price slots | Ignored `data/external/`, when acquired |
| ACN | Real Caltech sessions; API token required, no real sessions acquired during initial setup | Optional acquisition only |

Exact URLs, transformations, byte sizes, row counts, and SHA-256 values are in each manifest and `data/acquisition-report.json`. External observations retain provider terms; the project's MIT license does not relicense them.

NLR source: [dataset 176](https://data.nlr.gov/submissions/176), DOI [10.7799/1827356](https://doi.org/10.7799/1827356), Gilleran and coauthors (2021). Credit DOE/NREL/ALLIANCE and retain the entire [notice](../data/reference/NLR_DATA_LICENSE.txt) with copied or derived data. Original simulated timestamps start 2020-01-01, timezone unspecified. These DC profiles do not represent the demo AC station, individual arrivals, or driver deadlines. Fifteen-minute aggregation uses mean kW and preserves energy.

NASA source: [POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/). Solar irradiance is a resource series, not rooftop PV output. Provider units are in `nasa_power_metadata.json`.

OPSD source: [2020-10-06 time-series release](https://data.open-power-system-data.org/time_series/2020-10-06/), DOI [10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06). Original-provider terms apply; selected observations are not redistributed in Git. National MW values are grid context, never a depot capacity limit.

ACN source: [Caltech ACN-Data](https://ev.caltech.edu/dataset.html). Set an authorized `ACN_API_TOKEN` to fetch the selected week. The adapter strips personal IDs and labels its assumptions: historical delivered energy as an energy proxy, unplug time as availability, and 6.6 kW as an assumed cap. Do not represent California sessions paired with German prices as an observed local deployment.

Optional acquisition commands:

```powershell
uv run python scripts/prepare_data.py --sources opsd nlr nasa
uv run python scripts/prepare_data.py --sources acn
uv run python scripts/validate_data.py --external
```

Larger future fine-tuning/LoRA corpora and model checkpoints stay separate from the demo repository. No training is required to run the application.
