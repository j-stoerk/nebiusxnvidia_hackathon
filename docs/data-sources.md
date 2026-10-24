# Dataset provenance

All datasets are retained. The running application defaults to `data/demo/`; reference data are not silently mixed into that scenario.

## Original design's required inputs

The original workflow, recovered from commit `cb30fa6` (`ChargeWise AI — Project Workflow and Technology Stack.md`, section 2), requires five CSV columns and five station/price settings. The following pack covers the publicly recoverable values; it does **not** fill missing telemetry with invented measurements.

```powershell
uv run python scripts/acquire_required_data.py
```

Generated under `data/external/required/2019-04-01_2019-10-01/`: **5,392 recorded Caltech visits**, **261 usable request records known by arrival**, **54 published charger specifications**, **4,392 German price hours / 17,568 derived scheduling slots**, and the ACN team's historical SCE tariff/17,568 USD price slots. Total retained data is about **2.3 MB**; source JSON is processed in memory. Personal IDs and raw archives are not retained. File/source checksums and scope are in `manifest.json`; the tracked acquisition report records coverage.

| Design input | Real source and acquired field | Status / limitation |
| --- | --- | --- |
| `vehicle_id` | Stable aliases for source session rows | Satisfies the original vehicle/session identifier contract; not persistent vehicle/VIN identity |
| `arrival_time` | ACN `connectionTime` | Recorded plug-in time, explicit UTC |
| `departure_time` | ACN `userInputs.requestedDeparture` | Recorded request parameter. Only versions timestamped at/before arrival enter the 261-row cohort. Observed unplug is kept separately |
| `energy_required_kwh` | ACN `userInputs.kWhRequested` | Recorded requested kWh, **not** a substitution of delivered kWh. This archive lacks the later explicit user/default source flag; requests may include preferences/defaults |
| `max_charging_power_kw` | Published ACN EVSE ceiling: 208 V × 32 A = 6.656 nominal kW at unity power factor | **Partial:** a documented equipment ceiling, not the vehicle's acceptance limit. The latter remains unknown |
| Number of chargers | Published Caltech ACN network model | 54 ports in that historical model, not a live operational count |
| Station power limit | Published Caltech transformer model | 150 kW nominal, plus shared-pod/phase constraints. It is not a German depot's available import budget |
| Slot duration | Original design's 15-minute setting | A controller configuration, not a measured quantity |
| Electricity prices | Bundesnetzagentur SMARD filter 4169, DE, hourly EUR/MWh; SCE historical tariff separately in USD | German native observations are divided by 1,000 and held across four slots. No California/EUR join or currency relabeling; neither product establishes a depot's retail contract |
| Charger availability | Actual plug connection/disconnection windows in observed-session CSV | **Partial:** occupancy is known; operational online/fault state is unknown. Idle/zero current is not evidence of a fault |

Files: `caltech_observed_sessions.csv` preserves measured availability/delivery and request provenance; `caltech_requests_equipment_ceiling.csv` has the five core columns plus actual port bindings and J1772 compatibility, with the equipment-ceiling qualification above. It is a reported-deadline cohort, **not** an executed readiness result; an early observed unplug remains separate. `caltech_charger_catalog.csv` includes phase angles and allowable pilot amperages; `caltech_site.json` records nominal/shared limits. The current scalar scheduler does not enforce the full ACN phase network or pilot quantization, so these data do not confer hardware certification. Full six-month files exceed the interactive 100-session/72-hour upload budget; use them for batch analysis, or select a compatible short roster deliberately.

Optional older-blueprint fields `station_id`/`connector_type` have a source (Caltech public equipment identifiers and documented J1772 control). Battery capacity, current/target SoC and efficiency are absent from this AC-session snapshot. The real-measurement pack below supplies separate vehicle and equipment references; it cannot identify the anonymous Caltech vehicles.

