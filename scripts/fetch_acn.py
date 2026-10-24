"""Import ACN website JSON or stream the official client; retain no raw/PII fields."""

import argparse
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            result = parsedate_to_datetime(value)
    if result.tzinfo is None:
        raise ValueError("ACN timestamps need an explicit timezone; do not guess historical offsets")
    return result.astimezone(timezone.utc)


def normalized(item, index, power_kw):
    arrival, departure = instant(item["connectionTime"]), instant(item["disconnectTime"])
    energy = float(item["kWhDelivered"])
    if departure <= arrival or energy < 0:
        return None
    return {"vehicle_id": f"ACN-{index:07d}", "arrival_time": arrival.astimezone(timezone.utc).isoformat(),
            "departure_time": departure.astimezone(timezone.utc).isoformat(), "energy_required_kwh": energy,
            "max_charging_power_kw": power_kw, "charger_id": str(item.get("stationID") or "")}


def write_sessions(items, site, target, power_kw, source):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".partial.csv")
    if target.exists() or temporary.exists():
        raise ValueError("Output already exists; choose a fresh path")
    kept, skipped, first, last = 0, 0, None, None
    try:
        with temporary.open("x", newline="", encoding="utf-8") as stream:
            writer = None
            for index, item in enumerate(items, 1):
                if index > 100000 or stream.tell() > 32 * 1024 * 1024:
                    raise ValueError("Acquisition exceeds 100,000 sessions / 32 MiB; reduce the date range")
                row = normalized(item, index, power_kw)
                if row is None:
                    skipped += 1
                    continue
                if writer is None:
                    writer = csv.DictWriter(stream, fieldnames=list(row), lineterminator="\n")
                    writer.writeheader()
                writer.writerow(row)
                kept += 1
                first = min(first or row["arrival_time"], row["arrival_time"])
                last = max(last or row["arrival_time"], row["arrival_time"])
        if not kept:
            raise ValueError("ACN returned no usable sessions")
        temporary.rename(target)
    finally:
        temporary.unlink(missing_ok=True)
    metadata = {"source": source, "site": site, "observed_arrival_start": first, "observed_arrival_end": last,
                "kept": kept, "skipped_negative_energy_or_invalid_duration": skipped,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "assumptions": "Observed delivered meter kWh and disconnect are retrospective proxies, not known requirements. Efficiency=1. Rated power is user-assumed, not inferred from future observations. Public station IDs and zero-energy occupied sessions are retained; station configuration must match these physical ports. No persistent vehicle IDs or SoC."}
    target.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def fetch(client, site, start, end, target, power_kw):
    return write_sessions(client.get_sessions_by_time(site, start, end, timeseries=False),
                          site, target, power_kw, "ACN-Data via acnportal DataClient")


def import_export(content, site, target, power_kw, source="ACN-Data website JSON export"):
    if len(content) > 32 * 1024 * 1024:
        raise ValueError("JSON export exceeds the 32 MiB budget")
    payload = json.loads(content)
    if isinstance(payload, dict):
        if payload.get("_links", {}).get("next"):
            raise ValueError("This is an incomplete API page; use the full website export")
        items = payload.get("_items")
    else:
        items = payload
    if not isinstance(items, list) or not items or not all(isinstance(item, dict) for item in items):
        raise ValueError("Expected an ACN session array or a JSON object with _items")
    if isinstance(payload, dict) and payload.get("_meta", {}).get("total", len(items)) > len(items):
        raise ValueError("Export contains fewer sessions than its declared total")
    metadata = write_sessions(items, site, target, power_kw, source)
    metadata["source_json_sha256"] = hashlib.sha256(content).hexdigest()
    target.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=["caltech", "jpl", "office001"], default="caltech")
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default="2019-07-01")
    parser.add_argument("--power-kw", type=float, default=6.6)
    parser.add_argument("--output", type=Path, default=ROOT / "data/external/acn/caltech_2019_h1.csv")
    parser.add_argument("--json", type=Path, help="Import a website JSON export without an API token or client")
    args = parser.parse_args()
    start, end = [datetime.fromisoformat(v).replace(tzinfo=timezone.utc) for v in (args.start, args.end)]
    if not 0 < args.power_kw <= 1000 or not 1 <= (end - start).days <= 366:
        parser.error("Use a positive rated power and a date range of 1–366 days")
    if not args.output.resolve().is_relative_to((ROOT / "data/external").resolve()):
        parser.error("Keep acquired sessions under ignored data/external/")
    if args.json:
        if args.json.stat().st_size > 32 * 1024 * 1024:
            parser.error("JSON export exceeds the 32 MiB budget")
        print(json.dumps(import_export(args.json.read_bytes(), args.site, args.output, args.power_kw), indent=2))
        return
    load_dotenv(ROOT / ".env")
    token = os.getenv("ACN_API_TOKEN")
    if not token:
        parser.error("Use --json for a website export, or set ACN_API_TOKEN for the official Python client.")
    try:
        from acnportal.acndata import DataClient
    except ImportError:
        parser.error("Run with optional client: uv run --with acnportal==0.3.3 python scripts/fetch_acn.py")
    print(json.dumps(fetch(DataClient(token), args.site, start, end, args.output, args.power_kw), indent=2))


if __name__ == "__main__":
    main()
