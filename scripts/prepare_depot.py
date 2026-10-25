"""Prepare a complete demo or operator-supplied roster using existing app contracts.

Operator input: roster.csv, prices.csv, station.json. Optional target_soc is a
requested fraction, never an observed end-of-charge label. Private inputs stay ignored.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.models import StationConfig as Station
from backend.app.services.csv_validator import InputError, _frame as csv_frame, validate_prices_csv as parse_prices, validate_sessions_csv as parse_sessions
from backend.app.services.baseline_scheduler import build_baseline
from backend.app.services.optimizer import optimize_schedule
from backend.app.services.schedule_validator import validate_schedule
from scripts.prepare_data import write_csv, write_json


def csv_bytes(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def normalize_roster(content):
    """Use declared targets; reject missing goals or conflicting kWh and SoC."""
    frame = csv_frame(content)
    if not 1 <= len(frame) <= 100:
        raise InputError("Roster must contain 1–100 sessions")
    rows = frame.to_dict("records")
    for number, row in enumerate(rows, 2):
        target = row.pop("target_soc", "")
        if target != "":
            try:
                target, initial, capacity = [float(v) for v in
                    (target, row["initial_soc"], row["battery_capacity_kwh"])]
                if not all(map(math.isfinite, (target, initial, capacity))) or not 0 <= initial <= target <= 1 or capacity <= 0:
                    raise ValueError("Invalid capacity or initial/target SoC fractions")
                required = capacity * (target - initial)
                supplied = row.get("energy_required_kwh", "")
                if supplied != "" and not math.isclose(float(supplied), required, abs_tol=1e-6):
                    raise ValueError("Requested kWh conflicts with capacity and initial/target SoC")
                row["energy_required_kwh"] = required
            except (KeyError, ValueError) as exc:
                raise InputError([{"row": number, "message": f"target_soc needs capacity, initial_soc and a consistent energy goal: {exc}"}]) from exc
        if row.get("energy_required_kwh", "") == "":
            raise InputError([{"row": number, "message": "Supply requested energy_required_kwh or target_soc with capacity/initial_soc; no operator goal is guessed"}])
    return parse_sessions(csv_bytes(rows))


def demo_inputs(folder):
    """Reuse the existing four-van story, with explicit synthetic SoC goals."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("roster.csv", "station.json", "prices.csv"):
        (folder / name).write_bytes((ROOT / "data/demo/prepared/example-input" / name).read_bytes())


def compare(sessions, station, prices):
    results = {}
    for name in ("FCFS", "EDF", "LLF", "optimized"):
        schedule = optimize_schedule(sessions, station, prices) if name == "optimized" else build_baseline(sessions, station, prices, policy=name)
        validate_schedule(sessions, station, schedule)
        values = schedule.metrics.model_dump()
        results[name] = {"independently_validated": True, "solver_status": schedule.solver_status,
                        **{k: values[k] for k in ("unserved_kwh", "peak_power_kw", "cost_eur", "target_success_percent")}}
    return results


def build_pack(source, output, demo=False):
    if source.resolve() == output.resolve():
        raise ValueError("Keep the source roster and prepared output in different folders")
    inputs = {name: (source / name).read_bytes() for name in ("roster.csv", "prices.csv", "station.json")}
    config = json.loads(inputs["station.json"])
    missing = {"simulated", "station_id", "station_power_limit_kw", "charging_efficiency", "chargers"} - config.keys()
    if missing:
        raise ValueError(f"Declare station settings explicitly: {', '.join(sorted(missing))}")
    for charger in config["chargers"]:
        if {"charger_id", "max_power_kw", "connector_type", "available"} - charger.keys():
            raise ValueError("Each charger needs an explicit ID, power, connector type and availability")
    station = Station.model_validate(config)
    sessions = normalize_roster(inputs["roster.csv"])
    prices = parse_prices(inputs["prices.csv"])
    results = compare(sessions, station, prices)  # Validate before emitting a usable pack.
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "sessions.csv", [s.model_dump(mode="json") for s in sessions])
    write_json(output / "station.json", station.model_dump(mode="json"))
    (output / "prices.csv").write_bytes(inputs["prices.csv"])
    write_json(output / "comparison.json", results)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "mode": "synthetic_demo" if demo else "operator_supplied_unverified",
                "input_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in inputs.items()},
                "sessions": len(sessions), "target_method": "Declared kWh, or capacity * (requested target_soc - initial_soc); battery-side linear SoC/energy approximation",
                "assumptions": ["Demo roster, targets, hardware, availability and 0.9 efficiency are synthetic; 0.8 taper transition is an uncalibrated envelope; demand rate is an illustrative published German component, with synthetic energy prices and zero prior peak."] if demo else
                    ["Operator-supplied does not certify measurements or billing terms. Targets are requests/policies. Source declarations and omitted station defaults require review; no missing roster goal is filled automatically."],
                "station_defaults": sorted(set(Station.model_fields) - config.keys()),
                "files": [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in sorted(output.iterdir()) if p.is_file() and p.name != "manifest.json"]}
    write_json(output / "manifest.json", manifest)
    return manifest, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true")
    mode.add_argument("--input", type=Path, help="Folder with roster.csv, prices.csv and station.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/external/prepared")
    args = parser.parse_args()
    source = args.input or args.output / "example-input"
    if args.demo:
        demo_inputs(source)
    manifest, results = build_pack(source, args.output, args.demo)
    print(json.dumps({"folder": str(args.output), "mode": manifest["mode"], "comparison": results}, indent=2))
    print("Use sessions.csv and prices.csv in the dashboard upload; match Station settings to station.json.")


if __name__ == "__main__":
    main()
