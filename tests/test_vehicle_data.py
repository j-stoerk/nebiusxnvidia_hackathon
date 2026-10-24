import pandas as pd

from scripts.acquire_vehicle_data import efficiency_rows, evse_rows


def test_efficiency_units_missing_cells_and_duplicate_experiments():
    frame = pd.DataFrame([["same model", 90, None], ["same model", 0, 85]], columns=["Brand", 6, 8])
    rows = efficiency_rows(frame, "efficiency_fraction")
    assert len(rows) == 3  # Blank is unmeasured; a source zero is retained and flagged.
    assert rows[0]["efficiency_fraction"] == .9
    assert rows[1]["efficiency_fraction"] == 0
    assert rows[1]["quality_flag"] != "recorded"
    assert rows[0]["source_excel_row"] != rows[1]["source_excel_row"]
    assert rows[2]["charging_current_a"] == 8


def test_power_factor_source_error_is_flagged_without_rescaling():
    rows = efficiency_rows(pd.DataFrame([["car", 90.16]], columns=["Brand", 6]), "power_factor")
    assert rows[0]["power_factor"] == 90.16
    assert rows[0]["quality_flag"] != "recorded"


def test_reported_connector_power_and_unknown_availability_are_preserved():
    connector = {"id": "1", "standard": "IEC_62196_T2", "power_type": "AC_3_PHASE",
                 "max_voltage": 400, "max_amperage": 32, "max_electric_power": 11000}
    item = {"evse_id": "DE*TEST*1", "presence": "PRESENT", "status": "UNKNOWN",
            "last_updated": "2026-10-24T00:00:00Z", "connectors": [connector, {**connector, "id": "2"}]}
    rows = evse_rows([item], "2026-10-24T01:00:00Z")
    assert len({r["evse_id"] for r in rows}) == 1  # Alternative connectors share one EVSE.
    assert all(r["available_for_new_session"] is None and r["rated_connector_kw"] == 11 for r in rows)
    assert "target_soc" not in rows[0] and "battery_kwh" not in rows[0]
    for status, expected in [("OUTOFORDER", False), ("AVAILABLE", True), ("STATIC", None)]:
        assert evse_rows([{**item, "status": status}], "now")[0]["available_for_new_session"] is expected
    assert not evse_rows([{**item, "evse_id": "CH*TEST*1"}], "now")
