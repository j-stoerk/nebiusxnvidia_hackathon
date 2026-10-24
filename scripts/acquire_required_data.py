"""Acquire the original design's public inputs, with field-level provenance.

Raw ACN JSON/identities stay in memory. All acquired files are ignored by Git.
Missing vehicle ratings, SoC and fault telemetry are never invented.
"""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.fetch_acn import instant

MIRROR = "https://raw.githubusercontent.com/yvenn-amara/ev-load-open-data/3b1cb67d1b02f8fea0451c16fbcfaee34449ce46/1.%20Input%20Data/7.%20ACN%20Data/Caltech.json"
PORTAL = "https://raw.githubusercontent.com/zach401/acnportal/14e723b11339e56ca3afd2bf4969f9e4bc8c2623/acnportal/"
SMARD = "https://www.smard.de/app/chart_data/4169/DE/"


def fetch(url, registry):
    content = bytearray()
    with httpx.stream("GET", url, timeout=40, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 32 * 1024 * 1024:
                raise ValueError("Source exceeds the 32 MiB acquisition budget")
    registry.append({"url": url, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return bytes(content)


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def hardware_catalog(source, evse_source):
    """Read literals from the pinned primary model; never execute downloaded code."""
    function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "caltech_acn")
    defaults = dict(zip([a.arg for a in function.args.args][-len(function.args.defaults):], function.args.defaults))
    voltage, transformer = defaults["voltage"].value, defaults["transformer_cap"].value
    groups = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"CC_pod_ids", "AV_pod_ids", "AB_ids", "BC_ids", "CA_ids"}:
                groups[name] = [f"CA-{n.value}" if isinstance(n.value, int) else n.value
                                for part in ast.walk(node.value) if isinstance(part, ast.List)
                                for n in part.elts if isinstance(n, ast.Constant)]
    groups["AB_ids"] += groups["CC_pod_ids"] + groups["AV_pod_ids"]
    if "range(6, 33)" not in evse_source or "[0, 8, 16, 24, 32]" not in evse_source:
        raise ValueError("Unrecognized EVSE pilot definitions; inspect the source")
    rows = []
    for group, angle in [("AB_ids", 30), ("BC_ids", -90), ("CA_ids", 150)]:
        for name in groups[group]:
            clipper = name in groups["CC_pod_ids"]
            pilots = [0, 8, 16, 24, 32] if clipper else [0, *range(6, 33)]
            rows.append({"charger_id": name, "equipment": "ClipperCreek" if clipper else "AeroVironment",
                         "connector_type": "J1772",
                         "nominal_voltage_v": voltage, "max_pilot_a": max(pilots),
                         "nominal_equipment_ceiling_kw": voltage * max(pilots) / 1000,
                         "allowed_pilot_a": ";".join(map(str, pilots)), "phase_angle_deg": angle,
                         "operational_availability": "unknown"})
    if len(rows) != 54 or len({r["charger_id"] for r in rows}) != 54:
        raise ValueError("Published Caltech inventory did not resolve to 54 ports")
    return rows, {"published_transformer_cap_kw": transformer, "nominal_evse_voltage_v": voltage,
                  "published_port_count": len(rows), "cc_pod_limit_a": 80, "av_pod_limit_a": 80,
                  "scope": "Published historical ACN network model; phase/transformer constraints also apply. Not a current site survey or per-vehicle acceptance rating."}


def request_at_arrival(item):
    requests = [r for r in item.get("userInputs") or [] if r.get("modifiedAt") and r.get("requestedDeparture") and r.get("kWhRequested") is not None]
    requests.sort(key=lambda r: instant(r["modifiedAt"]))
    known = [r for r in requests if instant(r["modifiedAt"]) <= instant(item["connectionTime"])]
    return (known[-1], True) if known else (requests[0], False) if requests else (None, False)


def session_rows(items, catalog, start, end):
    observed, ready = [], []
    powers = {r["charger_id"]: r["nominal_equipment_ceiling_kw"] for r in catalog}
    for i, item in enumerate(items):
        arrival, departure = instant(item["connectionTime"]), instant(item["disconnectTime"])
        if not start <= arrival < end:
            continue
        request, known = request_at_arrival(item)
        public_id, port = f"CALTECH-{i + 1:07d}", item.get("spaceID", "")
        observed.append({"vehicle_id": public_id, "arrival_time": arrival.isoformat(),
                         "observed_disconnect_time": departure.isoformat(), "delivered_meter_kwh": item["kWhDelivered"],
                         "charger_id": port, "source_station_id": item.get("stationID", ""), "source_site_id": item.get("siteID", ""),
                         "request_recorded_at": instant(request["modifiedAt"]).isoformat() if request else "",
                         "requested_departure_time": instant(request["requestedDeparture"]).isoformat() if request else "",
                         "requested_energy_kwh": request["kWhRequested"] if request else "",
                         "request_known_at_arrival": known, "nominal_equipment_ceiling_kw": powers.get(port, "")})
        if request and known and port in powers:
            deadline, energy = instant(request["requestedDeparture"]), float(request["kWhRequested"])
            if departure > arrival and deadline > arrival and math.isfinite(energy) and 0 <= energy <= 1000:
                ready.append({"vehicle_id": public_id, "arrival_time": arrival.isoformat(), "departure_time": deadline.isoformat(),
                              "energy_required_kwh": energy, "max_charging_power_kw": powers[port],
                              "charger_id": port, "connector_type": "J1772"})
    return observed, ready


def smard_prices(start, end, registry):
    stamps = json.loads(fetch(SMARD + "index_hour.json", registry))["timestamps"]
    a, b = start.timestamp() * 1000, end.timestamp() * 1000
    stamps = [t for t in stamps if t < b and t + 7 * 86400000 > a]
    urls = [SMARD + f"4169_DE_hour_{t}.json" for t in stamps]
    with ThreadPoolExecutor(max_workers=4) as pool:
        chunks = list(pool.map(lambda url: json.loads(fetch(url, registry)), urls))
    values = {}
    for chunk in chunks:
        for stamp, price in chunk["series"]:
            if a <= stamp < b and price is not None:
                if not math.isfinite(float(price)):
                    raise ValueError("Nonfinite SMARD price")
                if stamp in values and values[stamp] != price:
                    raise ValueError("Conflicting SMARD observations")
                values[stamp] = price
    expected = int((end - start).total_seconds() / 3600)
    if len(values) != expected or any(a + i * 3600000 not in values for i in range(expected)):
        raise ValueError("SMARD price range is incomplete; missing data are not interpolated")
    native = [{"timestamp": datetime.fromtimestamp(t / 1000, timezone.utc).isoformat(), "price_eur_per_mwh": v} for t, v in sorted(values.items())]
    slots = [{"timestamp": (instant(row["timestamp"]) + timedelta(minutes=15 * q)).isoformat(), "price_eur_per_kwh": row["price_eur_per_mwh"] / 1000}
             for row in native for q in range(4)]
    return native, slots


def tariff_prices(tariff, start, end):
    rows, cursor = [], start
    while cursor < end:
        local = cursor.astimezone(ZoneInfo("America/Los_Angeles"))
        day = local.strftime("%m-%d")
        for schedule in tariff["schedule"]:
            a, b = schedule["effective_start"], schedule["effective_end"]
            season = a <= day <= b if a <= b else day >= a or day <= b
            weekend = (local.weekday() >= 5) == (schedule["dow_mask"] == "WEEKENDS")
            if season and weekend:
                index = max(i for i, hour in enumerate(schedule["times"]) if hour <= local.hour)
                rows.append({"timestamp": cursor.isoformat(), "price_usd_per_kwh": schedule["tariffs"][index]})
                break
        else:
            raise ValueError("Historical tariff does not cover this interval")
        cursor += timedelta(minutes=15)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-04-01")
    parser.add_argument("--end", default="2019-10-01")
    args = parser.parse_args()
    start, end = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in (args.start, args.end)]
    if not 1 <= (end - start).days <= 366:
        parser.error("Acquire 1–366 days at a time")
    folder = ROOT / "data/external/required" / f"{args.start}_{args.end}"
    folder.mkdir(parents=True, exist_ok=True)
    registry = []
    urls = [MIRROR, PORTAL + "acnsim/network/sites/caltech_acn.py", PORTAL + "acnsim/models/evse.py",
            PORTAL + "signals/tariffs/tariff_schedules/sce_tou_ev_4_march_2019.json"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        raw, network, evse, rates = list(pool.map(lambda u: fetch(u, registry), urls))
    catalog, site = hardware_catalog(network.decode(), evse.decode())
    observed, ready = session_rows(json.loads(raw)["_items"], catalog, start, end)
    del raw
    write_csv(folder / "caltech_observed_sessions.csv", observed)
    write_csv(folder / "caltech_requests_equipment_ceiling.csv", ready)
    write_csv(folder / "caltech_charger_catalog.csv", catalog)
    (folder / "caltech_site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    tariff = json.loads(rates)
    (folder / "sce_historical_tariff.json").write_text(json.dumps(tariff, indent=2) + "\n", encoding="utf-8")
    write_csv(folder / "sce_historical_prices_usd_15min.csv", tariff_prices(tariff, start, end))
    native, slots = smard_prices(start, end, registry)
    write_csv(folder / "germany_day_ahead_eur_mwh_hourly.csv", native)
    write_csv(folder / "germany_day_ahead_eur_kwh_15min.csv", slots)
    files = [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.is_file() and p.name != "manifest.json"]
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "start": start.isoformat(), "end": end.isoformat(),
                "observed_sessions": len(observed), "records_with_requested_parameters": sum(r["requested_energy_kwh"] != "" for r in observed),
                "requests_known_at_arrival": len(ready), "german_price_hours": len(native),
                "published_ports": len(catalog), "files": files, "sources": sorted(registry, key=lambda r: r["url"]),
                "scope": "ACN is a public research mirror with unverified original extraction/timezone history. Requested energy/deadlines are recorded request parameters, potentially preferences/defaults; this archive lacks an explicit user/default source flag. They are not delivered-energy proxies. IDs are session aliases, not persistent vehicles.",
                "connector_documentation": "https://thesis.library.caltech.edu/14191/1/Lee_Zachary_J_2021_Thesis.pdf (J1772 level-2 actuation; the vehicle may draw less than the pilot)",
                "power_limit": "CSV max_charging_power_kw is the published nominal EVSE ceiling at 208 V and 32 A (unity power factor), NOT a measured per-vehicle acceptance limit.",
                "availability": "Observed plug occupancy is available; real fault/online status is unknown. Silence is not interpreted as a fault.",
                "prices": "SMARD is German wholesale EUR, attributed to Bundesnetzagentur | SMARD.de (CC BY 4.0); hourly observations held for four slots. SCE is the ACN team's historical research tariff in USD, not a confirmed site contract or a current tariff. No cross-region/currency join is performed.",
                "missing": ["Per-vehicle maximum acceptance power", "Actual battery capacity/SoC/target SoC and charging efficiency", "Measured operational charger fault/online telemetry", "German depot duty cycles, connection agreement and retail contract"]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("observed_sessions", "requests_known_at_arrival", "german_price_hours", "published_ports", "missing")}, indent=2))
    print(f"Retained {sum(f['bytes'] for f in files):,} bytes under {folder}")


if __name__ == "__main__":
    main()
