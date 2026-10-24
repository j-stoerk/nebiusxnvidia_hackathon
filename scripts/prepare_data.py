"""Small, reproducible ChargeWise inputs. Python standard library only.

No model weights, full source archives, or personal identifiers are persisted.
External downloads are opt-in and ignored by Git. See docs/data-sources.md.
"""

import argparse
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2019, 1, 7, tzinfo=timezone.utc)
END = START + timedelta(days=7)
OPSD = "https://data.open-power-system-data.org/time_series/2020-10-06/"
NLR = "https://data.nlr.gov/system/files/176/electric_profiles.zip"
MAX_BYTES = 48 * 1024 * 1024


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def record(path, source, **extra):
    item = {
        "path": path.relative_to(ROOT).as_posix(),
        "source": source,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **extra,
    }
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as stream:
            item["rows"] = sum(1 for _ in csv.DictReader(stream))
    return item


def request(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "ChargeWise-data-preparation/1.0", **(headers or {})})
    return urllib.request.urlopen(req, timeout=45)


def read_small(url, headers=None):
    with request(url, headers) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Source exceeded 48 MiB download budget")
    return content


def synthetic():
    folder = ROOT / "data" / "demo"
    rng = random.Random(2026)
    sessions = []
    for i in range(50):
        arrival = START + timedelta(minutes=360 + 15 * rng.randrange(21))
        departure = START + timedelta(minutes=900 + 15 * rng.randrange(29))
        sessions.append({
            "vehicle_id": f"EV-{i + 1:03}",
            "arrival_time": stamp(arrival),
            "departure_time": stamp(departure),
            "energy_required_kwh": round(rng.uniform(6, 24), 2),
            "max_charging_power_kw": 11.0,
        })
    write_csv(folder / "sample_charging_sessions.csv", sessions)
    stress = [dict(row, vehicle_id=f"STRESS-{i + 1:03}") for i, row in enumerate(sessions * 2)]
    # A deliberate per-vehicle impossibility: 60 kWh required in half an hour at 11 kW.
    stress[0].update(arrival_time=stamp(START + timedelta(hours=17)),
                     departure_time=stamp(START + timedelta(hours=17, minutes=30)),
                     energy_required_kwh=60)
    write_csv(folder / "infeasible_charging_sessions.csv", stress)
    prices = []
    for slot in range(7 * 96):
        instant = START + timedelta(minutes=15 * slot)
        price = 0.12 if instant.hour < 6 or instant.hour >= 22 else 0.32 if 16 <= instant.hour < 20 else 0.22
        prices.append({"timestamp": stamp(instant), "price_eur_per_kwh": price})
    write_csv(folder / "synthetic_prices_15min.csv", prices)
    write_json(folder / "station_config.json", {
        "simulated": True, "station_id": "DEMO-01", "timezone": "UTC",
        "slot_minutes": 15, "station_power_limit_kw": 80,
        "charging_efficiency": 1.0,
        "chargers": [{"charger_id": f"CH-{i + 1:02}", "max_power_kw": 11,
                      "connector_type": "Type2", "available": True} for i in range(10)],
    })
    failure = {"event_id": "outage-001", "type": "CHARGER_FAILED", "charger_id": "CH-01",
               "start_time": stamp(START + timedelta(hours=9)), "end_time": stamp(START + timedelta(hours=12))}
    write_json(folder / "events.json", {
        "simulated": True,
        "scenarios": {
            "charger_outage": [failure, {"event_id": "recovery-001", "type": "CHARGER_RECOVERED",
                                         "charger_id": "CH-01", "time": failure["end_time"]}],
            "duplicate_delivery": [failure, failure],
            "price_spike": [{"event_id": "price-001", "type": "PRICE_CHANGED",
                             "start_time": stamp(START + timedelta(hours=15)),
                             "end_time": stamp(START + timedelta(hours=18)), "add_eur_per_kwh": 0.20}],
        },
    })
    files = [record(p, "ChargeWise deterministic synthetic generator", seed=2026, simulated=True,
                    license="MIT (project-generated fixtures)") for p in sorted(folder.iterdir())
             if p.suffix in (".csv", ".json") and p.name != "manifest.json"]
    write_json(folder / "manifest.json", {"schema_version": 1, "generator": "scripts/prepare_data.py",
                                          "period_utc": [stamp(START), stamp(END)], "files": files})
    return files


