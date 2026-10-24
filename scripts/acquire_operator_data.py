"""Small Royal Mail/Optimise Prime asset snapshot and bounded telemetry sample.

The provider's public read-only SAS is discovered at runtime and never retained.
No registration, RFID, device identifiers, location traces or raw archives are saved.
"""

import csv
from datetime import datetime, timezone
from html import unescape
from io import StringIO
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.acquire_required_data import fetch, write_csv
from scripts.acquire_vehicle_data import acquire, save_json

CATALOG = "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-optimise-prime"
CUTOFF = datetime(2021, 7, 1, tzinfo=timezone.utc)


def asset_snapshot(content, sockets=False):
    """Replay configuration events known before July; never take future revisions."""
    latest, changes = {}, []
    for row in csv.DictReader(StringIO(content.decode("utf-8-sig")), delimiter=";"):
        instant = datetime.fromtimestamp(int(row["timestamp"]) / 1000, timezone.utc)
        if instant >= CUTOFF:
            continue
        changes.append((int(row["timestamp"]), int(row["offset"]), json.loads(row["message"])))
    for _, _, item in sorted(changes, key=lambda change: change[:2]):
        key = (item["id"], item.get("SocketId")) if sockets else item["id"]
        if item.get("IsDeleted") or item.get("operation") == "Delete":
            keys = [k for k in latest if k[0] == item["id"]] if sockets and not item.get("SocketId") else [key]
            for removed in keys:
                latest.pop(removed, None)
        else:
            latest[key] = item
    return latest


def telemetry_rows(content, vehicles):
    rows = []
    # Range downloads end mid-row: remove the incomplete suffix before parsing.
    text = content[:content.rfind(b"\n") + 1].decode("utf-8-sig")
    for item in csv.DictReader(StringIO(text), delimiter=";"):
        ev = vehicles.get(int(item["ev_id"])) if item["ev_id"] else None
        stamp = datetime.fromisoformat(item["utc"].replace("/", "-")).replace(tzinfo=timezone.utc)
        if not ev or stamp < CUTOFF:
            continue
        soc = item["ngp_payload_energy_level"]
        soc = float(soc) if soc and 0 <= float(soc) <= 100 else ""  # 127 is unavailable.
        power = item["ngp_payload_charging_power"]
        if item["ngp_payload_charging_type"] == "0" or not power:
            power = ""  # Unknown type uses 31 kW as a sentinel, not actual power.
        rows.append({"vehicle_id": f"OP-EV-{ev['id']}", "depot_id": ev["DepotId"],
                     "timestamp": stamp.isoformat(), "soc_percent": soc,
                     "plug_connected": item["ngp_payload_plug_connected"],
                     "is_charging": item["ngp_payload_hv_battery_is_charging"],
                     "reported_charging_power_kw": power})
    return rows


def operator_data(folder, registry):
    catalog = json.loads(fetch(CATALOG, registry))
    description = unescape(catalog["metas"]["default"]["description"])
    link = re.search(r"https://ukpnoppublicdata001\.blob\.core\.windows\.net/optimiseprime\?[^<\s]+", description).group()
    base, sas = link.split("?", 1)

    def blob(name, limit=None):
        url = base + "/" + quote(name, safe="/")
        entries = []
        if limit:
            response = httpx.get(url + "?" + sas, headers={"Range": f"bytes=0-{limit - 1}"}, timeout=40)
            response.raise_for_status()
            if response.status_code != 206 or len(response.content) > limit:
                raise ValueError("Provider did not honor the bounded Range request")
            import hashlib
            content = response.content
            registry.append({"url": url, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                             "scope": "First 8 MiB only, incomplete final CSV line excluded; not a complete month/day"})
        else:
            content = fetch(url + "?" + sas, entries)
            registry.append({**entries[0], "url": url})
        return content

    # The catalogue response includes public access tokens: hash it, never save it.
    listing = httpx.get(link + "&restype=container&comp=list&maxresults=1500", timeout=40)
    listing.raise_for_status()
    root = ET.fromstring(listing.content)
    if root.findtext("NextMarker"):
        raise ValueError("Blob listing was truncated")
    names = [n.text for n in root.findall(".//Blob/Name")]

    def named(filename):
        return next(n for n in names if n.endswith("/" + filename))

    tables = {key: asset_snapshot(blob(named(key + "_202106.csv")), key == "chargepoints")
              for key in ("depots", "evtypes", "evehicles", "cptypes", "chargepoints")}
    vehicles = []
    for vehicle in tables["evehicles"].values():
        kind = tables["evtypes"].get(vehicle["ElectricVehicleTypeId"])
        if kind:
            vehicles.append({"vehicle_id": f"OP-EV-{vehicle['id']}", "depot_id": vehicle["DepotId"],
                             "ev_type_id": kind["id"], "battery_capacity_kwh": kind["BatteryCapacityKWh"],
                             "max_charging_power_kw": kind["MaxChargeRateKW"],
                             "type_max_soc_percent": kind["MaxStateCharge"]})
    write_csv(folder / "vehicles.csv", vehicles)
    chargers = []
    for cp in tables["chargepoints"].values():
        kind = tables["cptypes"].get(cp["ChargePointTypeId"])
        if kind:
            chargers.append({"chargepoint_id": cp["id"], "socket_id": cp.get("SocketId", ""),
                             "depot_id": cp["DepotId"], "connector_type": kind["ConnectorType"],
                             "configured_rating_kw": kind["RatingKW"], "phase": kind["Phase"],
                             "type_sockets": kind["Sockets"]})
    write_csv(folder / "charger_assets.csv", chargers)
    write_csv(folder / "depot_assets.csv", [{"depot_id": d["id"], "connection_point_kva": d["ConnectionPointKVA"],
              "configured_buffer_kw": d["BufferKW"]} for d in tables["depots"].values()])
    sampled = telemetry_rows(blob(named("brand_a_charging_202107.csv"), 8 * 1024 * 1024), tables["evehicles"])
    known = {v["vehicle_id"] for v in vehicles}
    observations = [row for row in sampled if row["vehicle_id"] in known]
    write_csv(folder / "observed_vehicle_telemetry.csv", observations)
    for name in ("ev_detail_by_site.csv", "cp_counts.csv"):
        (folder / name).write_bytes(blob(named(name)))
    save_json(folder / "source_notice.json", {"title": catalog["metas"]["default"]["title"],
              "license": catalog["metas"]["default"]["license"], "attribution": "UK Power Networks / Optimise Prime / Royal Mail",
              "source": CATALOG, "guidance": "https://ukpowernetworks.opendatasoft.com/api/datasets/1.0/ukpn-optimise-prime/attachments/202302_op_deliverables_d6_dataset_guidance_v4_pdf/"})
    return {"vehicles": len(vehicles), "charger_socket_records": len(chargers), "depots": len(tables["depots"]),
            "telemetry_observations": len(observations), "asset_snapshot_before_utc": CUTOFF.isoformat(),
            "excluded_observations_missing_vehicle_type": len(sampled) - len(observations),
            "license": "CC BY 4.0; UK Power Networks / Optimise Prime / Royal Mail",
            "scope": "Real UK depot data. Configurations replayed from June 2021 messages; later reconfigurations are not replayed. July telemetry is a bounded, incomplete prefix, not an evaluation cohort. Vehicle/type joins use source IDs. Type maximum SoC is a hardware/configuration ceiling, not requested target SoC. kVA is not converted to kW. Shared CP/socket limits need verification before scheduler import. No duty roster, customer EUR tariff or target requests are inferred."}


if __name__ == "__main__":
    acquire("optimiseprime", operator_data)
