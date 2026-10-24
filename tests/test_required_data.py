from datetime import datetime, timezone

from scripts.acquire_required_data import request_at_arrival, session_rows, tariff_prices


def test_only_request_versions_known_at_arrival_enter_cohort():
    item = {"connectionTime": "Mon, 01 Apr 2019 10:00:00 GMT", "disconnectTime": "Mon, 01 Apr 2019 16:00:00 GMT",
            "spaceID": "PORT", "stationID": "source-port", "siteID": "site", "kWhDelivered": 5,
            "userID": "private", "userInputs": [
                {"modifiedAt": "Mon, 01 Apr 2019 09:00:00 GMT", "requestedDeparture": "Mon, 01 Apr 2019 17:00:00 GMT", "kWhRequested": 12},
                {"modifiedAt": "Mon, 01 Apr 2019 11:00:00 GMT", "requestedDeparture": "Mon, 01 Apr 2019 18:00:00 GMT", "kWhRequested": 20}]}
    chosen, known = request_at_arrival(item)
    assert known and chosen["kWhRequested"] == 12
    start, end = datetime(2019, 4, 1, tzinfo=timezone.utc), datetime(2019, 4, 2, tzinfo=timezone.utc)
    observed, ready = session_rows([item], [{"charger_id": "PORT", "nominal_equipment_ceiling_kw": 6.656}], start, end)
    assert ready[0]["energy_required_kwh"] == 12  # Requested need, not 5 kWh delivered.
    assert "17:00:00" in ready[0]["departure_time"]  # Requested deadline, not observed unplug.
    assert ready[0]["connector_type"] == "J1772"
    assert "private" not in str(observed) and "private" not in str(ready)
    item["userInputs"].pop(0)
    observed, ready = session_rows([item], [{"charger_id": "PORT", "nominal_equipment_ceiling_kw": 6.656}], start, end)
    assert not ready and observed[0]["request_known_at_arrival"] is False


def test_missing_vehicle_or_hardware_data_are_not_invented():
    item = {"connectionTime": "Mon, 01 Apr 2019 10:00:00 GMT", "disconnectTime": "Mon, 01 Apr 2019 16:00:00 GMT",
            "spaceID": "UNKNOWN", "kWhDelivered": 5, "userInputs": []}
    start, end = datetime(2019, 4, 1, tzinfo=timezone.utc), datetime(2019, 4, 2, tzinfo=timezone.utc)
    observed, ready = session_rows([item], [], start, end)
    assert not ready and observed[0]["requested_energy_kwh"] == ""
    assert observed[0]["nominal_equipment_ceiling_kw"] == ""


def test_historical_california_tariff_uses_local_clock():
    tariff = {"schedule": [{"effective_start": "01-01", "effective_end": "12-31", "dow_mask": "WEEKDAYS",
                            "times": [0, 12], "tariffs": [.1, .3]}]}
    start, end = datetime(2019, 7, 1, 18, 45, tzinfo=timezone.utc), datetime(2019, 7, 1, 19, 15, tzinfo=timezone.utc)
    rows = tariff_prices(tariff, start, end)
    assert [r["price_usd_per_kwh"] for r in rows] == [.1, .3]
    assert all("price_eur_per_kwh" not in r for r in rows)