def opsd(folder):
    """Stream a single CSV; keep only one week and six columns on disk."""
    url = OPSD + "time_series_60min_singleindex.csv"
    fields = ["utc_timestamp", "DE_load_actual_entsoe_transparency", "DE_solar_generation_actual",
              "DE_wind_generation_actual", "DE_LU_price_day_ahead"]
    rows = []
    # No full CSV is materialized locally. Connection closes immediately after the selected week.
    with request(url) as response:
        reader = csv.DictReader(io.TextIOWrapper(response, encoding="utf-8-sig"))
        if not set(fields).issubset(reader.fieldnames or []):
            raise ValueError("OPSD schema changed")
        for row in reader:
            instant = datetime.strptime(row["utc_timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if instant >= END:
                break
            if instant >= START:
                if any(not row[f] for f in fields):
                    raise ValueError(f"Missing OPSD observation at {instant}")
                values = [float(row[f]) for f in fields[1:]]
                if not all(math.isfinite(value) for value in values):
                    raise ValueError("Non-finite OPSD observation")
                rows.append(dict(zip(["timestamp", "load_mw", "solar_mw", "wind_mw", "price_eur_per_mwh"],
                                     [stamp(instant), *values])))
    if len(rows) != 168:
        raise ValueError(f"Expected 168 OPSD hours, got {len(rows)}")
    target = folder / "opsd_germany_2019-01-07_week.csv"
    write_csv(target, rows)
    prices = []
    for row in rows:
        for quarter in range(4):
            instant = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")) + timedelta(minutes=15 * quarter)
            prices.append({"timestamp": stamp(instant), "price_eur_per_kwh": row["price_eur_per_mwh"] / 1000})
    price_path = folder / "opsd_prices_15min.csv"
    write_csv(price_path, prices)
    write_json(folder / "opsd_datapackage.json", json.loads(read_small(OPSD + "datapackage.json")))
    terms = "Original-provider terms apply; package metadata does not declare a data license. Not redistributed in Git."
    return [record(target, url, license=terms, measured=True, geography="Germany / DE-LU bidding zone"),
            record(folder / "opsd_datapackage.json", OPSD + "datapackage.json", kind="provider metadata"),
            record(price_path, url, license=terms, transformation="EUR/MWh divided by 1000; hourly values held across four quarters; wholesale, not retail tariff")]


class LicenseText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def nlr(folder):
    """Read 34 MB ZIP in RAM; persist one week from one aggregate DC profile."""
    archive_bytes = read_small(NLR)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        candidates = sorted(name for name in archive.namelist() if name.endswith(".csv") and not name.startswith("__MACOSX/"))
        if not candidates:
            raise ValueError("No CSV profiles in NLR archive")
        name = "electric_profiles/ev_station_2port_150kW_2event.csv"
        if name not in candidates:
            raise ValueError("Expected NLR two-port 150 kW profile missing")
        if archive.getinfo(name).file_size > MAX_BYTES:
            raise ValueError("Uncompressed profile exceeds budget")
        with archive.open(name) as stream:
            reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
            header = next(reader)
            # Keep original header/values: profile index and units must not be invented.
            rows = []
            for i, row in enumerate(reader):
                if i >= 7 * 24 * 60:
                    break
                rows.append(row)
    target = folder / "nlr_ev_load_first_week.csv"
    with target.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    license_url = "https://data.nlr.gov/node/176/license"
    parser = LicenseText()
    parser.feed(read_small(license_url).decode("utf-8"))
    text = " ".join(" ".join(parser.parts).split())
    start = text.index("The National Renewable Energy Laboratory (NREL) is operated")
    end = text.index("National Laboratory of the Rockies", start)
    notice = folder / "NLR_DATA_LICENSE.txt"
    notice.write_text(text[start:end].strip() + "\n", encoding="utf-8", newline="\n")
    if len(rows) != 10080:
        raise ValueError(f"Expected 10080 NLR minutes, got {len(rows)}")
    # Mean power (not sum) conserves energy when aggregating 15 one-minute samples.
    aggregates = []
    for i in range(0, len(rows), 15):
        window = rows[i:i + 15]
        aggregates.append({"profile_timestamp": window[0][0],
                           "mean_power_kw": sum(float(row[1]) for row in window) / len(window)})
    aggregate_path = folder / "nlr_ev_load_15min.csv"
    write_csv(aggregate_path, aggregates)
    return [record(target, NLR, simulated=True, member=name, selection="first 10080 observations; original time/index and column retained; timestamps start 2020-01-01, timezone unspecified",
                   archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),
                   license="NLR notice: keep entire notice with any copied data and credit DOE/NREL/ALLIANCE",
                   license_url=license_url),
            record(aggregate_path, NLR, simulated=True, member=name,
                   transformation="Mean of each 15 one-minute kW values; original simulated timestamps, timezone unspecified",
                   license="NLR full notice in NLR_DATA_LICENSE.txt"),
            record(notice, license_url, kind="required data notice")]


def nasa(folder):
    params = {"parameters": "ALLSKY_SFC_SW_DWN,T2M", "community": "RE", "longitude": 13.405,
              "latitude": 52.52, "start": "20190107", "end": "20190113", "format": "JSON", "time-standard": "UTC"}
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point?" + urllib.parse.urlencode(params)
    payload = json.loads(read_small(url))
    series = payload["properties"]["parameter"]
    rows = []
    for key in sorted(series["T2M"]):
        values = [series[name][key] for name in ("ALLSKY_SFC_SW_DWN", "T2M")]
        if any(value == payload.get("header", {}).get("fill_value", -999) or not math.isfinite(value) for value in values):
            raise ValueError("NASA missing observation")
        rows.append({"timestamp": stamp(datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=timezone.utc)),
                     "allsky_sfc_sw_dwn": values[0], "temperature_2m": values[1]})
    if len(rows) != 168:
        raise ValueError(f"Expected 168 NASA hours, got {len(rows)}")
    target = folder / "nasa_power_berlin_2019-01-07_week.csv"
    write_csv(target, rows)
    metadata = folder / "nasa_power_metadata.json"
    write_json(metadata, {key: payload.get(key) for key in ("header", "parameters", "geometry", "messages")})
    return [record(target, url, geography="Berlin, 52.52N 13.405E", source_type="satellite/reanalysis/model products",
                   license="NASA POWER source acknowledgment; consult source metadata", units=payload.get("parameters")),
            record(metadata, url, kind="units, location, and provider metadata")]


