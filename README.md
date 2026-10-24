# ChargeWise AI

EV charging planning for fleet and workplace operators: compare immediate charging with a constrained schedule, explain decisions with NVIDIA Nemotron via Nebius, and replan after simulated disruptions.

**Current status:** project documentation, source research, reproducible input datasets, and data tooling. The FastAPI backend, React UI, optimizer, and Nemotron integration are planned; this repository does not yet contain a working application or measured savings.

Repository: [j-stoerk/nebiusxnvidia_hackathon](https://github.com/j-stoerk/nebiusxnvidia_hackathon).

## Start here

- [Workflow and technology stack](ChargeWise%20AI%20%E2%80%94%20Project%20Workflow%20and%20Technology%20Stack.md)
- [Hackathon requirements and submission checklist](docs/hackathon-rules.md)
- [Dataset schemas and assumptions](docs/dataset-format.md)
- [Verified sources, acquired data, and remaining access requirements](docs/data-sources.md)
- [Storage strategy and cloud downloads](docs/storage.md)
- [NVIDIA forecasting candidate and future fine-tuning data](docs/forecasting.md)
- [Invite teammates and collaborate](CONTRIBUTING.md)
- [Decisions retained from the retired blueprint](docs/blueprint-decisions.md)
- [Target application structure](folder-structure.md)

## Use the data now

Python 3.11+ is sufficient; no dependency installation or local model download is needed for these scripts.

```powershell
python scripts/prepare_data.py
python scripts/validate_data.py
```

The committed `data/demo/` fixtures contain 50 synthetic sessions, a 100-session stress case, a week of synthetic 15-minute EUR prices, one simulated station with ten chargers, and disruption scenarios. Everything is labeled synthetic. Small NLR/NASA reference slices, provenance, and required notices are in `data/reference/`. [data/acquisition-report.json](data/acquisition-report.json) records acquisition results. Larger training corpora stay outside Git.

Fetch small historical slices when needed:

```powershell
python scripts/prepare_data.py --sources opsd nlr nasa
python scripts/validate_data.py --external
```

Outputs go into ignored `data/external/`. The script streams the OPSD source, reads the NLR archive in RAM, and retains only small slices. A registered ACN token enables `--sources acn`; synthetic sessions work without it. Scripts read credentials from the process environment, not automatically from `.env`.

## Build next

Implement CSV validation and analytics, a first-come-first-served baseline, OR-Tools scheduling with independent constraint checks, a dashboard, Nemotron tools, and outage/price-change replanning. Keep one end-to-end scenario working throughout development. See the workflow for acceptance criteria.

Project-authored code, docs, and generated fixtures use the [MIT license](LICENSE). External datasets keep their own terms. Configure secrets separately in each developer environment and in the deployment host.