Primary references: [ACN field definitions](https://ev.caltech.edu/dataset), [published Caltech network](https://github.com/zach401/acnportal/blob/14e723b11339e56ca3afd2bf4969f9e4bc8c2623/acnportal/acnsim/network/sites/caltech_acn.py), [EVSE pilot definitions](https://github.com/zach401/acnportal/blob/14e723b11339e56ca3afd2bf4969f9e4bc8c2623/acnportal/acnsim/models/evse.py), [ACN thesis: J1772/BMS limitations](https://thesis.library.caltech.edu/14191/1/Lee_Zachary_J_2021_Thesis.pdf), [SMARD market downloads](https://www.smard.de/en/downloadcenter/download-market-data/) and [required SMARD attribution/license](https://www.smard.de/en/datennutzung). The recorded sessions come from the [pinned research mirror](https://github.com/yvenn-amara/ev-load-open-data/tree/3b1cb67d1b02f8fea0451c16fbcfaee34449ce46/1.%20Input%20Data/7.%20ACN%20Data); original extraction/timezone history remains unverified. The SCE JSON is the ACN team's historical research representation, not a verified customer contract or complete current bill.

## Real vehicle and operational measurements

```powershell
uv run --with pyarrow --with openpyxl python scripts/acquire_vehicle_data.py
uv run python scripts/validate_data.py --external
```

Acquired on 2026-10-24 under shared `data/external/real/`, about **2.8 MB** including source notices. The optional readers are acquisition dependencies; the demo needs neither. Raw Parquet/Excel/source CSV files are processed in memory, with a 32 MiB limit per download. Use `--sources tum dtu curves mobidata` to select sources. Each folder has file/source SHA-256 checksums, retrieval time, attribution and limitations; the small tracked acquisition report inventories the files.

| Missing field/reference | Acquired real source | How it can be used |
| --- | --- | --- |
| Current SoC and a known vehicle model | [TUM field telemetry](https://github.com/TUMFTM/electric-vehicle-uds-dataset/tree/6bac2936e280b2d7f45607e5cb624a18b41b3faa): 13,764 measured SoC readings for CUP3, a 2022 CUPRA Born, November 2022–April 2023 | `tum/cup3_observed_soc.csv`. Source clock has no timezone; preserve it without assigning UTC. Readings include driving/parking, not just charging |
| Battery capacity and maximum charging power | TUM identifies a nominal 58 kWh usable pack; [CUPRA's 2022 technical sheet](https://www.seat-cupra-mediacenter.com/CUPRA-Brand/presskits/cupra-born-se/technical-data) specifies 120 kW DC for that model/pack | `tum/cup3_vehicle.json`. These are model ratings, not measured aged capacity, an AC limit, or instantaneous acceptance power |
| Charging efficiency, power factor and reactive power | [DTU experiments](https://doi.org/10.11583/DTU.25425262.v1): 315 efficiency, 295 power-factor and 305 reactive-power observations across 36 experiment rows | `dtu/*.csv`, by model/current; efficiency converted from percent to fraction. Repeated model names retain separate source-row IDs. No interpolation or assignment to CUP3/Caltech |
| Power versus charge level / taper reference | [Morin, Chatra, Whitacre and Michalek](https://doi.org/10.6084/m9.figshare.30570653.v1): 18,506 digitized points in 99 Fastned/InsideEVs profiles | `curves/digitized_dc_curves.csv`. Published plot digitization, **not raw telemetry**. Axis labels mix SOC/SOE; calculated times and inconsistent pack-capacity metadata are excluded. No automatic scheduler calibration |
| Actual charger status, connectors and power ratings in Germany | [MobiData BW](https://mobidata-bw.de/dataset/e-ladesaulen), chargecloud feed: 406 German EVSEs / 422 connector rows in the acquired sample | `mobidata/german_evse_snapshot.csv`: reported available/charging/out-of-order/inoperative/unknown status, timestamps, connector type and rated kW. Multiple connectors on one EVSE do not create extra chargers; UNKNOWN/STATIC give blank availability. A status snapshot is not an exact outage interval |
| Historical German availability/occupancy | Same portal, EcoMovement feed, Lidl Heilbronn location 323832: 137 observed snapshots, October 17–24, 2026 | `mobidata/heilbronn_observed_status_history.csv`: actual counts, original stale-data flag and observation/update times. These are station counts, not vehicle sessions or a complete fault log |

The status acquisition is bounded and stratified by status, **not a representative uptime sample**; counts can change on refresh. It preserves published connector power rather than recomputing an incompatible value from voltage/current. Source defects are retained and flagged: four zero efficiencies, an out-of-range power-factor entry and two negative digitized charge-level points. Exclude flagged rows from model fitting; missing experimental cells stay missing. The validator checks these exclusions and units.

TUM is **CC BY-NC 4.0**; keep its README/citation/license with derived data. DTU and the digitized curves are **CC BY 4.0**; author/DOI notices are retained. MobiData's aggregate uses **Datenlizenz Deutschland Namensnennung 2.0**; the selected chargecloud/EcoMovement feeds declare CC0, preserved in `source_notices.json`. These terms are separate from the application license.

**Remaining unavailable inputs:** a requested target SoC, actual acceptance/efficiency curves for the anonymous ACN vehicles, a German depot's duty-cycle roster, site connection agreement, complete customer retail tariff, building load and vehicle-linked OCPP/BMS logs. Observed end SoC is not a requested target; an OEM rating is not observed acceptance. The acquired sources cannot be joined into a fictitious single-depot record. The published German network tariff already documented in [evaluation.md](evaluation.md) remains a tariff sensitivity, not that depot's contract. These reference extracts do not change the synthetic guided demo, supply a calibrated CC–CV model, or establish 95% departure readiness.

## Operator data and a practical completion path

The [Optimise Prime operator release](https://ukpowernetworks.opendatasoft.com/explore/dataset/ukpn-optimise-prime/information/) provides a stronger linked reference: actual Royal Mail depot assets and vehicle telematics. Acquire the compact slice with `uv run python scripts/acquire_operator_data.py`. Under `data/external/real/optimiseprime/`, it retains **237 vehicle records with configured battery capacities/charge-rate limits, 229 charger/socket records, nine depot configurations, and 4,738 matched telemetry observations** (about **279 KB**). The telemetry covers 59 vehicles with 4,679 valid SoC readings; charging power is unavailable in this slice. The vehicle-to-type-to-depot joins use provider IDs. Another 7,078 sampled observations lacked a matching vehicle-type record in the as-of snapshot and are excluded, not completed with future configuration. The release's [field guidance](https://ukpowernetworks.opendatasoft.com/api/datasets/1.0/ukpn-optimise-prime/attachments/202302_op_deliverables_d6_dataset_guidance_v4_pdf/) documents these relationships and unavailable-value sentinels.

Asset events are replayed through June 30, 2021, excluding later revisions; later July reconfigurations are not replayed. Telemetry is the first 8 MiB of July's charging file, restricted to timestamps on/after July 1 and linked vehicles; **it is an incomplete sample, not a full day/month or scientific evaluation cohort**. Source power=31 with unknown charging type becomes missing, and SoC=127 becomes missing. Only aliases, readings and physical configuration fields are retained; RFID/device IDs and location traces are stripped. The current public read-only download token is discovered at runtime and never stored in code or manifests. Source/file hashes, CC BY 4.0 attribution and scope accompany the extract.

Connection capacity stays in **kVA**, not an invented kW charging budget. Charger/socket ratings may share upstream limits and need validation before physical scheduling. Vehicle type maximum SoC is a configuration ceiling, not an individual request. This UK release does not establish a German site's contract or give a known-at-arrival departure/target roster.

For a usable demo now, `uv run python scripts/prepare_depot.py --demo` fills every required planning input with explicit synthetic values, including requested SoC and efficiency. For a particular operator, replace the same three input files with fleet/telematics exports, the dispatcher's departure/target policy, verified equipment/available EV power budget, and contract prices. The converter checks both input consistency and all four resulting schedules; it never silently guesses an operator goal. See [the complete pack and import commands](dataset-format.md#completing-a-demo-or-operator-roster). This resolves demo completeness while keeping observed facts, configuration ratings and planning choices distinguishable.

## Retained datasets

| Data | Contents and origin | Location |
| --- | --- | --- |
| Demo sessions | Deterministic synthetic generator, seed 2026; 50 EVs plus 100-session stress case | `data/demo/` |
| Demo station/events/prices | Simulated 80 kW station, ten 11 kW chargers, outages/recovery/duplicate delivery/price changes, synthetic EUR prices | `data/demo/` |
| NLR charging load | Simulated aggregate two-port 150 kW DC station; first 10,080 one-minute points plus 672 quarter-hour means | `data/reference/` |
| NASA POWER | Berlin solar/weather, 168 hours, 2019-01-07 through 2019-01-13 UTC; units/location metadata retained | `data/reference/` |
| OPSD | Historical Germany/DE-LU load, wind/solar and wholesale prices; 168 hours and 672 derived price slots | Ignored `data/external/`, when acquired |
| ACN | Office 1 public research mirror: 1,481 real-session records, 2019–2021; normalized locally, personal fields stripped | Shared `data/external/acn/` |

Exact URLs, transformations, byte sizes, row counts, and SHA-256 values are in each manifest and `data/acquisition-report.json`. External observations retain provider terms; the project's MIT license does not relicense them.

NLR source: [dataset 176](https://data.nlr.gov/submissions/176), DOI [10.7799/1827356](https://doi.org/10.7799/1827356), Gilleran and coauthors (2021). Credit DOE/NREL/ALLIANCE and retain the entire [notice](../data/reference/NLR_DATA_LICENSE.txt) with copied or derived data. Original simulated timestamps start 2020-01-01, timezone unspecified. These DC profiles do not represent the demo AC station, individual arrivals, or driver deadlines. Fifteen-minute aggregation uses mean kW and preserves energy.

NASA source: [POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/). Solar irradiance is a resource series, not rooftop PV output. Provider units are in `nasa_power_metadata.json`.

OPSD source: [2020-10-06 time-series release](https://data.open-power-system-data.org/time_series/2020-10-06/), DOI [10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06). Original-provider terms apply; selected observations are not redistributed in Git. National MW values are grid context, never a depot capacity limit.

ACN source: [Caltech ACN-Data](https://ev.caltech.edu/dataset.html). The [official Python client](https://github.com/zach401/acnportal) still requires an authorized `ACN_API_TOKEN`. Configure it in `.env`, then run `uv run --with acnportal==0.3.3 python scripts/fetch_acn.py` for January–June 2019 by default. Override site/dates/output as needed. Acquisition streams metadata-only sessions (no raw charging time series), strips personal IDs, enforces 100,000-session/32 MiB limits, and saves a checksum/provenance sidecar under ignored `data/external/`.

The [website export](https://ev.caltech.edu/dataset) is an alternative: `uv run python scripts/fetch_acn.py --json PATH.json --site office001 --output data/external/acn/office001.csv`. The importer accepts a full session array or `_items` JSON, parses RFC 1123/ISO timestamps with explicit offsets, rejects incomplete API pages, and needs no token/client. Old web downloads made before the portal's October 2019 timezone fix may contain shifted timestamps; the portal documents this issue.

Direct Caltech connections timed out. A [public research mirror](https://github.com/yvenn-amara/ev-load-open-data/tree/master/1.%20Input%20Data/7.%20ACN%20Data) supplied Office 1: 1,481 visits, 2019-03-25–2021-04-12, eight distinct ports, no overlapping same-port records, longest stay 73.85 h. Only the 134,334-byte normalized CSV and provenance/checksums are shared under `data/external/acn/`; raw JSON and personal fields are not saved. The mirror is distinct from a live Caltech acquisition, and its upstream extraction/timezone history has not been independently verified.

The adapter labels its assumptions: observed meter energy as a retrospective target proxy (efficiency=1), unplug time as availability, and 6.6 kW as an explicitly assumed cap. Public station IDs and zero-energy occupied sessions are retained; the evaluation station configuration must match the actual ports, rather than silently assigning them to fictional demo chargers. These are not known-at-arrival requirements or measured battery SoC. Real workplace sessions are not depot duty cycles. Do not represent California sessions paired with German prices as an observed local deployment. See [evaluation.md](evaluation.md) for chronology, leakage checks and claim limits.

Optional acquisition commands:

```powershell
uv run python scripts/prepare_data.py --sources opsd nlr nasa
uv run --with acnportal==0.3.3 python scripts/fetch_acn.py
uv run python scripts/validate_data.py --external
```

Larger future fine-tuning/LoRA corpora and model checkpoints stay separate from the demo repository. No training is required to run the application.