def acn(folder):
    """Legacy acquisition entry point delegates to the official streaming client."""
    from dotenv import load_dotenv
    from fetch_acn import fetch
    load_dotenv(ROOT / ".env")
    token = os.environ.get("ACN_API_TOKEN")
    if not token:
        raise ValueError("Set ACN_API_TOKEN; see scripts/fetch_acn.py for six-month acquisition")
    try:
        from acnportal.acndata import DataClient
    except ImportError as exc:
        raise ValueError("Use uv run --with acnportal==0.3.3 python scripts/fetch_acn.py for optional ACN acquisition") from exc
    target = folder / "acn/caltech_2019_h1.csv"
    metadata = fetch(DataClient(token), "caltech", datetime(2019, 1, 1, tzinfo=timezone.utc),
                     datetime(2019, 7, 1, tzinfo=timezone.utc), target, 6.6)
    return [record(target, "https://ev.caltech.edu/dataset.html", measured=True,
                   assumptions=metadata["assumptions"], license="Redistribution terms unverified; ignored by Git")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="*", choices=["opsd", "nlr", "nasa", "acn"], default=[])
    parser.add_argument("--export-reference", action="store_true", help="Copy acquired NLR/NASA demo slices and notices into shareable data/reference")
    args = parser.parse_args()
    demo = synthetic()
    print(f"Generated {len(demo)} synthetic demo files.", flush=True)
    folder = ROOT / "data" / "external"
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"schema_version": 1, "sources": {}}
    failed = False
    for source in args.sources:
        try:
            files = globals()[source](folder)
            manifest["sources"][source] = {"status": "downloaded", "retrieved_at_utc": stamp(datetime.now(timezone.utc)), "files": files}
            print(f"{source}: {sum(f.get('rows', 0) for f in files)} rows, {sum(f['bytes'] for f in files)} bytes retained", flush=True)
        except (ValueError, KeyError, OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
            failed = True
            # Do not print token-bearing URLs, provider response bodies, or credentials.
            detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            previous = manifest["sources"].get(source, {})
            manifest["sources"][source] = {"status": "failed", "error": detail, "previous_result": previous}
            print(f"{source}: FAILED ({detail})", flush=True)
        write_json(manifest_path, manifest)
    if args.export_reference:
        shared = ROOT / "data" / "reference"
        shared.mkdir(parents=True, exist_ok=True)
        shared_records = []
        for source in ("nlr", "nasa"):
            result = manifest["sources"].get(source, {})
            if result.get("status") != "downloaded":
                raise ValueError(f"Acquire {source} successfully before exporting reference slices")
            for entry in result["files"]:
                original = ROOT / entry["path"]
                if hashlib.sha256(original.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Source hash mismatch: {original.name}")
                target = shared / original.name
                shutil.copyfile(original, target)
                shared_records.append(dict(entry, path=target.relative_to(ROOT).as_posix()))
        write_json(shared / "manifest.json", {"schema_version": 1, "files": shared_records})
        print(f"Exported {len(shared_records)} small reference files with provenance and NLR notice.", flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
