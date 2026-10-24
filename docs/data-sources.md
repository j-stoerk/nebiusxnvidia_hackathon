# Dataset provenance

All datasets are retained. The running application defaults to `data/demo/`; reference data are not silently mixed into that scenario.

| Data | Contents and origin | Location |
| --- | --- | --- |
| Demo sessions | Deterministic synthetic generator, seed 2026; 50 EVs plus 100-session stress case | `data/demo/` |
| Demo station/events/prices | Simulated 80 kW station, ten 11 kW chargers, outages/recovery/duplicate delivery/price changes, synthetic EUR prices | `data/demo/` |
| NLR charging load | Simulated aggregate two-port 150 kW DC station; first 10,080 one-minute points plus 672 quarter-hour means | `data/reference/` |
| NASA POWER | Berlin solar/weather, 168 hours, 2019-01-07 through 2019-01-13 UTC; units/location metadata retained | `data/reference/` |
| OPSD | Historical Germany/DE-LU load, wind/solar and wholesale prices; 168 hours and 672 derived price slots | Ignored `data/external/`, when acquired |
| ACN | Office 1 public research mirror: 1,481 real-session records, 2019–2021; normalized locally, personal fields stripped | Offline evaluation; outside Git |

Exact URLs, transformations, byte sizes, row counts, and SHA-256 values are in each manifest and `data/acquisition-report.json`. External observations retain provider terms; the project's MIT license does not relicense them.

NLR source: [dataset 176](https://data.nlr.gov/submissions/176), DOI [10.7799/1827356](https://doi.org/10.7799/1827356), Gilleran and coauthors (2021). Credit DOE/NREL/ALLIANCE and retain the entire [notice](../data/reference/NLR_DATA_LICENSE.txt) with copied or derived data. Original simulated timestamps start 2020-01-01, timezone unspecified. These DC profiles do not represent the demo AC station, individual arrivals, or driver deadlines. Fifteen-minute aggregation uses mean kW and preserves energy.

NASA source: [POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/). Solar irradiance is a resource series, not rooftop PV output. Provider units are in `nasa_power_metadata.json`.

OPSD source: [2020-10-06 time-series release](https://data.open-power-system-data.org/time_series/2020-10-06/), DOI [10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06). Original-provider terms apply; selected observations are not redistributed in Git. National MW values are grid context, never a depot capacity limit.

ACN source: [Caltech ACN-Data](https://ev.caltech.edu/dataset.html). The [official Python client](https://github.com/zach401/acnportal) still requires an authorized `ACN_API_TOKEN`. Configure it in `.env`, then run `uv run --with acnportal==0.3.3 python scripts/fetch_acn.py` for January–June 2019 by default. Override site/dates/output as needed. Acquisition streams metadata-only sessions (no raw charging time series), strips personal IDs, enforces 100,000-session/32 MiB limits, and saves a checksum/provenance sidecar under ignored `data/external/`.

The [website export](https://ev.caltech.edu/dataset) is an alternative: `uv run python scripts/fetch_acn.py --json PATH.json --site office001 --output data/external/acn/office001.csv`. The importer accepts a full session array or `_items` JSON, parses RFC 1123/ISO timestamps with explicit offsets, rejects incomplete API pages, and needs no token/client. Old web downloads made before the portal's October 2019 timezone fix may contain shifted timestamps; the portal documents this issue.

Direct Caltech connections timed out. A [public research mirror](https://github.com/yvenn-amara/ev-load-open-data/tree/master/1.%20Input%20Data/7.%20ACN%20Data) supplied Office 1: 1,481 visits, 2019-03-25–2021-04-12, eight distinct ports, no overlapping same-port records, longest stay 73.85 h. Only the 134,334-byte normalized CSV and provenance/checksums are retained under ignored `data/external/acn/`; raw JSON and personal fields are not saved. The mirror is distinct from a live Caltech acquisition, and its upstream extraction/timezone history has not been independently verified.

The adapter labels its assumptions: observed meter energy as a retrospective target proxy (efficiency=1), unplug time as availability, and 6.6 kW as an explicitly assumed cap. Public station IDs and zero-energy occupied sessions are retained; the evaluation station configuration must match the actual ports, rather than silently assigning them to fictional demo chargers. These are not known-at-arrival requirements or measured battery SoC. Real workplace sessions are not depot duty cycles. Do not represent California sessions paired with German prices as an observed local deployment. See [evaluation.md](evaluation.md) for chronology, leakage checks and claim limits.

Optional acquisition commands:

```powershell
uv run python scripts/prepare_data.py --sources opsd nlr nasa
uv run --with acnportal==0.3.3 python scripts/fetch_acn.py
uv run python scripts/validate_data.py --external
```

Larger future fine-tuning/LoRA corpora and model checkpoints stay separate from the demo repository. No training is required to run the application.
