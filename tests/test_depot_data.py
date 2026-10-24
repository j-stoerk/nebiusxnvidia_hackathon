from datetime import datetime, timezone
import csv
from io import StringIO
import json

import pytest

from backend.app.services.csv_validator import InputError, parse_prices, parse_sessions
from scripts.acquire_operator_data import asset_snapshot, telemetry_rows
from scripts.prepare_depot import build_pack, csv_bytes, demo_inputs, normalize_roster


def provider_csv(rows):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def test_complete_pack_is_uploadable_and_independently_scheduled(tmp_path):
    source, output = tmp_path / "inputs", tmp_path / "ready"
    demo_inputs(source)
    manifest, comparison = build_pack(source, output, demo=True)
    assert manifest["mode"] == "synthetic_demo"
    assert len(parse_sessions((output / "sessions.csv").read_bytes())) == 4
    assert parse_prices((output / "prices.csv").read_bytes())
    assert all(r["independently_validated"] and r["unserved_kwh"] < 1e-5 for r in comparison.values())
    assert comparison["optimized"]["peak_power_kw"] < comparison["EDF"]["peak_power_kw"]
    assert "target_soc" in (source / "roster.csv").read_text()
    assert "target_soc" not in (output / "sessions.csv").read_text()  # Existing API contract.


@pytest.mark.parametrize("change", [{"target_soc": ""}, {"target_soc": 80},
    {"target_soc": .2}, {"energy_required_kwh": 99}, {"initial_soc": ""}])
def test_operator_goals_are_never_guessed_or_silently_replaced(change):
    row = {"vehicle_id": "V1", "arrival_time": "2026-10-24T06:00:00Z", "departure_time": "2026-10-24T12:00:00Z",
           "battery_capacity_kwh": 40, "initial_soc": .25, "target_soc": .8, "max_charging_power_kw": 11}
    with pytest.raises(InputError):
        normalize_roster(csv_bytes([{**row, **change}]))
    assert normalize_roster(csv_bytes([row]))[0].energy_required_kwh == 22


def test_asset_events_do_not_leak_future_versions_and_delete_all_sockets():
    stamp = int(datetime(2021, 6, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = [{"offset": i, "timestamp": stamp + i, "message": json.dumps(item)} for i, item in enumerate([
        {"id": 1, "SocketId": "A", "operation": "Insert"},
        {"id": 1, "SocketId": "B", "operation": "Insert"},
        {"id": 1, "operation": "Delete"}])]
    rows.append({"offset": 9, "timestamp": stamp + 40 * 86400000,
                 "message": json.dumps({"id": 1, "SocketId": "C", "operation": "Insert"})})
    assert not asset_snapshot(provider_csv(list(reversed(rows))), sockets=True)


def test_telematics_sentinels_are_not_measurements():
    row = {"ev_id": 1, "utc": "2021/07/01 00:00:00.000000000", "ngp_payload_energy_level": 127,
           "ngp_payload_charging_type": 0, "ngp_payload_charging_power": 31,
           "ngp_payload_plug_connected": "false", "ngp_payload_hv_battery_is_charging": "false"}
    observed = telemetry_rows(provider_csv([row]), {1: {"id": 1, "DepotId": 2}})
    assert observed[0]["soc_percent"] == "" and observed[0]["reported_charging_power_kw"] == ""
    assert observed[0]["timestamp"].endswith("+00:00")
