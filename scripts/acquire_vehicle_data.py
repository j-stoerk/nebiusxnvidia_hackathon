"""Fetch compact, separate real-measurement references; never fabricate fleet joins.

Run with optional readers: uv run --with pyarrow --with openpyxl python scripts/acquire_vehicle_data.py
Raw archives stay in memory; generated data and source notices stay outside Git.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_required_data import fetch, write_csv

TUM_COMMIT = "6bac2936e280b2d7f45607e5cb624a18b41b3faa"
TUM = f"https://raw.githubusercontent.com/TUMFTM/electric-vehicle-uds-dataset/{TUM_COMMIT}/"
MOBI = "https://api.mobidata-bw.de/ocpdb/api/public/ocpi/3.0/evses"
HISTORY = "https://mobidata-bw.de/api/3/action/datastore_search"
RESOURCE = "89fb3a0b-cc42-48a6-b17a-8f1b46abccf1"


def query(url, params, registry):
    return json.loads(fetch(str(httpx.URL(url, params=params)), registry))


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def article(number, folder, registry):
    """Keep attribution and version metadata, without unrelated Figshare attachments."""
    data = json.loads(fetch(f"https://api.figshare.com/v2/articles/{number}/versions/1", registry))
    save_json(folder / "source_notice.json", {key: data.get(key) for key in
              ("title", "doi", "url_public_html", "version", "authors", "license", "description")})
    return {f["name"]: f["download_url"] for f in data["files"]}


def tum(folder, registry):
    import pyarrow.parquet as pq  # Acquisition-only dependency, never needed by the demo.

    for name in ("README.MD", "LICENSE", "data/value_overview.csv"):
        content = fetch(TUM + name, registry)
        (folder / Path(name).name).write_bytes(content)
    url = f"https://media.githubusercontent.com/media/TUMFTM/electric-vehicle-uds-dataset/{TUM_COMMIT}/data/uds_data/CUP3.parquet"
    raw = fetch(url, registry)
    expected = "38efe95854cfcd4014c4b5d96168e7d3d6a419d1daf7a45468772ee14ba38e26"
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Pinned TUM file checksum differs")
    frame = pq.read_table(BytesIO(raw)).to_pandas()
    soc = frame.loc[frame.value_id == 900, ["vehicle_id", "time", "value"]].copy()
    if not soc.value.between(0, 100).all() or set(soc.vehicle_id) != {"CUP3"}:
        raise ValueError("Unexpected TUM vehicle or SoC range")
    soc.columns = ["vehicle_id", "source_time_unspecified_timezone", "soc_percent"]
    soc.sort_values("source_time_unspecified_timezone").to_csv(folder / "cup3_observed_soc.csv", index=False)
    # Rated capacity and power are specifications, not measured aged capacity/acceptance.
    oem = "https://www.seat-cupra-mediacenter.com/CUPRA-Brand/presskits/cupra-born-se/technical-data"
    fetch(oem, registry)
    save_json(folder / "cup3_vehicle.json", {"vehicle_id": "CUP3", "model": "CUPRA Born 2022",
              "nominal_usable_battery_kwh": 58, "rated_dc_max_kw": 120,
              "capacity_source": TUM + "README.MD", "power_source": oem,
              "scope": "Model-level ratings. No measured capacity, current, charging power, requested target SoC or planned departure in this extract. Source timestamps are naive; timezone is unknown."})
    return {"soc_observations": len(soc), "vehicles": 1,
            "license": "CC BY-NC 4.0; TUMFTM and the authors listed in README.MD",
            "scope": "Real German field telemetry, 2022-11 to 2023-04. SoC readings include driving and parking; endpoints are not driver targets. No linkage to anonymous ACN vehicles."}


def efficiency_rows(frame, metric):
    """Retain experiment row identity: repeated model names are separate tests."""
    rows = []
    for i, (_, row) in enumerate(frame.iterrows(), start=2):
        for current, value in row.iloc[1:].items():
            if pd.isna(value):
                continue  # Unmeasured cells must not become zero efficiency.
            measured = float(value) / (100 if metric == "efficiency_fraction" else 1)
            if not math.isfinite(measured):
                raise ValueError("Nonfinite experimental measurement")
            valid = (0 < measured <= 1 if metric == "efficiency_fraction" else
                     0 <= measured <= 1 if metric == "power_factor" else True)
            rows.append({"source_excel_row": i, "vehicle_model": row.iloc[0],
                         "charging_current_a": float(current), metric: measured,
                         "quality_flag": "recorded" if valid else f"invalid_{metric}_requires_review"})
    return rows


def dtu(folder, registry):
    files = article(25425262, folder, registry)
    readme = next(url for name, url in files.items() if name.lower() == "readme.txt")
    (folder / "README.txt").write_bytes(fetch(readme, registry))
    counts = {}
    for filename, metric in [("Efficiency_3phase_data.xlsx", "efficiency_fraction"),
                             ("Powerfactor_3phase_data.xlsx", "power_factor"),
                             ("Reactive_power_3phase_data.xlsx", "reactive_power_var")]:
        frame = pd.read_excel(BytesIO(fetch(files[filename], registry)))
        rows = efficiency_rows(frame, metric)
        write_csv(folder / f"{metric}.csv", rows)
        counts[metric] = len(rows)
    return {"observations": counts, "license": "CC BY 4.0; Kristian Sevdari, DTU, DOI 10.11583/DTU.25425262.v1",
            "scope": "Controlled onboard-charger experiments by model and current; missing test cells stay absent. Source zero efficiencies and out-of-range power factors are preserved and flagged for exclusion from models. Not measurements of the ACN or TUM vehicles; no automatic efficiency assignment."}


def curves(folder, registry):
    files = article(30570653, folder, registry)
    # The combined profile preserves source point order; derived time/capacity are omitted.
    url = files["main-data-fastcharge-profile-het.csv"]
    frame = pd.read_csv(BytesIO(fetch(url, registry)))
    selected = frame[["filename", "soe.percent", "power.kW", "charger_company_source", "data_input_type"]].copy()
    selected.columns = ["profile_id", "source_soc_or_soe_percent", "power_kw", "plot_source", "data_input_type"]
    valid = selected.source_soc_or_soe_percent.between(0, 100) & selected.power_kw.ge(0)
    selected["quality_flag"] = valid.map({True: "digitized", False: "invalid_axis_requires_review"})
    selected["source_point_order"] = selected.groupby("profile_id", sort=False).cumcount()
    selected.to_csv(folder / "digitized_dc_curves.csv", index=False)
    return {"curve_points": len(selected), "profiles": selected.profile_id.nunique(), "flagged_points": int((~valid).sum()),
            "license": "CC BY 4.0; Morin, Chatra, Whitacre and Michalek; DOI 10.6084/m9.figshare.30570653.v1",
            "scope": "Digitized Fastned/InsideEVs plots, not raw meter telemetry. Source labels mix SOC/SOE; not calibrated cell SOC. Out-of-range digitization points are preserved and flagged, not clipped. Capacity metadata contain model/filename inconsistencies and are deliberately excluded. No curve is assigned to an ACN or TUM vehicle."}


def evse_rows(items, observed_at, source_uid=""):
    rows = []
    for item in items:
        if not item.get("evse_id", "").startswith("DE*") or item.get("presence") != "PRESENT":
            continue
        status = item["status"]
        available = True if status == "AVAILABLE" else False if status in {
            "CHARGING", "BLOCKED", "INOPERATIVE", "OUTOFORDER", "RESERVED"} else None
        for connector in item.get("connectors", []):
            watts = connector.get("max_electric_power")
            rows.append({"evse_id": item["evse_id"], "connector_id": connector["id"], "source_uid": source_uid,
                         "connector_type": connector["standard"], "power_type": connector["power_type"],
                         "rated_connector_kw": watts / 1000 if watts is not None else "",
                         "max_voltage_v": connector.get("max_voltage", ""),
                         "max_current_a": connector.get("max_amperage", ""),
                         "reported_status": status, "available_for_new_session": available,
                         "observed_at_utc": observed_at, "status_last_updated": item.get("status_last_updated", ""),
                         "source_last_updated": item["last_updated"]})
    return rows


def mobidata(folder, registry):
    observed = datetime.now(timezone.utc).isoformat()
    rows = []
    notices = query("https://api.mobidata-bw.de/ocpdb/api/public/v1/sources", {}, registry)
    save_json(folder / "source_notices.json", [r for r in notices["items"] if r["uid"] in
              {"datex2_chargecloud", "datex2_ecomovement"}])
    for status in ("AVAILABLE", "CHARGING", "OUTOFORDER", "INOPERATIVE", "UNKNOWN", "STATIC"):
        data = query(MOBI, {"status": status, "limit": 100, "source_uid": "datex2_chargecloud"}, registry)
        rows.extend(evse_rows(data["items"], observed, "datex2_chargecloud"))
    write_csv(folder / "german_evse_snapshot.csv", rows)
    # One real German location's observed counts, not an invented outage timeline.
    data = query(HISTORY, {"resource_id": RESOURCE, "filters": json.dumps({"station_id": 323832}),
                          "limit": 1000, "sort": "_id asc"}, registry)
    if not data.get("success") or data["result"]["total"] > 1000:
        raise ValueError("Historical status query failed or was truncated")
    records = data["result"]["records"]
    fields = ["station_id", "city", "operator_name", "source", "datastore_updated_at", "status_last_updated",
              "last_updated", "realtime_data_outdated", "max_electric_power"]
    fields += ["chargepoint_" + status + "_count" for status in
               ("available", "charging", "unknown", "inoperative", "outoforder", "static", "reserved")]
    if not records or any(r["city"] != "Heilbronn" for r in records):
        raise ValueError("Unexpected historical station")
    write_csv(folder / "heilbronn_observed_status_history.csv", [{k: r.get(k) for k in fields} for r in records])
    return {"connector_rows": len(rows), "evses": len({r["evse_id"] for r in rows}), "history_snapshots": len(records),
            "license": "MobiData BW / chargecloud / EcoMovement; aggregate Datenlizenz Deutschland Namensnennung 2.0; selected source feeds declare CC0 in source_notices.json. See https://mobidata-bw.de/dataset/e-ladesaulen.",
            "scope": "Bounded, status-stratified German sample, not a representative availability estimate. Multiple connectors on one EVSE are alternatives, not independent chargers. UNKNOWN/STATIC stay unknown. Published connector power takes precedence over voltage/current arithmetic. Historical counts are sampled observations, not exact transition times or OCPP fault causes. Not the ACN site."}


def acquire(name, loader):
    folder = ROOT / "data/external/real" / name
    folder.mkdir(parents=True, exist_ok=True)
    registry = []
    details = loader(folder, registry)
    files = [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(folder.iterdir()) if p.is_file() and p.name != "manifest.json"]
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), **details,
                "files": files, "sources": registry}
    save_json(folder / "manifest.json", manifest)
    # A small tracked inventory makes the ignored data discoverable/reproducible.
    report_path = ROOT / "data/acquisition-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["sources"][f"real_{name}"] = {"status": "downloaded", **manifest,
        "source_manifest": (folder / "manifest.json").relative_to(ROOT).as_posix(),
        "files": [{**f, "path": (folder / f["file"]).relative_to(ROOT).as_posix()} for f in files]}
    save_json(report_path, report)
    print(json.dumps({"source": name, **details, "retained_bytes": sum(f["bytes"] for f in files)}), flush=True)


def main():
    loaders = {"tum": tum, "dtu": dtu, "curves": curves, "mobidata": mobidata}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", choices=loaders, default=list(loaders))
    args = parser.parse_args()
    for name in args.sources:
        acquire(name, loaders[name])


if __name__ == "__main__":
    main()
