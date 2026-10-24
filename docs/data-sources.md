# Verified data sources and demo acquisition

Reviewed 2026-10-24. This reconciles the original `data_sources.txt` and retired PDF. Required demo inputs are charging sessions, prices, station settings, and disruption events. External historical sources add realism; the hackathon does not require downloading every listed source.

## Ready for the demo

| Inputs | Actual contents | Storage |
| --- | --- | --- |
| Charging sessions | 50 deterministic synthetic EVs; 100-session stress fixture with an impossible energy target | `data/demo/` in GitHub |
| Station/events | Ten simulated 11 kW chargers, 80 kW cap; outage/recovery, duplicate delivery, price spike | `data/demo/` in GitHub |
| Price curve | Synthetic EUR time-of-use values; 672 quarter-hours | `data/demo/` in GitHub |
| Historical prices and grid context | OPSD Germany/DE-LU, 168 hours, 2019-01-07 to 2019-01-14 UTC; 672 derived price slots | `data/external/`, ignored |
| Aggregate EV load reference | NLR simulated DC profile: two 150 kW ports, two events/port/day; 10,080 minute samples plus 672 quarter-hour means | Small reference slice in GitHub |
| Optional solar/weather | NASA POWER Berlin: 168 hourly irradiance/temperature points, 2019-01-07 through 2019-01-13 UTC; units/location metadata retained | Small reference slice in GitHub |

The NLR timestamps begin January 1, 2020 with no timezone declared; the profile is a distinct simulated reference, not a synchronized observation of the 2019 German scenario. Its station type also differs from the AC demo. Credit **DOE/NREL/ALLIANCE**, Gilleran and coauthors (2021), dataset DOI [10.7799/1827356](https://doi.org/10.7799/1827356). NASA observations use the POWER project products; the saved metadata includes parameter names/units and source details.

Run `python scripts/prepare_data.py --sources opsd nlr nasa --export-reference`, then `python scripts/validate_data.py --external`. No installed Python packages are needed. The committed acquisition report records exact URLs, hashes, rows, source transformations, and failures. `--export-reference` copies only the small NLR/NASA slices plus their notices into Git; it does not export OPSD or ACN observations.

## Source register

| Source and primary reference | Role and access | Decision |
| --- | --- | --- |
| [Caltech ACN-Data](https://ev.caltech.edu/dataset.html) | Real session timestamps/energy; API registration/token, pagination. Avoid optional high-volume `/ts` endpoint. | **Blocked for API acquisition:** `ACN_API_TOKEN` absent. Public web export was tested but returned an incomplete JSON payload without usable sessions. Synthetic sessions are the working fallback. Adapter is ready for an authorized token. |
| [NLR EVI-Pro Lite](https://developer.nlr.gov/docs/transportation/evi-pro-lite-v1/) | Modeled aggregate EV demand, not individual sessions. Developer documentation currently exposes little extractable endpoint information. | Optional; no successful API acquisition asserted, no key configured. NLR static profiles cover the aggregate-load reference role. |
| [OPSD time series](https://data.open-power-system-data.org/time_series/2020-10-06/) | Historical European load, wind/solar, day-ahead prices. Pinned 2020-10-06 release. No API key for CSV. | **Acquired** selected columns/week by streaming; no full archive on disk. Source is historical, not current pricing. |
| [EIA Open Data](https://www.eia.gov/opendata/) | U.S. balancing-area actual/forecast demand, generation, interchange; API registration for normal use. | Optional U.S. grid-context alternative; not required for the chosen German scenario. No API call/data claimed. |
| [ENTSO-E Transparency](https://transparency.entsoe.eu/) | European wholesale electricity data; live portal requires JavaScript; programmatic access needs authorization. | Optional direct/live integration; historical OPSD slice supplies the demo price/context role. No token configured. |
| [NLR NSRDB](https://developer.nlr.gov/docs/solar/nsrdb/) | Solar resource/weather products; product-specific coverage and API access. | Optional solar extension; NASA POWER is the acquired location-based alternative. Solar resource alone is not PV generation. |
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) | Public point API; hourly solar/weather; explicit UTC request, latitude/longitude and parameter units. | **Acquired** Berlin slice; optional for future solar-context feature. |
| [Electricity Maps](https://app.electricitymaps.com/docs) | Historical/current/forecast grid intensity and market APIs; account, key, coverage and plan constraints. | Optional emissions extension. No token or licensed history available; omit actual emissions claims. Original API-doc URL redirects here. |
| [WattTime](https://docs.watttime.org/) | Emissions signals; authenticated service and geographic/product coverage. | Optional; no credentials/data acquired. Do not mix marginal and average carbon intensity. |
| [NASA battery catalog](https://data.nasa.gov/dataset/?tags=batteries) | Laboratory battery cycling/degradation datasets; catalog, not a single vehicle fleet dataset. | Out of MVP: not required for energy/deadline scheduling; no battery archive downloaded. |
| [mobilityhouse OCPP](https://github.com/mobilityhouse/ocpp) | Python protocol implementation, not fault/session observations. | Reference for a future real-charger adapter; no dependency or full repository copied. |
| [OCA compliance test tool](https://openchargealliance.org/test-tool/) | Protocol conformity tool; not a public charger-fault dataset. | Not required for a simulated web demo; no certification or hardware compatibility claim. |
| [CEC MIDAS](https://github.com/california-energy-commission/MIDAS) | California rate/signal API integration materials; not a generic plug-in fault dataset. | Optional U.S. demand-response/rate extension; no account/API acquisition. |
| [OpenADR 3.1 guide](https://github.com/grid-coordination/openadr3-specification/blob/main/3.1.0/User_Guide.md) and [specifications](https://www.openadr.org/specification) | Event/API semantics, not measured demand-response events or an operating policy corpus. | References only; author synthetic events and project policy instead of claiming historical events. |
| [OCPP specifications](https://openchargealliance.org/my-oca/ocpp/) | Protocol documents with their own download/license conditions. | Optional reference; no standards bundle mirrored into Git. |

## Terms and interpretations

NLR permits copying/use subject to retaining its entire notice and crediting DOE/NREL/ALLIANCE. That notice accompanies both the minute profile and its 15-minute derivative. [Dataset-specific notice](https://data.nlr.gov/node/176/license).

OPSD's package metadata/README requests attribution but does not declare a blanket data license. Source-provider terms remain relevant. Keep these downloaded observations outside Git until redistribution terms for the selected series are established; a repository MIT license cannot license upstream data. Attribution: Open Power System Data (2020), Data Package Time series, version 2020-10-06, DOI [10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06). [Package README](https://data.open-power-system-data.org/time_series/2020-10-06/README.md), [OPSD legal context](https://open-power-system-data.org/legal/).

ACN delivered energy is a historical observation, not necessarily the driver's requested energy; max vehicle power is not directly supplied by the session endpoint. The adapter labels those assumptions and strips personal identifiers. Do not silently combine California observations with German wholesale prices as a real deployment. See [dataset contract](dataset-format.md).

Carbon, solar, battery aging, live tariffs, physical OCPP control, and real demand-response services are optional. Their missing credentials do not block the charging scheduler/agent demo. No paid API, account registration, or credential collection was performed.

## Data for future training

Only demo-sized inputs belong in this repository. A larger authorized forecast-adaptation or Nemotron LoRA corpus requires a separate cloud dataset, immutable version/hash manifests, and held-out evaluation. The current fixtures are sufficient to exercise the demo's input contracts; they are not a validated fine-tuning corpus. See [forecasting and fine-tuning plan](forecasting.md).
