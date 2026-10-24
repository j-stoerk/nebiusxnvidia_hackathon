"""Validate dataset contracts, provenance hashes, time grids, and deliberate edge cases."""

import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_manifest(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("files", [])
    sources = payload.get("sources", {})
    for source in sources.values() if isinstance(sources, dict) else []:
        if source["status"] == "downloaded":
            entries.extend(source["files"])
    for entry in entries:
        target = ((ROOT / entry["path"]) if "path" in entry else (path.parent / entry["file"])).resolve()
        require(target.is_relative_to(ROOT.resolve()), "Manifest path escapes project")
        require(target.is_file(), f"Missing file: {target}")
        content = target.read_bytes()
        require(hashlib.sha256(content).hexdigest() == entry["sha256"], f"Hash mismatch: {target.name}")
        require(len(content) == entry["bytes"], f"Size mismatch: {target.name}")
        if "rows" in entry:
            require(len(read_csv(target)) == entry["rows"], f"Row count mismatch: {target.name}")
    return len(entries)


def sessions(path, expected_count, expect_impossible=False):
    rows = read_csv(path)
    require(len(rows) == expected_count, f"Session count in {path.name}")
    require(len({row["vehicle_id"] for row in rows}) == len(rows), "Duplicate vehicle/session ID")
    impossible = 0
    for row in rows:
        require(bool(row["vehicle_id"].strip()), "Empty ID")
        arrival = datetime.fromisoformat(row["arrival_time"].replace("Z", "+00:00"))
        departure = datetime.fromisoformat(row["departure_time"].replace("Z", "+00:00"))
        require(arrival.utcoffset() is not None and departure.utcoffset() is not None, "Missing timezone")
        require(departure > arrival, "Invalid availability")
        energy, rate = float(row["energy_required_kwh"]), float(row["max_charging_power_kw"])
        require(math.isfinite(energy) and energy >= 0 and math.isfinite(rate) and rate > 0, "Invalid energy/rate")
        impossible += energy > rate * (departure - arrival).total_seconds() / 3600
    require((impossible > 0) == expect_impossible, "Unexpected per-vehicle feasibility")


def time_grid(path, column, count, minutes, aware=True):
    rows = read_csv(path)
    require(len(rows) == count, f"Unexpected grid length: {path.name}")
    times = [datetime.fromisoformat(row[column].replace("Z", "+00:00")) for row in rows]
    if aware:
        require(all(instant.utcoffset() is not None for instant in times), "Missing timezone")
    require(all(b - a == timedelta(minutes=minutes) for a, b in zip(times, times[1:])), f"Gap/duplicate in {path.name}")
    for row in rows:
        for name, value in row.items():
            if name != column:
                require(math.isfinite(float(value)), f"Non-finite {name}")
    return rows


def required_pack(folder):
    payload = json.loads((folder / "manifest.json").read_text())
    observed = {r["vehicle_id"]: r for r in read_csv(folder / "caltech_observed_sessions.csv")}
    requests = read_csv(folder / "caltech_requests_equipment_ceiling.csv")
    require(len(observed) == payload["observed_sessions"], "Observed session count differs")
    require(len(requests) == payload["requests_known_at_arrival"], "Requested-session count differs")
    for row in requests:
        source = observed[row["vehicle_id"]]
        require(source["request_known_at_arrival"] == "True", "Future request leaked into the arrival cohort")
        require(datetime.fromisoformat(source["request_recorded_at"]) <= datetime.fromisoformat(row["arrival_time"]), "Request was not known at arrival")
        require(float(row["energy_required_kwh"]) == float(source["requested_energy_kwh"]), "Requested energy was replaced")
        require(row["departure_time"] == source["requested_departure_time"], "Requested deadline was replaced")
        require(float(row["max_charging_power_kw"]) == float(source["nominal_equipment_ceiling_kw"]), "Equipment ceiling differs")
    hours = time_grid(folder / "germany_day_ahead_eur_mwh_hourly.csv", "timestamp", payload["german_price_hours"], 60)
    quarters = time_grid(folder / "germany_day_ahead_eur_kwh_15min.csv", "timestamp", len(hours) * 4, 15)
    for i, row in enumerate(quarters):
        require(math.isclose(float(row["price_eur_per_kwh"]), float(hours[i // 4]["price_eur_per_mwh"]) / 1000), "SMARD price unit conversion differs")
    time_grid(folder / "sce_historical_prices_usd_15min.csv", "timestamp", len(quarters), 15)


def real_pack(folder):
    """Check measured values and exclusions, without assigning reference models to ACN."""
    payload = json.loads((folder / "manifest.json").read_text())
    if folder.name == "tum":
        rows = read_csv(folder / "cup3_observed_soc.csv")
        require(len(rows) == payload["soc_observations"], "SoC count differs")
        for row in rows:
            require(row["vehicle_id"] == "CUP3" and 0 <= float(row["soc_percent"]) <= 100, "Invalid measured SoC")
            stamp = datetime.fromisoformat(row["source_time_unspecified_timezone"])
            require(stamp.tzinfo is None, "Unknown source timezone was invented")
        vehicle = json.loads((folder / "cup3_vehicle.json").read_text())
        require("target_soc" not in vehicle and "efficiency" not in vehicle, "Unobserved vehicle fields were added")
    elif folder.name == "dtu":
        for metric, count in payload["observations"].items():
            rows = read_csv(folder / f"{metric}.csv")
            require(len(rows) == count, "Experimental observation count differs")
            for row in rows:
                value = float(row[metric])
                valid = (0 < value <= 1 if metric == "efficiency_fraction" else
                         0 <= value <= 1 if metric == "power_factor" else True)
                require(math.isfinite(value) and (row["quality_flag"] == "recorded") == valid,
                        "Invalid experiment value lost its quality flag")
    elif folder.name == "curves":
        rows = read_csv(folder / "digitized_dc_curves.csv")
        require(len(rows) == payload["curve_points"], "Curve count differs")
        flagged = 0
        for row in rows:
            axis, power = float(row["source_soc_or_soe_percent"]), float(row["power_kw"])
            require(math.isfinite(axis) and math.isfinite(power), "Nonfinite curve point")
            valid = 0 <= axis <= 100 and power >= 0
            require((row["quality_flag"] == "digitized") == valid, "Curve quality flag differs")
            flagged += not valid
        require(flagged == payload["flagged_points"], "Flagged curve count differs")
    elif folder.name == "mobidata":
        rows = read_csv(folder / "german_evse_snapshot.csv")
        require(len(rows) == payload["connector_rows"], "Connector count differs")
        for row in rows:
            require(row["evse_id"].startswith("DE*"), "Foreign equipment in German sample")
            expected = "True" if row["reported_status"] == "AVAILABLE" else "" if row["reported_status"] in {"UNKNOWN", "STATIC"} else "False"
            require(row["available_for_new_session"] == expected, "Unknown availability became operational")
            if row["rated_connector_kw"]:
                require(math.isfinite(float(row["rated_connector_kw"])) and float(row["rated_connector_kw"]) > 0,
                        "Invalid published connector power")
        history = read_csv(folder / "heilbronn_observed_status_history.csv")
        require(len(history) == payload["history_snapshots"], "History count differs")
        require(all(r["city"] == "Heilbronn" and r["station_id"] == "323832" for r in history), "Unrelated history joined")
    elif folder.name == "optimiseprime":
        vehicles = {r["vehicle_id"]: r for r in read_csv(folder / "vehicles.csv")}
        require(len(vehicles) == payload["vehicles"], "Operator vehicle count differs")
        for vehicle in vehicles.values():
            require(all(math.isfinite(float(vehicle[k])) and float(vehicle[k]) > 0 for k in
                        ("battery_capacity_kwh", "max_charging_power_kw")), "Invalid operator vehicle specification")
        observed = read_csv(folder / "observed_vehicle_telemetry.csv")
        require(len(observed) == payload["telemetry_observations"], "Operator observation count differs")
        for row in observed:
            require(row["vehicle_id"] in vehicles and row["depot_id"] == vehicles[row["vehicle_id"]]["depot_id"], "Operator vehicle join differs")
            require(not row["soc_percent"] or 0 <= float(row["soc_percent"]) <= 100, "SoC sentinel became a measurement")
            require(datetime.fromisoformat(row["timestamp"]) >= datetime.fromisoformat(payload["asset_snapshot_before_utc"]),
                    "Future configuration used for earlier telemetry")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true")
    args = parser.parse_args()
    demo = ROOT / "data" / "demo"
    verified = verify_manifest(demo / "manifest.json")
    sessions(demo / "sample_charging_sessions.csv", 50)
    sessions(demo / "infeasible_charging_sessions.csv", 100, expect_impossible=True)
    time_grid(demo / "synthetic_prices_15min.csv", "timestamp", 672, 15)
    config = json.loads((demo / "station_config.json").read_text())
    require(config["simulated"] and config["station_power_limit_kw"] > 0, "Invalid station")
    require(len({c["charger_id"] for c in config["chargers"]}) == 10, "Charger IDs")
    events = json.loads((demo / "events.json").read_text())
    duplicate = events["scenarios"]["duplicate_delivery"]
    require(duplicate[0] == duplicate[1], "Duplicate scenario does not repeat the same event")
    reference = ROOT / "data" / "reference"
    if (reference / "manifest.json").exists():
        verified += verify_manifest(reference / "manifest.json")
        minute = time_grid(reference / "nlr_ev_load_first_week.csv", "Timestamp", 10080, 1, aware=False)
        quarter = time_grid(reference / "nlr_ev_load_15min.csv", "profile_timestamp", 672, 15, aware=False)
        energy_minute = sum(float(row["Power (kW)"]) for row in minute) / 60
        energy_quarter = sum(float(row["mean_power_kw"]) for row in quarter) / 4
        require(math.isclose(energy_minute, energy_quarter, rel_tol=1e-10, abs_tol=1e-8), "NLR resampling changed energy")
        time_grid(reference / "nasa_power_berlin_2019-01-07_week.csv", "timestamp", 168, 60)
        require((reference / "NLR_DATA_LICENSE.txt").stat().st_size > 1000, "Missing NLR notice")
    if args.external:
        external = ROOT / "data" / "external"
        verified += verify_manifest(external / "manifest.json")
        for manifest in sorted((external / "required").glob("*/manifest.json")):
            verified += verify_manifest(manifest)
            required_pack(manifest.parent)
        for manifest in sorted((external / "real").glob("*/manifest.json")):
            verified += verify_manifest(manifest)
            real_pack(manifest.parent)
        if (external / "prepared/manifest.json").exists():
            verified += verify_manifest(external / "prepared/manifest.json")
        if (external / "opsd_prices_15min.csv").exists():
            hourly = time_grid(external / "opsd_germany_2019-01-07_week.csv", "timestamp", 168, 60)
            quarter = time_grid(external / "opsd_prices_15min.csv", "timestamp", 672, 15)
            for i, row in enumerate(quarter):
                require(math.isclose(float(row["price_eur_per_kwh"]), float(hourly[i // 4]["price_eur_per_mwh"]) / 1000), "Price unit conversion")
        statuses = json.loads((external / "manifest.json").read_text())["sources"]
        for source, result in statuses.items():
            if result["status"] != "downloaded":
                print(f"Not acquired: {source}: {result.get('error', result['status'])}")
    print(f"Validated {verified} provenance hashes; session contracts, price grids, and available reference data passed.")
    print("This verifies dataset inputs; application and scheduling tests are in tests/.")


if __name__ == "__main__":
    main()
